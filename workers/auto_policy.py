"""Deterministic auto-accept / auto-approve policy.

This project has no editorial team; a human clicking through every source
candidate and every integration proposal one at a time does not scale and is
not required for this site. Errors are corrected after the fact rather than
prevented by manual pre-review.

The one gate this policy does NOT remove is the existing hard block on
`high` / `safety_review` risk in `apply_repository.py` (electrical, gas,
refrigerant, dismantling, or otherwise hazardous procedures) - that block is
structural (apply-integration refuses those regardless of proposal status)
and is left in place unchanged. This module only decides whether a
`low`/`medium` risk item still has to wait for a human, or can proceed
immediately.
"""
from __future__ import annotations

AUTO_POLICY_REVIEWER = "auto-policy-v1"

# Source candidates: never auto-accept a forum result or a low-tier "other"
# match - both are documented as candidate-only, low-reliability tiers. Every
# other discovered tier (manufacturer/support/manual, official parts,
# service manual) auto-accepts above this confidence floor.
SOURCE_AUTO_ACCEPT_MIN_CONFIDENCE = 60
SOURCE_NEVER_AUTO_ACCEPT_TYPES = {"forum", "other"}

# Integration proposals: auto-approve low/medium risk regardless of
# confidence tier. High and safety_review risk are intentionally excluded -
# not because this policy blocks them (apply-integration already does that
# unconditionally) but because there is no reason to mark them "approved"
# when they can never be applied.
PROPOSAL_AUTO_APPROVE_RISK = {"low", "medium"}
PROPOSAL_AUTO_APPROVE_FROM_STATUS = {"proposed", "needs_review"}


def source_candidate_status(source_type: str, confidence: int) -> str:
    """Status to store for a freshly discovered source candidate."""
    if (
        source_type not in SOURCE_NEVER_AUTO_ACCEPT_TYPES
        and confidence >= SOURCE_AUTO_ACCEPT_MIN_CONFIDENCE
    ):
        return "accepted"
    return "candidate"


def integration_proposal_status(status: str, risk_level: str) -> str:
    """Status to store for a freshly created integration proposal."""
    if (
        status in PROPOSAL_AUTO_APPROVE_FROM_STATUS
        and risk_level in PROPOSAL_AUTO_APPROVE_RISK
    ):
        return "approved"
    return status
