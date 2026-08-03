"""Deterministic, proposal-only knowledge integration (PR 2C)."""

from __future__ import annotations

from hashlib import sha256
import json
import re
from difflib import SequenceMatcher

DETECTOR_NAME = "repairbase_deterministic_resolver"
DETECTOR_VERSION = "1.0.0"


def normalize_identifier(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def normalize_text(value: object) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(value).casefold()).split())


class ResolutionEngine:
    def resolve(
        self, fact: dict, catalog: dict, proposal_filter: str | None = None
    ) -> dict:
        if fact["extraction_status"] == "rejected":
            return self._result(fact, "rejected", [])
        if fact.get("out_of_scope"):
            proposal = self._proposal(
                fact,
                "propose_source_evidence",
                "scope",
                None,
                "blocked",
                0,
                "high",
                "out_of_scope",
                [],
                {"fact": fact["value"]},
                "manual_scope_review",
                conflicts=[
                    self._conflict(
                        "scope_mismatch", "high", {"scope": fact.get("scope")}
                    )
                ],
            )
            return self._result(
                fact, "out_of_scope", self._filter([proposal], proposal_filter)
            )
        resolver = {
            "specification": self._model_content,
            "overview": self._model_content,
            "identity": self._identity,
            "error_code": self._error_code,
            "fault": self._fault,
            "guide_step": self._guide,
            "guide": self._guide,
        }.get(fact["fact_type"], self._evidence_only)
        proposals = resolver(fact, catalog)
        if fact["extraction_status"] in {"needs_review", "conflicted"}:
            for proposal in proposals:
                proposal["status"] = (
                    "blocked"
                    if fact["extraction_status"] == "conflicted"
                    else "needs_review"
                )
                if fact["extraction_status"] == "conflicted":
                    proposal["conflicts"].append(
                        self._conflict(
                            "source_fact_conflict",
                            "high",
                            fact.get("conflict_metadata", {}),
                        )
                    )
                    proposal["risk_level"] = "high"
        proposals = self._filter(proposals, proposal_filter)
        state = (
            "blocked_by_conflict"
            if any(x["status"] == "blocked" for x in proposals)
            else (
                "needs_review"
                if any(x["status"] == "needs_review" for x in proposals)
                else (
                    "integration_proposal_created" if proposals else "same_as_existing"
                )
            )
        )
        return self._result(fact, state, proposals)

    def _identity(self, fact, catalog):
        predicate = fact["predicate"]
        if predicate == "model_code":
            return self._model_match_proposal(fact, catalog)
        if predicate == "variant_code":
            return self._variant_proposal(fact, catalog)
        if predicate == "product_code":
            return self._product_code_proposal(fact, catalog)
        return self._evidence_only(fact, catalog)

    def _models(self, fact, catalog, value=None):
        brand, category = fact.get("brand_id"), fact.get("category_id")
        models = catalog.get("models", [])
        scoped = [
            m
            for m in models
            if (brand is None or m.get("brand_id") == brand)
            and (category is None or m.get("category_id") == category)
        ]
        if (
            fact.get("backlog_entity_type") == "model"
            and str(fact.get("backlog_entity_id", "")).isdigit()
        ):
            exact_id = [
                m for m in scoped if str(m["id"]) == str(fact["backlog_entity_id"])
            ]
            if exact_id:
                return [
                    (
                        exact_id[0],
                        "exact",
                        100,
                        ["backlog_model_id", "brand_scope", "category_scope"],
                    )
                ]
        needle = normalize_identifier(
            value if value is not None else fact.get("subject_hint", "")
        )
        matches = []
        for model in scoped:
            identifiers = {
                normalize_identifier(model.get(k, ""))
                for k in ("name", "slug", "base_model", "model_code")
            }
            if needle and needle in identifiers:
                matches.append(
                    (
                        model,
                        "normalized_exact",
                        95,
                        ["normalized_identifier", "brand_scope", "category_scope"],
                    )
                )
        if matches:
            return matches
        aliases = [
            a
            for a in catalog.get("model_aliases", [])
            if a.get("status", "verified") == "verified"
            and normalize_identifier(a.get("alias")) == needle
        ]
        for alias in aliases:
            model = next((m for m in scoped if m["id"] == alias["model_id"]), None)
            if model:
                matches.append(
                    (
                        model,
                        "alias",
                        85,
                        ["verified_alias", "brand_scope", "category_scope"],
                    )
                )
        return matches

    def _model_match_proposal(self, fact, catalog):
        matches = self._models(fact, catalog, fact["value"])
        if not matches:
            needle = normalize_identifier(fact["value"])
            wrong_scope = [
                m
                for m in catalog.get("models", [])
                if needle
                in {
                    normalize_identifier(m.get(k, ""))
                    for k in ("name", "slug", "base_model", "model_code")
                }
            ]
            if wrong_scope:
                proposal = self._unresolved(fact, "match_existing_model", "model")
                proposal["difference_class"] = "out_of_scope"
                proposal["conflicts"].append(
                    self._conflict(
                        "brand_category_scope_mismatch",
                        "high",
                        {"candidate_ids": [x["id"] for x in wrong_scope]},
                    )
                )
                return [proposal]
            return [self._unresolved(fact, "match_existing_model", "model")]
        status = "proposed" if len(matches) == 1 else "blocked"
        targets = self._targets(matches, preferred=len(matches) == 1)
        conflicts = (
            []
            if len(matches) == 1
            else [
                self._conflict(
                    "multiple_model_targets",
                    "high",
                    {"target_ids": [m[0]["id"] for m in matches]},
                )
            ]
        )
        return [
            self._proposal(
                fact,
                "match_existing_model",
                "model",
                str(matches[0][0]["id"]) if len(matches) == 1 else None,
                status,
                matches[0][2] if len(matches) == 1 else 50,
                "low" if len(matches) == 1 else "high",
                "new_information",
                targets,
                {"identifier": fact["value"]},
                "bind_candidate_to_existing_model",
                conflicts=conflicts,
            )
        ]

    def _model_content(self, fact, catalog):
        matches = self._models(fact, catalog)
        if len(matches) != 1:
            ptype = (
                "propose_model_spec_update"
                if fact["fact_type"] == "specification"
                else "propose_model_overview_update"
            )
            return [
                self._unresolved(
                    fact, ptype, "model", multiple=bool(matches), matches=matches
                )
            ]
        model, match_type, score, components = matches[0]
        if fact["fact_type"] == "specification":
            current = (
                catalog.get("model_specs", {})
                .get(str(model["id"]), {})
                .get(fact["predicate"])
            )
            proposed = {
                "field": fact["predicate"],
                "value": fact["value"],
                "unit": fact.get("unit"),
            }
            ptype = "propose_model_spec_update"
            operation = "upsert_model_spec_field"
        else:
            current = catalog.get("model_overviews", {}).get(
                f"{model['id']}:{fact.get('locale')}"
            )
            proposed = {"field": fact["predicate"], "source_value": fact["value"]}
            ptype = "propose_model_overview_update"
            operation = "update_model_content_field"
        comparison = self._compare(current, fact["value"])
        if comparison == "same_as_existing":
            return []
        status = (
            "blocked"
            if comparison == "conflicts_with_existing"
            else ("proposed" if score >= 95 else "needs_review")
        )
        conflicts = (
            []
            if status != "blocked"
            else [
                self._conflict(
                    "existing_value_conflict",
                    "high",
                    {"current": current, "proposed": fact["value"]},
                )
            ]
        )
        return [
            self._proposal(
                fact,
                ptype,
                "model",
                str(model["id"]),
                status,
                score,
                "high"
                if conflicts
                else ("medium" if ptype.endswith("overview_update") else "low"),
                comparison,
                self._targets(matches, True),
                proposed,
                operation,
                current=current,
                components=components,
                conflicts=conflicts,
            )
        ]

    def _variant_proposal(self, fact, catalog):
        needle = normalize_identifier(fact["value"])
        model_matches = self._models(fact, catalog, needle.split("EU")[0])
        variants = []
        for variant in catalog.get("variants", []):
            if normalize_identifier(variant.get("variant_code")) == needle:
                if model_matches and variant["model_id"] not in {
                    m[0]["id"] for m in model_matches
                }:
                    continue
                verified = variant.get("status", "verified") == "verified"
                variants.append(
                    (
                        variant,
                        "variant_code" if verified else "candidate",
                        95 if verified else 70,
                        [
                            "normalized_variant_code",
                            "model_scope",
                            "verified_variant" if verified else "candidate_variant",
                        ],
                    )
                )
        if len(variants) == 1:
            return [
                self._proposal(
                    fact,
                    "match_existing_variant",
                    "model_variant",
                    str(variants[0][0]["id"]),
                    "proposed" if variants[0][1] == "variant_code" else "needs_review",
                    variants[0][2],
                    "low" if variants[0][1] == "variant_code" else "medium",
                    "new_information",
                    self._targets(variants, True),
                    {"variant_code": fact["value"]},
                    "bind_candidate_to_existing_variant",
                )
            ]
        if len(variants) > 1:
            return [
                self._unresolved(
                    fact,
                    "match_existing_variant",
                    "model_variant",
                    multiple=True,
                    matches=variants,
                )
            ]
        target = self._targets(model_matches, len(model_matches) == 1)
        return [
            self._proposal(
                fact,
                "propose_variant_mapping",
                "model",
                str(model_matches[0][0]["id"]) if len(model_matches) == 1 else None,
                "needs_review" if len(model_matches) == 1 else "blocked",
                80 if len(model_matches) == 1 else 30,
                "medium",
                "relation_gap" if model_matches else "insufficient_evidence",
                target,
                {"variant_code": fact["value"]},
                "create_reviewed_model_variant_mapping",
                conflicts=[]
                if len(model_matches) == 1
                else [self._conflict("no_unique_main_model", "high", {})],
            )
        ]

    def _product_code_proposal(self, fact, catalog):
        needle = normalize_identifier(fact["value"])
        matches = [
            (p, "product_code", 100, ["exact_product_code"])
            for p in catalog.get("product_codes", [])
            if normalize_identifier(p.get("code")) == needle
        ]
        if len(matches) == 1:
            p = matches[0][0]
            model_hint = self._models(fact, catalog)
            mismatch = model_hint and p["model_id"] not in {
                x[0]["id"] for x in model_hint
            }
            return [
                self._proposal(
                    fact,
                    "match_existing_product_code",
                    "product_code",
                    str(p["id"]),
                    "blocked" if mismatch else "proposed",
                    100,
                    "high" if mismatch else "low",
                    "conflicts_with_existing" if mismatch else "new_information",
                    self._targets(matches, not mismatch),
                    {"code": fact["value"]},
                    "bind_candidate_to_existing_product_code",
                    conflicts=[
                        self._conflict(
                            "product_code_model_mismatch",
                            "high",
                            {"existing_model_id": p["model_id"]},
                        )
                    ]
                    if mismatch
                    else [],
                )
            ]
        if len(matches) > 1:
            return [
                self._unresolved(
                    fact,
                    "match_existing_product_code",
                    "product_code",
                    multiple=True,
                    matches=matches,
                )
            ]
        models = self._models(fact, catalog)
        return [
            self._proposal(
                fact,
                "propose_product_code_mapping",
                "model",
                str(models[0][0]["id"]) if len(models) == 1 else None,
                "needs_review" if len(models) == 1 else "blocked",
                80 if len(models) == 1 else 30,
                "medium",
                "relation_gap",
                self._targets(models, len(models) == 1),
                {"product_code": fact["value"]},
                "create_reviewed_product_code_mapping",
            )
        ]

    def _error_code(self, fact, catalog):
        value = (
            fact["value"]
            if isinstance(fact["value"], dict)
            else {"code": fact["value"]}
        )
        code = normalize_identifier(value.get("code", ""))
        matches = []
        for ec in catalog.get("error_codes", []):
            if (
                normalize_identifier(ec.get("code")) == code
                and ec.get("brand_id") == fact.get("brand_id")
                and ec.get("category_id") == fact.get("category_id")
            ):
                matches.append(
                    (
                        ec,
                        "normalized_exact",
                        98,
                        ["error_code", "brand_scope", "category_scope"],
                    )
                )
        if len(matches) != 1:
            wrong_scope = [
                ec
                for ec in catalog.get("error_codes", [])
                if normalize_identifier(ec.get("code")) == code
            ]
            if not matches and wrong_scope:
                proposal = self._unresolved(
                    fact, "match_existing_error_code", "error_code"
                )
                proposal["difference_class"] = "out_of_scope"
                proposal["conflicts"].append(
                    self._conflict(
                        "brand_category_scope_mismatch",
                        "high",
                        {"candidate_ids": [x["id"] for x in wrong_scope]},
                    )
                )
                return [proposal]
            return [
                self._unresolved(
                    fact,
                    "match_existing_error_code",
                    "error_code",
                    multiple=bool(matches),
                    matches=matches,
                )
            ]
        ec = matches[0][0]
        meaning = value.get("meaning")
        if not meaning:
            return [
                self._proposal(
                    fact,
                    "match_existing_error_code",
                    "error_code",
                    str(ec["id"]),
                    "proposed",
                    98,
                    "low",
                    "new_information",
                    self._targets(matches, True),
                    {"code": value.get("code")},
                    "bind_candidate_to_existing_error_code",
                )
            ]
        current = ec.get("description") or ec.get("short_description")
        comparison = self._compare(current, meaning)
        if comparison == "same_as_existing":
            return []
        ptype = (
            "propose_error_code_translation"
            if fact.get("locale")
            and fact.get("locale") != catalog.get("default_locale", "en")
            else "propose_error_code_description"
        )
        status = "blocked" if comparison == "conflicts_with_existing" else "proposed"
        return [
            self._proposal(
                fact,
                ptype,
                "error_code",
                str(ec["id"]),
                status,
                98,
                "high" if status == "blocked" else "low",
                comparison,
                self._targets(matches, True),
                {"field": "description", "value": meaning},
                "update_error_code_content",
                current=current,
                conflicts=[
                    self._conflict(
                        "error_code_meaning_conflict",
                        "high",
                        {"current": current, "proposed": meaning},
                    )
                ]
                if status == "blocked"
                else [],
            )
        ]

    def _fault(self, fact, catalog):
        text = (
            fact["value"].get("symptom", "")
            if isinstance(fact["value"], dict)
            else str(fact["value"])
        )
        scoped = [
            f
            for f in catalog.get("faults", [])
            if f.get("brand_id") == fact.get("brand_id")
            and f.get("category_id") == fact.get("category_id")
        ]
        exact = [
            (f, "normalized_exact", 95, ["fault_name", "brand_scope", "category_scope"])
            for f in scoped
            if normalize_text(f.get("canonical_name")) == normalize_text(text)
        ]
        if exact:
            return [
                self._proposal(
                    fact,
                    "match_existing_fault",
                    "fault",
                    str(exact[0][0]["id"]),
                    "proposed",
                    95,
                    "low",
                    "new_information",
                    self._targets(exact, True),
                    {"symptom": text},
                    "bind_candidate_to_existing_fault",
                )
            ]
        fuzzy = sorted(
            (
                (
                    f,
                    SequenceMatcher(
                        None,
                        normalize_text(text),
                        normalize_text(f.get("canonical_name")),
                    ).ratio(),
                )
                for f in scoped
            ),
            key=lambda x: x[1],
            reverse=True,
        )
        targets = [
            (
                x[0],
                "contextual",
                round(x[1] * 100),
                ["fuzzy_symptom", "brand_scope", "category_scope"],
            )
            for x in fuzzy[:3]
            if x[1] >= 0.55
        ]
        wrong_scope = [
            f
            for f in catalog.get("faults", [])
            if normalize_text(f.get("canonical_name")) == normalize_text(text)
            and f not in scoped
        ]
        conflicts = (
            [
                self._conflict(
                    "brand_category_scope_mismatch",
                    "high",
                    {"candidate_ids": [x["id"] for x in wrong_scope]},
                )
            ]
            if wrong_scope
            else []
        )
        return [
            self._proposal(
                fact,
                "match_existing_fault",
                "fault",
                None,
                "needs_review" if targets else "blocked",
                targets[0][2] if targets else 20,
                "high" if conflicts else "medium",
                "out_of_scope" if conflicts else "insufficient_evidence",
                self._targets(targets, False),
                {"symptom": text},
                "review_fault_match",
                conflicts=conflicts,
            )
        ]

    def _guide(self, fact, catalog):
        value = (
            fact["value"]
            if isinstance(fact["value"], dict)
            else {"instruction": fact["value"]}
        )
        procedure_hash = value.get("procedure_hash")
        matches = [
            (g, "exact", 98, ["procedure_hash", "brand_scope", "category_scope"])
            for g in catalog.get("guides", [])
            if procedure_hash
            and g.get("steps_hash") == procedure_hash
            and (g.get("brand_id") in {None, fact.get("brand_id")})
            and g.get("category_id") == fact.get("category_id")
        ]
        if len(matches) == 1:
            return [
                self._proposal(
                    fact,
                    "match_existing_guide",
                    "guide",
                    str(matches[0][0]["id"]),
                    "proposed",
                    98,
                    "medium",
                    "new_information",
                    self._targets(matches, True),
                    value,
                    "bind_candidate_to_existing_guide",
                )
            ]
        safety = any(
            x in normalize_text(value)
            for x in (
                "electric",
                "voltage",
                "gas",
                "refrigerant",
                "dismantle",
                "disconnect power",
            )
        )
        return [
            self._proposal(
                fact,
                "propose_new_guide_candidate",
                "guide",
                None,
                "needs_review",
                70,
                "safety_review" if safety else "medium",
                "new_information",
                [],
                value,
                "create_reviewed_guide",
                conflicts=[self._conflict("multiple_guide_procedures", "high", {})]
                if len(matches) > 1
                else [],
            )
        ]

    def _evidence_only(self, fact, _catalog):
        return [
            self._proposal(
                fact,
                "propose_source_evidence",
                fact.get("backlog_entity_type", "unknown"),
                fact.get("backlog_entity_id"),
                "needs_review",
                fact.get("confidence", 50),
                "low",
                "new_information",
                [],
                {"fact": fact["value"]},
                "attach_source_evidence",
            )
        ]

    def _unresolved(self, fact, ptype, entity_type, multiple=False, matches=None):
        conflicts = (
            [
                self._conflict(
                    "multiple_targets",
                    "high",
                    {"target_ids": [x[0]["id"] for x in matches or []]},
                )
            ]
            if multiple
            else []
        )
        return self._proposal(
            fact,
            ptype,
            entity_type,
            None,
            "blocked",
            40 if multiple else 20,
            "high" if multiple else "medium",
            "insufficient_evidence",
            self._targets(matches or [], False),
            {"fact": fact["value"]},
            "manual_resolution",
            conflicts=conflicts,
        )

    @staticmethod
    def _compare(current, proposed):
        if current is None or current == "":
            return "fills_missing_value"
        if normalize_text(current) == normalize_text(proposed):
            return "same_as_existing"
        return "conflicts_with_existing"

    @staticmethod
    def _targets(matches, preferred):
        return [
            {
                "target_entity_type": _entity_type(x[0]),
                "target_entity_id": str(x[0]["id"]),
                "match_type": x[1],
                "match_score": x[2],
                "is_preferred": preferred and i == 0,
                "reason": {"score_components": x[3]},
            }
            for i, x in enumerate(matches)
        ]

    def _proposal(
        self,
        fact,
        ptype,
        entity_type,
        entity_id,
        status,
        confidence,
        risk,
        difference,
        targets,
        proposed,
        operation,
        current=None,
        components=None,
        conflicts=None,
    ):
        components = components or sorted(
            {c for t in targets for c in t["reason"]["score_components"]}
        )
        identity = [
            fact["id"],
            ptype,
            entity_type,
            entity_id,
            proposed,
            DETECTOR_VERSION,
        ]
        return {
            "candidate_fact_id": fact["id"],
            "backlog_item_id": fact["backlog_item_id"],
            "proposal_type": ptype,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "locale": fact.get("locale"),
            "status": status,
            "confidence": confidence,
            "risk_level": risk,
            "difference_class": difference,
            "reason": {
                "score_components": components,
                "source_extraction_status": fact["extraction_status"],
            },
            "current_value": current,
            "proposed_value": proposed,
            "expected_apply_operation": operation,
            "input_hash": sha256(
                json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest(),
            "targets": targets,
            "evidence": fact.get("evidence", []),
            "conflicts": conflicts or [],
        }

    @staticmethod
    def _conflict(kind, severity, details):
        return {
            "conflict_type": kind,
            "severity": severity,
            "details": details,
            "status": "open",
        }

    @staticmethod
    def _filter(proposals, ptype):
        return [x for x in proposals if not ptype or x["proposal_type"] == ptype]

    @staticmethod
    def _result(fact, state, proposals):
        return {
            "candidate_fact_id": fact["id"],
            "backlog_item_id": fact["backlog_item_id"],
            "processing_state": state,
            "proposals": proposals,
        }


def _entity_type(row):
    if "variant_code" in row:
        return "model_variant"
    if "code" in row and "model_id" in row:
        return "product_code"
    if "code" in row and "brand_id" in row:
        return "error_code"
    if "canonical_name" in row:
        return "fault"
    if "canonical_title" in row or "steps_hash" in row:
        return "guide"
    return "model"
