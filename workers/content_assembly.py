"""Deterministic facts-to-draft assembly. No validation, approval, or publication."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

ASSEMBLER_VERSION = "1.0.0"


@dataclass(frozen=True)
class Template:
    id: str
    version: str
    draft_type: str
    actions: tuple[str, ...]
    required: tuple[str, ...]
    optional: tuple[str, ...]
    sections: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    safety: str = "low"


TEMPLATES = {
    "model_overview_v1": Template(
        "model_overview_v1",
        "1.0.0",
        "model_overview",
        ("create_model_overview", "translate_model_overview"),
        ("model_name",),
        (
            "brand",
            "category",
            "release_year",
            "short_summary",
            "official_description",
            "specifications",
            "variants",
            "product_codes",
            "sources",
            "related_content",
        ),
        (
            "short_summary",
            "overview",
            "key_specifications",
            "variants_summary",
            "manuals_or_sources",
            "related_content",
        ),
        (
            "typical_lifespan",
            "common_failures",
            "reliability",
            "repair_cost",
            "market_position",
            "user_rating",
        ),
    ),
    "error_code_description_v1": Template(
        "error_code_description_v1",
        "1.0.0",
        "error_code_description",
        ("describe_error_code", "translate_error_code"),
        ("code", "meaning"),
        (
            "short_description",
            "severity",
            "first_safe_checks",
            "related_faults",
            "related_guides",
            "applicability_note",
        ),
        (
            "title",
            "meaning",
            "short_description",
            "severity",
            "first_safe_checks",
            "related_faults",
            "related_guides",
            "applicability_note",
        ),
        ("invented_repair_step", "part_recommendation"),
        "medium",
    ),
    "fault_summary_v1": Template(
        "fault_summary_v1",
        "1.0.0",
        "fault_summary",
        ("translate_fault", "enrich_fault"),
        ("symptom",),
        (
            "short_description",
            "possible_causes",
            "related_error_codes",
            "related_guides",
        ),
        (
            "title",
            "short_description",
            "symptoms",
            "possible_causes",
            "related_error_codes",
            "related_guides",
        ),
        ("definitive_cause", "full_procedure"),
        "medium",
    ),
    "troubleshooting_guide_v1": Template(
        "troubleshooting_guide_v1",
        "1.0.0",
        "troubleshooting_guide",
        ("create_or_enrich_guide",),
        ("title", "steps"),
        (
            "short_description",
            "summary",
            "safety_notes",
            "prerequisites",
            "tools",
            "verification_after_work",
            "estimated_minutes",
            "difficulty",
            "applicability",
        ),
        (
            "title",
            "short_description",
            "summary",
            "safety_notes",
            "prerequisites",
            "tools",
            "steps",
            "verification_after_work",
            "estimated_minutes",
            "difficulty",
            "applicability",
        ),
        ("invented_step",),
        "high",
    ),
    "translation_v1": Template(
        "translation_v1",
        "1.0.0",
        "translation",
        ("translate_model_overview", "translate_error_code", "translate_fault"),
        (
            "source_locale",
            "target_locale",
            "source_content_hash",
            "translated_sections",
        ),
        (
            "technical_identifiers",
            "safety_notes",
            "applicability",
            "uncertainty_markers",
        ),
        ("translation_metadata", "translated_sections"),
        ("added_fact", "removed_warning", "strengthened_uncertainty"),
        "medium",
    ),
    "faq_candidate_v1": Template(
        "faq_candidate_v1",
        "1.0.0",
        "faq_candidate",
        ("create_faq_candidate",),
        ("faq_items",),
        (),
        ("faq_items",),
        ("seo_only_question",),
    ),
}

ACTION_DEFAULT = {
    action: key
    for key, t in TEMPLATES.items()
    for action in t.actions
    if not action.startswith("translate_")
}
ACTION_DEFAULT.update(
    {
        "translate_model_overview": "translation_v1",
        "translate_error_code": "translation_v1",
        "translate_fault": "translation_v1",
    }
)


class AssemblyEngine:
    def assemble(self, item: dict, template_id: str | None = None) -> dict:
        template = self._template(item, template_id)
        facts = {
            f["key"]: f
            for f in item.get("facts", [])
            if f.get("integration_status", "integrated") == "integrated"
        }
        source_hash = _hash(
            {
                k: {
                    "value": v.get("value"),
                    "version": v.get("version"),
                    "evidence": v.get("evidence", []),
                }
                for k, v in sorted(facts.items())
            }
        )
        if item.get("out_of_scope"):
            return self._draft(
                item,
                template,
                "blocked",
                "high",
                source_hash,
                [],
                [
                    self._issue(
                        None,
                        "template_input_invalid",
                        "high",
                        {"reason": "out_of_scope"},
                    )
                ],
                "new_draft",
            )
        conflicts = [f for f in facts.values() if f.get("conflicted")]
        if conflicts:
            sections = [
                self._section(
                    "conflicts",
                    0,
                    "blocked_conflict",
                    {"fact_keys": [f["key"] for f in conflicts]},
                    True,
                    conflicts,
                )
            ]
            issues = [
                self._issue(
                    "conflicts",
                    "conflicting_fact",
                    "high",
                    {"fact_keys": [f["key"] for f in conflicts]},
                )
            ]
            return self._draft(
                item,
                template,
                "blocked",
                "high",
                source_hash,
                sections,
                issues,
                "conflicts_with_existing",
            )
        forbidden = [key for key in template.forbidden_claims if key in facts]
        if forbidden:
            return self._draft(
                item,
                template,
                "blocked",
                "high",
                source_hash,
                [],
                [
                    self._issue(
                        None, "unsupported_claim", "high", {"fact_keys": forbidden}
                    )
                ],
                "new_draft",
            )
        if template.draft_type == "model_overview":
            sections, issues = self._model(facts, template)
        elif template.draft_type == "error_code_description":
            sections, issues = self._error(facts, template)
        elif template.draft_type == "fault_summary":
            sections, issues = self._fault(facts, template)
        elif template.draft_type == "troubleshooting_guide":
            sections, issues = self._guide(facts, template)
        elif template.draft_type == "translation":
            sections, issues = self._translation(facts, template, item)
        else:
            sections, issues = self._faq(facts, template)
        for section in sections:
            if (
                section["section_status"] in {"assembled", "needs_review"}
                and section["content"]
                and not section["evidence"]
            ):
                section["section_status"] = "blocked_missing_evidence"
                issues.append(
                    self._issue(
                        section["section_key"],
                        "missing_required_fact",
                        "high",
                        {"reason": "section_has_no_evidence"},
                    )
                )
        assembled = [
            s for s in sections if s["section_status"] in {"assembled", "needs_review"}
        ]
        blocked = any(
            i["severity"] in {"high", "safety_review"}
            and i["issue_type"] != "safety_review_required"
            for i in issues
        )
        incomplete = any(
            s["section_status"]
            in {"blocked_conflict", "blocked_missing_evidence", "needs_review"}
            for s in sections
        )
        status = (
            "blocked"
            if blocked or not assembled
            else ("partial" if issues or incomplete else "assembled")
        )
        risk = self._risk(facts, template, issues)
        rendered = {s["section_key"]: s["content"] for s in assembled}
        existing = item.get("existing_content")
        comparison = (
            "same_as_existing"
            if existing == rendered
            else ("updates_existing_draft" if existing else "new_draft")
        )
        if comparison == "same_as_existing":
            status = "assembled"
        return self._draft(
            item, template, status, risk, source_hash, sections, issues, comparison
        )

    def _model(self, f, t):
        sections = []
        issues = []
        summary = self._values(
            f, "short_summary", "model_name", "brand", "category", "release_year"
        )
        sections.append(
            self._section(
                "short_summary",
                0,
                "assembled" if "model_name" in f else "blocked_missing_evidence",
                summary,
                True,
                self._facts(f, *summary),
            )
        )
        overview = self._values(f, "official_description")
        sections.append(self._optional("overview", 1, overview, f))
        sections.append(
            self._optional(
                "key_specifications", 2, self._values(f, "specifications"), f
            )
        )
        sections.append(
            self._optional(
                "variants_summary", 3, self._values(f, "variants", "product_codes"), f
            )
        )
        sections.append(
            self._optional("manuals_or_sources", 4, self._values(f, "sources"), f)
        )
        sections.append(
            self._optional("related_content", 5, self._values(f, "related_content"), f)
        )
        if "official_description" not in f:
            issues.append(
                self._issue(
                    "overview",
                    "missing_required_fact",
                    "low",
                    {"fact": "official_description", "behavior": "section_omitted"},
                )
            )
        return sections, issues

    def _error(self, f, t):
        sections = []
        issues = []
        for pos, key in enumerate(t.sections):
            fact_key = {"title": "code", "first_safe_checks": "first_safe_checks"}.get(
                key, key
            )
            values = self._values(f, fact_key)
            required = key in {"title", "meaning"}
            status = (
                "assembled"
                if values
                else ("blocked_missing_evidence" if required else "omitted_no_data")
            )
            sections.append(
                self._section(
                    key, pos, status, values, required, self._facts(f, *values)
                )
            )
            if required and not values:
                issues.append(
                    self._issue(
                        key, "missing_required_fact", "high", {"fact": fact_key}
                    )
                )
        return sections, issues

    def _fault(self, f, t):
        sections = []
        issues = []
        mapping = {"title": "symptom", "symptoms": "symptom"}
        for pos, key in enumerate(t.sections):
            fact_key = mapping.get(key, key)
            values = self._values(f, fact_key)
            required = key == "title"
            sections.append(
                self._section(
                    key,
                    pos,
                    "assembled"
                    if values
                    else (
                        "blocked_missing_evidence" if required else "omitted_no_data"
                    ),
                    values,
                    required,
                    self._facts(f, *values),
                )
            )
            if required and not values:
                issues.append(
                    self._issue(
                        key, "missing_required_fact", "high", {"fact": "symptom"}
                    )
                )
        return sections, issues

    def _guide(self, f, t):
        sections = []
        issues = []
        for pos, key in enumerate(t.sections):
            values = self._values(f, key)
            required = key in {"title", "steps"}
            status = (
                "assembled"
                if values
                else ("blocked_missing_evidence" if required else "omitted_no_data")
            )
            if (
                key == "steps"
                and values
                and (
                    not isinstance(values.get("steps"), list)
                    or len(values["steps"]) < 2
                )
            ):
                status = "blocked_missing_evidence"
                issues.append(
                    self._issue(
                        key, "insufficient_procedure", "high", {"minimum_steps": 2}
                    )
                )
            sections.append(
                self._section(
                    key, pos, status, values, required, self._facts(f, *values)
                )
            )
            if required and not values:
                issues.append(
                    self._issue(
                        key,
                        "insufficient_procedure"
                        if key == "steps"
                        else "missing_required_fact",
                        "high",
                        {"fact": key},
                    )
                )
        return sections, issues

    def _translation(self, f, t, item):
        required = [k for k in t.required if k not in f]
        issues = []
        if required:
            issues.append(
                self._issue(
                    "translation_metadata",
                    "missing_locale_source",
                    "high",
                    {"missing": required},
                )
            )
        metadata = self._values(
            f,
            "source_locale",
            "target_locale",
            "source_content_hash",
            "technical_identifiers",
            "safety_notes",
            "applicability",
            "uncertainty_markers",
        )
        translated = self._values(f, "translated_sections")
        sections = [
            self._section(
                "translation_metadata",
                0,
                "assembled" if not required else "blocked_missing_evidence",
                metadata,
                True,
                self._facts(f, *metadata),
            ),
            self._section(
                "translated_sections",
                1,
                "needs_review" if translated else "blocked_missing_evidence",
                translated,
                True,
                self._facts(f, *translated),
            ),
        ]
        if f.get("target_locale", {}).get("value") != item.get("locale"):
            issues.append(
                self._issue(
                    "translation_metadata",
                    "template_input_invalid",
                    "high",
                    {"reason": "target_locale_mismatch"},
                )
            )
        return sections, issues

    def _faq(self, f, t):
        values = self._values(f, "faq_items")
        valid = values and all(
            x.get("question") and x.get("answer") and x.get("evidence")
            for x in values.get("faq_items", [])
        )
        section = self._section(
            "faq_items",
            0,
            "needs_review" if valid else "blocked_missing_evidence",
            values,
            True,
            self._facts(f, *values),
        )
        return [section], [] if valid else [
            self._issue(
                "faq_items",
                "missing_required_fact",
                "high",
                {"reason": "directly_evidenced_faq_required"},
            )
        ]

    def _template(self, item, template_id):
        # A guide can be created as a side effect of resolving a
        # translate_error_code/translate_fault backlog item (apply-integration's
        # create_reviewed_guide targets the item's topic, not a dedicated
        # create_or_enrich_guide item). The originating action_type says
        # nothing about that; the presence of assembled "steps" does.
        if template_id is None and any(f["key"] == "steps" for f in item.get("facts", [])):
            return TEMPLATES["troubleshooting_guide_v1"]
        key = template_id or ACTION_DEFAULT.get(item["action_type"])
        if key not in TEMPLATES:
            raise ValueError("unsupported_content_action_or_template")
        t = TEMPLATES[key]
        if item["action_type"] not in t.actions:
            raise ValueError("template_action_mismatch")
        return t

    @staticmethod
    def _values(f, *keys):
        return {
            k: f[k]["value"]
            for k in keys
            if k in f and f[k].get("value") not in (None, "", [], {})
        }

    @staticmethod
    def _facts(f, *keys):
        return [f[k] for k in keys if k in f]

    def _optional(self, key, pos, values, f):
        return self._section(
            key,
            pos,
            "assembled" if values else "omitted_no_data",
            values,
            False,
            self._facts(f, *values),
        )

    @staticmethod
    def _section(key, pos, status, content, required, facts):
        return {
            "section_key": key,
            "sort_order": pos,
            "section_status": status,
            "content": content,
            "required": required,
            "input_hash": _hash({"key": key, "content": content}),
            "evidence": [e for fact in facts for e in fact.get("evidence", [])],
        }

    @staticmethod
    def _issue(section, kind, severity, details):
        return {
            "section_key": section,
            "issue_type": kind,
            "severity": severity,
            "details": details,
            "status": "open",
        }

    def _risk(self, f, t, issues):
        text = json.dumps(
            {k: v.get("value") for k, v in f.items()}, ensure_ascii=False
        ).casefold()
        hazards = (
            "230 v",
            "mains voltage",
            "live equipment",
            "gas",
            "refrigerant",
            "remove rear panel",
            "dismantle",
            "hot surface",
            "pressurized",
            "sharp",
            "chemical",
            "heavy component",
            "water and electricity",
            "test motor wiring",
        )
        if any(x in text for x in hazards):
            if not any(i["issue_type"] == "safety_review_required" for i in issues):
                issues.append(
                    self._issue(
                        None,
                        "safety_review_required",
                        "safety_review",
                        {"signals": [x for x in hazards if x in text]},
                    )
                )
            return "safety_review"
        return t.safety

    def _draft(self, item, t, status, risk, source_hash, sections, issues, comparison):
        rendered = {
            s["section_key"]: s["content"]
            for s in sections
            if s["section_status"] in {"assembled", "needs_review"}
        }
        identity = [
            item["backlog_id"],
            item["entity_type"],
            item["entity_id"],
            item["locale"],
            t.draft_type,
            t.id,
            t.version,
            source_hash,
            ASSEMBLER_VERSION,
        ]
        return {
            "backlog_item_id": item["backlog_id"],
            "entity_type": item["entity_type"],
            "entity_id": str(item["entity_id"]),
            "locale": item["locale"],
            "draft_type": t.draft_type,
            "template_id": t.id,
            "template_version": t.version,
            "status": status,
            "risk_level": risk,
            "comparison_class": comparison,
            "source_input_hash": source_hash,
            "content_hash": _hash(rendered),
            "rendered_content": rendered,
            "assembler_version": ASSEMBLER_VERSION,
            "validation_state": "validation_failed"
            if status == "blocked"
            else "pending",
            "review_state": "unreviewed",
            "sections": sections,
            "issues": issues,
            "processing_state": "content_draft_blocked"
            if status == "blocked"
            else (
                "content_draft_partial"
                if status == "partial"
                else "needs_content_validation"
            ),
            "identity_hash": _hash(identity),
        }


def _hash(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()
