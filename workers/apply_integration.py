"""Strict, deterministic application of manually approved proposals."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

PLACEHOLDERS = frozenset(
    {
        "coming soon",
        "guide coming soon",
        "diagnostic title coming soon",
        "description coming soon",
        "to be added",
        "tbd",
        "todo",
        "not yet available",
    }
)
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "safety_review": 3}


@dataclass(frozen=True)
class Operation:
    name: str
    table: str
    risk: str
    evidence_required: bool = True


APPLY_OPERATIONS = {
    "propose_model_spec_update": Operation(
        "upsert_model_spec_field", "model_specs", "low"
    ),
    "propose_model_overview_update": Operation(
        "update_model_content_field", "model_content_translations", "low"
    ),
    "propose_error_code_description": Operation(
        "update_error_code_content", "error_code_translations", "low"
    ),
    "propose_error_code_translation": Operation(
        "update_error_code_content", "error_code_translations", "low"
    ),
    "propose_fault_translation": Operation(
        "upsert_draft_fault_translation", "fault_translations", "low"
    ),
    "propose_variant_mapping": Operation(
        "create_candidate_model_variant", "model_variants", "medium"
    ),
}


def is_placeholder(value):
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[\s.!?:;,\-–—]+$", "", " ".join(value.split()).casefold())
    return normalized in PLACEHOLDERS


def contains_invalid_text(value):
    if isinstance(value, str):
        return not value.strip() or is_placeholder(value)
    if isinstance(value, dict):
        return any(
            contains_invalid_text(v)
            for k, v in value.items()
            if k
            in {
                "value",
                "source_value",
                "overview",
                "title",
                "description",
                "symptom_name",
                "short_summary",
                "meta_description",
            }
        )
    return False


def stable_hash(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


class ApplyBlocked(Exception):
    def __init__(self, code, message=None):
        self.code, self.message = code, message or code


class StaleProposal(ApplyBlocked):
    pass


class ApplyEngine:
    def __init__(self, repository):
        self.repository = repository

    def plan(self, proposal, *, max_risk="medium", retry_failed=False):
        if proposal.get("status") != "approved":
            raise ApplyBlocked("status_not_approved")
        for field in (
            "reviewed_at",
            "reviewed_by",
            "risk_level",
            "expected_apply_operation",
            "proposed_value_json",
        ):
            if proposal.get(field) is None or proposal.get(field) == "":
                raise ApplyBlocked(f"missing_{field}")
        if "current_value_json" not in proposal:
            raise ApplyBlocked("missing_current_value_json")
        operation = APPLY_OPERATIONS.get(proposal.get("proposal_type"))
        if not operation:
            raise ApplyBlocked("unsupported_apply_operation")
        if proposal["expected_apply_operation"] != operation.name:
            raise ApplyBlocked("operation_contract_mismatch")
        if proposal["risk_level"] not in RISK_ORDER or max_risk not in RISK_ORDER:
            raise ApplyBlocked("unknown_risk_level")
        if RISK_ORDER[proposal["risk_level"]] < RISK_ORDER[operation.risk]:
            raise ApplyBlocked("risk_underclassified")
        if RISK_ORDER[proposal["risk_level"]] > RISK_ORDER[max_risk] or proposal[
            "risk_level"
        ] in {"high", "safety_review"}:
            raise ApplyBlocked("risk_policy_blocked")
        if proposal.get("blocking_conflicts", 0):
            raise ApplyBlocked("unresolved_blocking_conflict")
        if operation.evidence_required and not proposal.get("evidence"):
            raise ApplyBlocked("apply_blocked_missing_evidence")
        if contains_invalid_text(proposal["proposed_value_json"]):
            raise ApplyBlocked("placeholder_or_empty_content")
        if proposal.get("successful_attempt"):
            return {
                "idempotent": True,
                "proposal_id": proposal["id"],
                "operation": operation.name,
            }
        if not proposal.get("preferred_target"):
            raise ApplyBlocked("missing_unique_target")
        target = proposal["preferred_target"]
        if target.get("target_entity_type") != proposal.get("entity_type") or str(
            target.get("target_entity_id")
        ) != str(proposal.get("entity_id")):
            raise ApplyBlocked("target_identity_mismatch")
        return {
            "idempotent": False,
            "proposal_id": proposal["id"],
            "proposal_type": proposal["proposal_type"],
            "operation": operation.name,
            "table": operation.table,
            "target": target,
            "locale": proposal.get("locale"),
            "current": proposal["current_value_json"],
            "proposed": proposal["proposed_value_json"],
            "input_hash": proposal["input_hash"],
        }

    def apply(
        self,
        proposal_id,
        *,
        applied_by,
        max_risk="medium",
        dry_run=False,
        retry_failed=False,
    ):
        with self.repository.proposal_transaction(proposal_id) as proposal:
            plan = self.plan(proposal, max_risk=max_risk, retry_failed=retry_failed)
            if dry_run or plan["idempotent"]:
                return {
                    "status": "dry_run" if dry_run else "succeeded",
                    "plan": plan,
                    "changed": False,
                }
            self.repository.validate_target(plan)
            current = self.repository.read_current(plan)
            if current != plan["current"]:
                raise StaleProposal("stale_proposal")
            attempt_id = self.repository.start_attempt(proposal, plan, applied_by)
            before = current
            after = self.repository.mutate(plan)
            verified = self.repository.read_current(plan)
            if verified != after:
                raise ApplyBlocked("verification_failed")
            change = {
                "entity_type": proposal["entity_type"],
                "entity_id": proposal.get("entity_id"),
                "table_name": plan["table"],
                "operation": plan["operation"],
                "key": plan["target"] or {},
                "before": before,
                "after": after,
            }
            change["change_hash"] = stable_hash(change)
            change["rollback_payload"] = {
                "expected_current": after,
                "restore": before,
                "operation": plan["operation"],
            }
            self.repository.record_change(attempt_id, change)
            self.repository.finish_attempt(attempt_id, "succeeded")
            return {
                "status": "succeeded",
                "attempt_id": attempt_id,
                "change": change,
                "changed": True,
            }
