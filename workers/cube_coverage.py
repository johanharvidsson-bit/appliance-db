"""Cube Coverage & Backlog Worker: inventory only, never content mutation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


WORKER_NAME = "cube-coverage"
WORKER_VERSION = "1.0.0"
PLACEHOLDERS = ("coming soon", "placeholder", "to be added", "tbd", "lorem ipsum")

RULES = {
    "missing_model_overview": ("high", "create_model_overview", "low"),
    "missing_model_specs": ("medium", "enrich_model_specs", "low"),
    "published_model_content_placeholder": ("high", "remove_public_placeholder", "medium"),
    "unresolved_variant_candidate": ("medium", "resolve_variant_mapping", "medium"),
    "product_code_without_active_model_identity": ("critical", "resolve_relation_conflict", "high"),
    "error_code_missing_translation": ("high", "translate_error_code", "low"),
    "error_code_missing_description": ("high", "describe_error_code", "low"),
    "error_code_placeholder_content": ("high", "remove_public_placeholder", "medium"),
    "error_code_relation_conflict": ("critical", "resolve_relation_conflict", "high"),
    "fault_missing_translation": ("medium", "translate_fault", "low"),
    "fault_placeholder_content": ("high", "remove_public_placeholder", "medium"),
    "fault_relation_conflict": ("critical", "resolve_relation_conflict", "high"),
    "guide_missing_translation": ("high", "create_or_enrich_guide", "medium"),
    "guide_missing_procedure": ("high", "create_or_enrich_guide", "medium"),
    "guide_placeholder_content": ("high", "remove_public_placeholder", "medium"),
    "guide_without_topic": ("high", "create_or_enrich_guide", "medium"),
    "duplicate_procedure_candidate": ("low", None, "low"),
    "missing_source_evidence": ("medium", "add_source_evidence", "medium"),
}
WEIGHTS = {"critical": (100, "P0"), "high": (80, "P1"), "medium": (55, "P2"), "low": (25, "P3")}


def meaningful(value: Any) -> bool:
    if value is None or value == {} or value == []:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and not any(marker in value.lower() for marker in PLACEHOLDERS)
    return True


def has_placeholder(*values: Any) -> bool:
    text = " ".join(json.dumps(v, sort_keys=True) if not isinstance(v, str) else v for v in values if v is not None).lower()
    return any(marker in text for marker in PLACEHOLDERS)


def stable_hash(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class Finding:
    entity_type: str
    entity_id: str
    locale: str | None
    finding_type: str
    severity: str
    details: dict
    finding_hash: str


@dataclass(frozen=True)
class Metric:
    brand_id: int | None
    category_id: int | None
    locale: str | None
    name: str
    numerator: int | None
    denominator: int | None
    availability: str
    definition: str

    @property
    def percentage(self) -> float | None:
        return None if self.denominator in (None, 0) or self.numerator is None else round(100 * self.numerator / self.denominator, 3)


class CoverageEngine:
    """Pure offline detector. Input is a frozen, repository-produced snapshot."""

    def evaluate(self, data: dict, *, filters: dict | None = None) -> dict:
        filters = filters or {}
        scope = data["scope"]
        brand_ids = [x["id"] for x in scope["brands"] if not filters.get("brand") or x.get("slug") == filters["brand"]]
        category_ids = [x["id"] for x in scope["categories"] if not filters.get("category") or x.get("slug") == filters["category"]]
        locales = [x for x in scope["locales"] if not filters.get("locale") or x == filters["locale"]]
        findings: list[Finding] = []

        def add(kind: str, entity_type: str, entity_id: Any, locale: str | None, details: dict):
            if filters.get("finding_type") and filters["finding_type"] != kind:
                return
            severity = RULES[kind][0]
            findings.append(Finding(entity_type, str(entity_id), locale, kind, severity, details,
                                    stable_hash(WORKER_NAME, WORKER_VERSION, kind, entity_type, str(entity_id), locale, details.get("predicate_version", 1))))

        models = [m for m in data.get("models", []) if m["brand_id"] in brand_ids and m["category_id"] in category_ids]
        content = {(x["model_id"], x["locale"]): x for x in data.get("model_content", []) if x.get("publication_status") == "published"}
        specs = {x["model_id"] for x in data.get("model_specs", []) if meaningful(x.get("specs_json"))}
        for model in models:
            for locale in locales:
                if locale not in model.get("expected_locales", locales):
                    continue
                row = content.get((model["id"], locale))
                if row and has_placeholder(row.get("overview"), row.get("short_summary")):
                    add("published_model_content_placeholder", "model", model["id"], locale, {})
                elif not row or not meaningful(row.get("overview") or row.get("short_summary")):
                    add("missing_model_overview", "model", model["id"], locale, {"public_representation": model.get("public", False)})
            if model.get("specs_expected", model.get("public", False)) and model["id"] not in specs:
                add("missing_model_specs", "model", model["id"], None, {"policy": "public_models_expect_specs"})

        for candidate in data.get("variant_candidates", []):
            if candidate.get("status") == "candidate" and candidate.get("legacy_model_id") in {m["id"] for m in models}:
                add("unresolved_variant_candidate", "model", candidate["legacy_model_id"], None, {"candidate_id": candidate["id"]})
        for pc in data.get("product_codes", []):
            if pc.get("brand_id") not in brand_ids or pc.get("category_id") not in category_ids:
                continue
            if pc.get("has_active_model_identity", pc.get("model_id") in {m["id"] for m in models if m.get("has_active_identity", m.get("is_active", True))}) is False:
                add("product_code_without_active_model_identity", "product_code", pc["id"], None, {"model_id": pc.get("model_id")})

        translations = {(x["error_code_id"], x["locale"]): x for x in data.get("error_code_translations", []) if x.get("publication_status") == "published"}
        for code in data.get("error_codes", []):
            if code["brand_id"] not in brand_ids or code["category_id"] not in category_ids:
                continue
            for locale in locales:
                row = translations.get((code["id"], locale))
                if not row:
                    add("error_code_missing_translation", "error_code", code["id"], locale, {})
                elif has_placeholder(row.get("title"), row.get("description")):
                    add("error_code_placeholder_content", "error_code", code["id"], locale, {})
                elif not meaningful(row.get("description")):
                    add("error_code_missing_description", "error_code", code["id"], locale, {})

        fault_trans = {(x["fault_id"], x["locale"]): x for x in data.get("fault_translations", []) if x.get("publication_status") == "published"}
        for fault in data.get("faults", []):
            if fault["brand_id"] not in brand_ids or fault["category_id"] not in category_ids:
                continue
            for locale in locales:
                row = fault_trans.get((fault["id"], locale))
                if row and has_placeholder(row):
                    add("fault_placeholder_content", "fault", fault["id"], locale, {})
                elif not row or not meaningful(row.get("symptom_name") or row.get("description")):
                    add("fault_missing_translation", "fault", fault["id"], locale, {})

        guide_trans = {(x["guide_id"], x["locale"]): x for x in data.get("guide_translations", []) if x.get("publication_status") == "published"}
        topics = {x["guide_id"] for x in data.get("guide_topics", []) if x.get("status") == "verified"}
        content_hashes: dict[str, list[tuple[int, str]]] = {}
        for guide in data.get("guides", []):
            if guide.get("brand_id") not in brand_ids or guide.get("category_id") not in category_ids:
                continue
            if guide.get("content_status") != "published":
                continue
            for locale in locales:
                row = guide_trans.get((guide["id"], locale))
                if not row:
                    add("guide_missing_translation", "guide", guide["id"], locale, {})
                    continue
                if not meaningful(row.get("summary")) and not meaningful(row.get("steps_json")):
                    add("guide_missing_procedure", "guide", guide["id"], locale, {})
                if has_placeholder(row):
                    add("guide_placeholder_content", "guide", guide["id"], locale, {})
                procedure_hash = stable_hash(row.get("summary"), row.get("steps_json"))
                content_hashes.setdefault(procedure_hash, []).append((guide["id"], locale))
            if not guide.get("is_general", False) and guide["id"] not in topics and any(k[0] == guide["id"] for k in guide_trans):
                add("guide_without_topic", "guide", guide["id"], None, {})
        for duplicate_group in content_hashes.values():
            if len(duplicate_group) > 1:
                for guide_id, locale in duplicate_group:
                    add("duplicate_procedure_candidate", "guide", guide_id, locale, {"matches": duplicate_group})

        for conflict in data.get("relation_conflicts", []):
            add(conflict["finding_type"], conflict["entity_type"], conflict["entity_id"], conflict.get("locale"), conflict.get("details", {}))
        for relation in data.get("evidence_required_relations", []):
            if relation.get("entity_type") == "guide" and str(relation.get("entity_id")) not in {str(g["id"]) for g in data.get("guides", []) if g.get("brand_id") in brand_ids and g.get("category_id") in category_ids}:
                continue
            if relation.get("status") == "verified" and not relation.get("source_evidence_id"):
                add("missing_source_evidence", relation["entity_type"], relation["entity_id"], None, {"policy": "evidence_required"})

        metrics: list[Metric] = []
        for brand_id in brand_ids:
            for category_id in category_ids:
                cell_models = [m for m in models if m["brand_id"] == brand_id and m["category_id"] == category_id]
                for locale in locales:
                    expected = [m for m in cell_models if locale in m.get("expected_locales", locales)]
                    overview_count = sum(meaningful(content.get((m["id"], locale), {}).get("overview") or content.get((m["id"], locale), {}).get("short_summary")) for m in expected)
                    metrics.append(Metric(brand_id, category_id, locale, "model_overview_coverage", overview_count, len(expected), "not_applicable" if not expected else "available", "published meaningful overview / models expected to have a page in locale"))
                    metrics.append(Metric(brand_id, category_id, locale, "model_specs_coverage", sum(m["id"] in specs for m in expected), len(expected), "not_applicable" if not expected else "available", "meaningful non-empty specs / models expected to have a page"))
        backlog = []
        for finding in findings:
            _, action, risk = RULES[finding.finding_type]
            if action:
                priority, band = WEIGHTS[finding.severity]
                blocked = "conflict" in finding.finding_type
                backlog.append({"finding_hash": finding.finding_hash, "action_type": action, "priority": priority,
                                "priority_band": band, "risk_level": risk, "status": "blocked" if blocked else "queued",
                                "reason": {"severity": finding.severity, "rule": finding.finding_type}})
        return {"scope": scope, "entities_scanned": len(models), "cube_cells_scanned": len(brand_ids)*len(category_ids)*len(locales),
                "findings": [asdict(x) for x in findings], "backlog": backlog,
                "metrics": [{**asdict(x), "percentage": x.percentage} for x in metrics], "data_sources": data.get("data_sources", {})}


def render_markdown(report: dict) -> str:
    counts: dict[str, int] = {}
    for finding in report["findings"]:
        counts[finding["finding_type"]] = counts.get(finding["finding_type"], 0) + 1
    lines = ["# Cube Coverage & Backlog", "", f"Run: `{report['run_id']}`", f"Status: **{report['status']}**",
             f"Cube cells: {report['cube_cells_scanned']}", f"Entities scanned: {report['entities_scanned']}",
             f"Findings: {len(report['findings'])}", f"Backlog: {len(report['backlog'])}", "", "## Findings"]
    lines += [f"- `{kind}`: {count}" for kind, count in sorted(counts.items())] or ["- None"]
    lines += ["", "## Data availability"] + [f"- `{k}`: {v}" for k, v in sorted(report.get("data_sources", {}).items())]
    return "\n".join(lines) + "\n"


def write_report(report: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{report['run_id']}.json"
    md_path = output_dir / f"{report['run_id']}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
