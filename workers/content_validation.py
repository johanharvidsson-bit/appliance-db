"""Deterministic validation of immutable structured content drafts."""

from __future__ import annotations
from hashlib import sha256
import json
import re

VALIDATOR_VERSION = "1.1.0"
RULESET_ID = "content_validation_v1"
RULESET_VERSION = "1.0.0"
PLACEHOLDERS = (
    "coming soon",
    "guide coming soon",
    "diagnostic title coming soon",
    "description coming soon",
    "tbd",
    "todo",
    "to be added",
    "not yet available",
)
SAFETY_RULES = {
    "mains_electricity": ("230 v", "mains voltage", "line voltage"),
    "energized_testing": ("energized", "live equipment", "test live"),
    "water_and_electricity": ("water and electricity", "wet electrical"),
    "gas": ("gas line", "gas valve"),
    "refrigerant": ("refrigerant", "coolant circuit"),
    "pressure": ("pressurized", "pressure vessel"),
    "hot_surfaces": ("hot surface",),
    "sharp_components": ("sharp edge", "sharp component"),
    "heavy_components": ("heavy component",),
    "chemical_exposure": ("chemical", "solvent"),
    "moving_parts": ("moving part",),
    "disassembly": ("remove rear panel", "dismantle", "disassembly"),
    "fire_risk": ("bypass fuse", "wrong fuse", "fire risk"),
}
FAIL_CODES = {
    "unsupported_claim",
    "conflicted_claim",
    "missing_evidence",
    "broken_evidence_chain",
    "identifier_mismatch",
    "scope_mismatch",
    "locale_mismatch",
    "placeholder_present",
    "empty_required_section",
    "missing_required_fact",
    "missing_required_step",
    "procedure_order_changed",
    "unsupported_safety_instruction",
    "missing_safety_warning",
    "template_schema_invalid",
    "content_hash_mismatch",
    "translation_safety_loss",
}
REVIEW_CODES = {
    "partially_supported_claim",
    "claim_strength_exceeded",
    "stale_translation",
    "translation_information_loss",
    "translation_uncertainty_changed",
    "unexpected_empty_section",
    "duplicate_content",
    "duplicate_procedure",
    "article_guide_procedure_duplication",
    "safety_review_required",
}

RULE_CATALOG = {
    code: {
        "predicate": f"deterministic check emits {code}",
        "severity": "high" if code in FAIL_CODES else "medium",
        "applicable_draft_types": "all unless the validator method narrows scope",
        "effect": "fail" if code in FAIL_CODES else "needs_review",
        "false_positive_risk": "low" if code in FAIL_CODES else "medium",
        "remediation": "create a corrected draft from evidenced upstream input",
    }
    for code in FAIL_CODES | REVIEW_CODES
}
REQUIRED = {
    "model_overview": ("short_summary",),
    "error_code_description": ("title", "meaning"),
    "fault_summary": ("title",),
    "troubleshooting_guide": ("title", "steps"),
    "translation": ("translation_metadata", "translated_sections"),
    "faq_candidate": ("faq_items",),
}


class ValidationEngine:
    def validate(self, draft: dict, context: dict | None = None) -> dict:
        context = context or {}
        issues = []
        checks = []
        safety = []
        duplicates = []
        sections = draft.get("sections", [])
        rendered = draft.get("rendered_content", {})
        section_map = {s["section_key"]: s for s in sections}
        actual_hash = _hash(rendered)
        if actual_hash != draft.get("content_hash"):
            issues.append(
                self._issue(
                    "content_hash_mismatch",
                    "high",
                    None,
                    {"expected": draft.get("content_hash"), "actual": actual_hash},
                )
            )
        for key in REQUIRED.get(draft["draft_type"], ()):
            s = section_map.get(key)
            if (
                not s
                or s.get("section_status") not in {"assembled", "needs_review"}
                or _empty(s.get("content"))
            ):
                issues.append(
                    self._issue(
                        "empty_required_section",
                        "high",
                        s and s.get("id"),
                        {"section": key},
                    )
                )
        for section in sections:
            content = section.get("content")
            sid = section.get("id")
            if section.get("section_status") in {
                "assembled",
                "needs_review",
            } and _empty(content):
                issues.append(
                    self._issue(
                        "unexpected_empty_section",
                        "medium",
                        sid,
                        {"section": section["section_key"]},
                    )
                )
            text = json.dumps(content, ensure_ascii=False).casefold()
            if any(
                re.search(rf"\b{re.escape(p)}\b[\s.!?]*", text, re.I)
                for p in PLACEHOLDERS
            ):
                issues.append(
                    self._issue(
                        "placeholder_present",
                        "high",
                        sid,
                        {"section": section["section_key"]},
                    )
                )
            checks.extend(self._claims(draft, section, issues))
            self._strength(section, text, issues)
        self._identifiers(draft, context, issues)
        self._translation(draft, context, issues)
        self._lost_information(draft, context, issues)
        safety.extend(self._safety(draft, context, issues))
        duplicates.extend(self._duplicates(draft, context, issues))
        if draft.get("status") == "partial":
            issues.append(
                self._issue(
                    "partially_supported_claim",
                    "medium",
                    None,
                    {"reason": "partial_draft"},
                )
            )
        if draft.get("status") == "blocked":
            issues.append(
                self._issue(
                    "template_schema_invalid", "high", None, {"reason": "blocked_draft"}
                )
            )
        effects = [
            RULE_CATALOG.get(i["reason_code"], {"effect": "needs_review"})["effect"]
            for i in issues
        ]
        overall = (
            "fail"
            if "fail" in effects
            else ("needs_review" if "needs_review" in effects or safety else "pass")
        )
        claim_result = _aggregate(
            [c["result"] for c in checks],
            {
                "unsupported": "fail",
                "conflicted": "fail",
                "partially_supported": "needs_review",
            },
        )
        structure_result = _subresult(
            issues,
            {
                "placeholder_present",
                "empty_required_section",
                "unexpected_empty_section",
                "template_schema_invalid",
                "content_hash_mismatch",
            },
        )
        translation_result = (
            "not_applicable"
            if draft["draft_type"] != "translation"
            else _subresult(
                issues,
                {
                    "stale_translation",
                    "translation_information_loss",
                    "translation_uncertainty_changed",
                    "translation_safety_loss",
                    "locale_mismatch",
                    "identifier_mismatch",
                },
            )
        )
        duplication_result = "needs_review" if duplicates else "pass"
        safety_result = (
            "needs_review"
            if safety and overall != "fail"
            else (
                "fail"
                if any(
                    i["reason_code"]
                    in {
                        "missing_safety_warning",
                        "unsupported_safety_instruction",
                        "translation_safety_loss",
                    }
                    for i in issues
                )
                else "pass"
            )
        )
        evidence_hash = _hash(
            [
                {k: e.get(k) for k in sorted(e)}
                for s in sections
                for e in s.get("evidence", [])
            ]
        )
        identity = _hash(
            [
                draft["id"],
                draft.get("content_hash"),
                evidence_hash,
                VALIDATOR_VERSION,
                RULESET_VERSION,
                draft.get("template_version"),
                draft.get("entity_id"),
            ]
        )
        return {
            "content_draft_id": draft["id"],
            "validator_version": VALIDATOR_VERSION,
            "ruleset_id": RULESET_ID,
            "ruleset_version": RULESET_VERSION,
            "input_content_hash": draft.get("content_hash"),
            "evidence_hash": evidence_hash,
            "validation_identity_hash": identity,
            "overall_result": overall,
            "claim_result": claim_result,
            "structure_result": structure_result,
            "translation_result": translation_result,
            "duplication_result": duplication_result,
            "safety_result": safety_result,
            "publication_readiness_result": "ready_for_editorial_review"
            if overall == "pass"
            else ("requires_review" if overall == "needs_review" else "not_ready"),
            "risk_level": "safety_review" if safety else draft.get("risk_level", "low"),
            "claim_checks": checks,
            "safety_findings": safety,
            "duplication_findings": duplicates,
            "issues": issues,
            "summary": {
                "issue_codes": sorted({i["reason_code"] for i in issues}),
                "draft_content_unchanged": True,
            },
            "draft_validation_state": {
                "pass": "validation_passed",
                "needs_review": "validation_needs_review",
                "fail": "validation_failed",
            }[overall],
            "backlog_validation_state": {
                "pass": "content_validation_passed",
                "needs_review": "content_validation_needs_review",
                "fail": "content_validation_failed",
            }[overall],
        }

    def _claims(self, draft, section, issues):
        checks = []
        evidence = section.get("evidence", [])
        sid = section.get("id")
        for key, value in _leaves(section.get("content"), section["section_key"]):
            factual = not key.endswith((".heading", ".label"))
            result = "not_a_factual_claim" if not factual else "supported"
            reason = "not_factual"
            valid = [
                e
                for e in evidence
                if e.get("source_evidence_id")
                or (e.get("candidate_fact_id") and e.get("source_document_id"))
            ]
            if factual and not valid:
                result = "unsupported"
                reason = "missing_evidence"
                issues.append(
                    self._issue("missing_evidence", "high", sid, {"claim": key})
                )
            elif factual and any(e.get("conflicted") for e in valid):
                result = "conflicted"
                reason = "conflicted_claim"
                issues.append(
                    self._issue("conflicted_claim", "high", sid, {"claim": key})
                )
            elif factual and any(
                e.get("entity_id") not in (None, str(draft.get("entity_id")))
                for e in valid
            ):
                result = "unsupported"
                reason = "broken_evidence_chain"
                issues.append(
                    self._issue("broken_evidence_chain", "high", sid, {"claim": key})
                )
            else:
                reason = "evidence_chain_present"
            checks.append(
                {
                    "content_draft_section_id": sid,
                    "claim_key": key,
                    "claim_text_hash": _hash(value),
                    "claim_type": "factual" if factual else "formatting",
                    "result": result,
                    "supporting_evidence_count": len(valid),
                    "reason_code": reason,
                    "details": {"value_hash": _hash(value)},
                }
            )
        return checks

    def _strength(self, section, text, issues):
        sid = section.get("id")
        evidence_text = " ".join(
            str(e.get("source_text", "")).casefold()
            for e in section.get("evidence", [])
        )
        strong = (
            "always",
            "definitely",
            "will ",
            "must ",
            "common",
            "typical",
            "compatible",
            "safe",
            "official",
            "recommended",
        )
        if any(x in text for x in strong) and not any(
            x in evidence_text for x in strong
        ):
            issues.append(
                self._issue(
                    "claim_strength_exceeded",
                    "medium",
                    sid,
                    {"signals": [x for x in strong if x in text]},
                )
            )
        if any(
            x in evidence_text for x in ("may", "can", "possible", "likely")
        ) and any(x in text for x in ("will ", "definitely", "always")):
            issues.append(
                self._issue(
                    "claim_strength_exceeded",
                    "medium",
                    sid,
                    {"reason": "uncertainty_strengthened"},
                )
            )

    def _identifiers(self, draft, context, issues):
        text = json.dumps(draft.get("rendered_content", {}), ensure_ascii=False)
        for identifier in context.get("required_identifiers", []):
            if identifier not in text:
                issues.append(
                    self._issue(
                        "identifier_mismatch",
                        "high",
                        None,
                        {"missing_identifier": identifier},
                    )
                )
        for wrong in context.get("forbidden_identifiers", []):
            if wrong in text:
                issues.append(
                    self._issue(
                        "identifier_mismatch", "high", None, {"wrong_identifier": wrong}
                    )
                )
        if (
            context.get("expected_locale")
            and draft.get("locale") != context["expected_locale"]
        ):
            issues.append(
                self._issue(
                    "locale_mismatch",
                    "high",
                    None,
                    {
                        "expected": context["expected_locale"],
                        "actual": draft.get("locale"),
                    },
                )
            )

    def _translation(self, draft, context, issues):
        if draft["draft_type"] != "translation":
            return
        metadata = draft.get("rendered_content", {}).get("translation_metadata", {})
        if (
            context.get("current_source_hash")
            and metadata.get("source_content_hash") != context["current_source_hash"]
        ):
            issues.append(
                self._issue(
                    "stale_translation",
                    "medium",
                    None,
                    {
                        "expected": context["current_source_hash"],
                        "actual": metadata.get("source_content_hash"),
                    },
                )
            )
        translated = json.dumps(
            draft.get("rendered_content", {}).get("translated_sections", {}),
            ensure_ascii=False,
        ).casefold()
        for warning in context.get("required_safety_phrases", []):
            if warning.casefold() not in translated:
                issues.append(
                    self._issue(
                        "translation_safety_loss", "high", None, {"missing": warning}
                    )
                )
        for marker in context.get("required_uncertainty_markers", []):
            if marker.casefold() not in translated:
                issues.append(
                    self._issue(
                        "translation_uncertainty_changed",
                        "medium",
                        None,
                        {"missing": marker},
                    )
                )

    def _lost_information(self, draft, context, issues):
        text = json.dumps(
            draft.get("rendered_content", {}), ensure_ascii=False
        ).casefold()
        for phrase in context.get("required_information", []):
            if phrase.casefold() not in text:
                code = (
                    "missing_safety_warning"
                    if phrase in context.get("required_safety_phrases", [])
                    else "partially_supported_claim"
                )
                issues.append(
                    self._issue(
                        code,
                        "high" if code == "missing_safety_warning" else "medium",
                        None,
                        {"missing": phrase},
                    )
                )
        expected = context.get("expected_step_order", [])
        actual = _steps(draft)
        if expected and actual != expected:
            issues.append(
                self._issue(
                    "procedure_order_changed",
                    "high",
                    None,
                    {"expected": expected, "actual": actual},
                )
            )

    def _safety(self, draft, context, issues):
        text = json.dumps(
            draft.get("rendered_content", {}), ensure_ascii=False
        ).casefold()
        findings = []
        for kind, signals in SAFETY_RULES.items():
            found = [x for x in signals if x in text]
            if found:
                findings.append(
                    {
                        "content_draft_section_id": None,
                        "safety_type": kind,
                        "severity": "safety_review"
                        if kind
                        in {
                            "mains_electricity",
                            "energized_testing",
                            "water_and_electricity",
                            "gas",
                            "refrigerant",
                            "pressure",
                            "disassembly",
                            "fire_risk",
                        }
                        else "medium",
                        "review_required": True,
                        "details": {"signals": found},
                    }
                )
        if findings:
            issues.append(
                self._issue(
                    "safety_review_required",
                    "safety_review",
                    None,
                    {"categories": [x["safety_type"] for x in findings]},
                )
            )
        if any(
            x in text for x in ("bypass safety", "bypass fuse", "work while energized")
        ):
            issues.append(
                self._issue("unsupported_safety_instruction", "high", None, {})
            )
        return findings

    def _duplicates(self, draft, context, issues):
        findings = []
        content_hash = draft.get("content_hash")
        procedure = _hash(_steps(draft)) if _steps(draft) else None
        for other in context.get("existing_drafts", []):
            if other.get("id") == draft.get("id"):
                continue
            match = None
            if other.get("content_hash") == content_hash:
                match = "exact_duplicate"
            elif procedure and other.get("procedure_hash") == procedure:
                match = "procedure_duplicate"
            elif other.get("normalized_hash") == _hash(
                _normalize_content(draft.get("rendered_content", {}))
            ):
                match = "identifier_substitution_duplicate"
            if match:
                severity = (
                    "high"
                    if draft["draft_type"]
                    in {"error_code_description", "fault_summary"}
                    and match == "procedure_duplicate"
                    else "medium"
                )
                findings.append(
                    {
                        "content_draft_section_id": None,
                        "matched_entity_type": other.get("entity_type"),
                        "matched_entity_id": str(other.get("entity_id")),
                        "match_type": match,
                        "similarity_value": 1.0,
                        "severity": severity,
                        "details": {"matched_draft_id": other.get("id")},
                    }
                )
                issues.append(
                    self._issue(
                        "article_guide_procedure_duplication"
                        if severity == "high"
                        else (
                            "duplicate_procedure"
                            if match == "procedure_duplicate"
                            else "duplicate_content"
                        ),
                        severity,
                        None,
                        {"matched_draft_id": other.get("id")},
                    )
                )
        return findings

    @staticmethod
    def _issue(code, severity, section_id, details):
        return {
            "reason_code": code,
            "severity": severity,
            "content_draft_section_id": section_id,
            "details": details,
        }


def _leaves(value, path):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _leaves(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _leaves(v, f"{path}[{i}]")
    elif value is not None:
        yield path, value


def _empty(v):
    return (
        v is None
        or v == ""
        or v == []
        or v == {}
        or (isinstance(v, dict) and all(_empty(x) for x in v.values()))
    )


def _steps(d):
    raw = d.get("rendered_content", {}).get("steps", {})
    rows = raw.get("steps", raw if isinstance(raw, list) else [])
    return [x.get("instruction") if isinstance(x, dict) else str(x) for x in rows]


def _normalize_content(v):
    return re.sub(
        r"[A-Z0-9/\-]+",
        "<ID>",
        json.dumps(v, sort_keys=True, ensure_ascii=False).upper(),
    )


def _aggregate(values, priority):
    if not values:
        return "pass"
    effects = [priority.get(v, "pass") for v in values]
    return (
        "fail"
        if "fail" in effects
        else ("needs_review" if "needs_review" in effects else "pass")
    )


def _subresult(issues, codes):
    selected = [i for i in issues if i["reason_code"] in codes]
    effects = [
        RULE_CATALOG.get(i["reason_code"], {"effect": "needs_review"})["effect"]
        for i in selected
    ]
    return "fail" if "fail" in effects else ("needs_review" if effects else "pass")


def _hash(v):
    return sha256(
        json.dumps(
            v, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()
