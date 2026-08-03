from __future__ import annotations

import json
from pathlib import Path

import pytest

from workers.__main__ import main
from workers.integration_repository import IntegrationRepository
from workers.knowledge_integration import ResolutionEngine, normalize_identifier

FIXTURE = Path(__file__).parent / "fixtures" / "knowledge_integration.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def resolve(index, catalog=None):
    data = load_fixture()
    return ResolutionEngine().resolve(data["facts"][index], catalog or data["catalog"])


def test_exact_model_spec_is_atomic_and_evidenced():
    result = resolve(0)
    proposal = result["proposals"][0]
    assert proposal["proposal_type"] == "propose_model_spec_update"
    assert (
        proposal["entity_id"] == "1" and proposal["targets"][0]["match_type"] == "exact"
    )
    assert proposal["proposed_value"] == {
        "field": "capacity",
        "value": "8",
        "unit": "kg",
    }
    assert proposal["evidence"][0]["id"] == 701 and proposal["status"] == "proposed"


def test_normalized_model_code_and_scope_rules():
    data = load_fixture()
    fact = {
        **data["facts"][0],
        "fact_type": "identity",
        "predicate": "model_code",
        "value": "DV80N62542W-EU",
        "backlog_entity_type": "unknown",
        "backlog_entity_id": "x",
    }
    data["catalog"]["models"][0]["name"] = "DV80N62542W/EU"
    proposal = ResolutionEngine().resolve(fact, data["catalog"])["proposals"][0]
    assert proposal["targets"][0]["match_type"] == "normalized_exact"
    wrong = {**fact, "brand_id": 999}
    wrong_proposal = ResolutionEngine().resolve(wrong, data["catalog"])["proposals"][0]
    assert wrong_proposal["status"] == "blocked" and wrong_proposal["conflicts"]


def test_variant_is_proposal_not_entity_write():
    proposal = resolve(1)["proposals"][0]
    assert proposal["proposal_type"] == "propose_variant_mapping"
    assert proposal["status"] == "needs_review" and proposal["entity_type"] == "model"


def test_exact_variant_and_wrong_model():
    data = load_fixture()
    data["catalog"]["variants"] = [
        {
            "id": 21,
            "model_id": 1,
            "variant_code": "DV80N62542W/EU",
            "status": "verified",
        }
    ]
    assert (
        ResolutionEngine().resolve(data["facts"][1], data["catalog"])["proposals"][0][
            "proposal_type"
        ]
        == "match_existing_variant"
    )
    data["catalog"]["variants"][0]["model_id"] = 2
    assert (
        ResolutionEngine().resolve(data["facts"][1], data["catalog"])["proposals"][0][
            "proposal_type"
        ]
        == "propose_variant_mapping"
    )


def test_candidate_variant_is_review_only():
    data = load_fixture()
    data["catalog"]["variants"] = [
        {
            "id": 21,
            "model_id": 1,
            "variant_code": "DV80N62542W/EU",
            "status": "candidate",
        }
    ]
    proposal = ResolutionEngine().resolve(data["facts"][1], data["catalog"])[
        "proposals"
    ][0]
    assert (
        proposal["status"] == "needs_review"
        and proposal["targets"][0]["match_type"] == "candidate"
    )


def test_verified_alias_can_only_create_reviewable_identity_score():
    data = load_fixture()
    fact = {
        **data["facts"][0],
        "fact_type": "identity",
        "predicate": "model_code",
        "value": "OLD-DV80",
        "backlog_entity_type": "unknown",
        "backlog_entity_id": "x",
    }
    data["catalog"]["model_aliases"] = [
        {"model_id": 1, "alias": "OLD DV80", "status": "verified"}
    ]
    proposal = ResolutionEngine().resolve(fact, data["catalog"])["proposals"][0]
    assert (
        proposal["targets"][0]["match_type"] == "alias" and proposal["confidence"] == 85
    )


def test_candidate_alias_and_legacy_candidate_are_not_verified_matches():
    data = load_fixture()
    fact = {
        **data["facts"][0],
        "fact_type": "identity",
        "predicate": "model_code",
        "value": "UNVERIFIED",
        "backlog_entity_type": "unknown",
        "backlog_entity_id": "x",
    }
    data["catalog"]["model_aliases"] = [
        {"model_id": 1, "alias": "UNVERIFIED", "status": "candidate"}
    ]
    data["catalog"]["legacy_model_mapping_candidates"] = [
        {"legacy_model_id": 99, "candidate_model_id": 1, "candidate_status": "accepted"}
    ]
    assert (
        ResolutionEngine().resolve(fact, data["catalog"])["proposals"][0]["status"]
        == "blocked"
    )


def test_out_of_scope_is_blocked_and_safety_procedure_gets_safety_review():
    data = load_fixture()
    outside = {**data["facts"][0], "out_of_scope": True, "scope": {"brand_id": 999}}
    proposal = ResolutionEngine().resolve(outside, data["catalog"])["proposals"][0]
    assert (
        proposal["status"] == "blocked"
        and proposal["difference_class"] == "out_of_scope"
    )
    hazardous = {
        **data["facts"][4],
        "value": {"instruction": "Disconnect power and dismantle electrical panel"},
    }
    proposal = ResolutionEngine().resolve(hazardous, data["catalog"])["proposals"][0]
    assert proposal["risk_level"] == "safety_review"


def test_proposal_identity_is_stable_and_changes_with_value():
    data = load_fixture()
    engine = ResolutionEngine()
    first = engine.resolve(data["facts"][0], data["catalog"])["proposals"][0][
        "input_hash"
    ]
    again = engine.resolve(data["facts"][0], data["catalog"])["proposals"][0][
        "input_hash"
    ]
    changed = {**data["facts"][0], "value": "9"}
    changed_hash = engine.resolve(changed, data["catalog"])["proposals"][0][
        "input_hash"
    ]
    assert first == again and first != changed_hash


def test_error_code_is_scoped_by_brand_and_category():
    proposal = resolve(2)["proposals"][0]
    assert (
        proposal["proposal_type"] == "propose_error_code_description"
        and proposal["entity_id"] == "41"
    )
    data = load_fixture()
    data["facts"][2]["category_id"] = 999
    wrong = ResolutionEngine().resolve(data["facts"][2], data["catalog"])["proposals"][
        0
    ]
    assert wrong["status"] == "blocked" and wrong["conflicts"]


def test_same_as_existing_emits_no_active_proposal():
    data = load_fixture()
    data["catalog"]["model_specs"] = {"1": {"capacity": "8"}}
    result = ResolutionEngine().resolve(data["facts"][0], data["catalog"])
    assert (
        result["proposals"] == [] and result["processing_state"] == "same_as_existing"
    )


def test_product_code_conflict_preserves_all_targets_and_no_winner():
    proposal = resolve(3)["proposals"][0]
    assert proposal["status"] == "blocked" and len(proposal["targets"]) == 2
    assert not any(x["is_preferred"] for x in proposal["targets"])
    assert proposal["conflicts"]


def test_fault_exact_fuzzy_and_cross_scope():
    data = load_fixture()
    fact = {
        **data["facts"][0],
        "fact_type": "fault",
        "value": {"symptom": "Will not drain"},
    }
    data["catalog"]["faults"] = [
        {
            "id": 51,
            "brand_id": 10,
            "category_id": 20,
            "canonical_name": "Will not drain",
        }
    ]
    assert (
        ResolutionEngine().resolve(fact, data["catalog"])["proposals"][0]["status"]
        == "proposed"
    )
    fact["value"] = {"symptom": "Does not drain properly"}
    assert ResolutionEngine().resolve(fact, data["catalog"])["proposals"][0][
        "status"
    ] in {"needs_review", "blocked"}
    fact["value"] = {"symptom": "Will not drain"}
    fact["brand_id"] = 11
    wrong = ResolutionEngine().resolve(fact, data["catalog"])["proposals"][0]
    assert wrong["status"] == "blocked" and wrong["conflicts"]


def test_guide_candidate_and_exact_procedure():
    result = resolve(4)
    assert result["proposals"][0]["proposal_type"] == "propose_new_guide_candidate"
    data = load_fixture()
    data["facts"][4]["value"]["procedure_hash"] = "abc"
    data["catalog"]["guides"] = [
        {"id": 61, "brand_id": 10, "category_id": 20, "steps_hash": "abc"}
    ]
    assert (
        ResolutionEngine().resolve(data["facts"][4], data["catalog"])["proposals"][0][
            "proposal_type"
        ]
        == "match_existing_guide"
    )


def test_conflicted_fact_is_never_apply_ready():
    proposal = resolve(3)["proposals"][0]
    assert proposal["status"] == "blocked" and proposal["status"] not in {
        "approved",
        "applied",
    }


def test_identity_normalization_is_deterministic():
    assert normalize_identifier("DV80N62542W/EU") == normalize_identifier(
        "DV80N62542W-EU"
    )


def test_fixture_acceptance_and_rejected_fact_skipped(tmp_path, capsys):
    assert (
        main(
            [
                "knowledge-integration",
                "--site",
                "appliance-repair-base",
                "--fixture",
                str(FIXTURE),
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["candidate_facts_read"] == 5 and output["proposals_generated"] == 5
    assert output["blocked_proposals"] == 1 and output["proposals_needing_review"] >= 2
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert set(report["proposal_types"]) >= {
        "propose_model_spec_update",
        "propose_variant_mapping",
        "propose_error_code_description",
        "propose_new_guide_candidate",
    }


def test_cli_filters_and_empty_result(tmp_path, capsys):
    main(
        [
            "knowledge-integration",
            "--site",
            "appliance-repair-base",
            "--fixture",
            str(FIXTURE),
            "--candidate-fact-id",
            "999",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert json.loads(capsys.readouterr().out)["candidate_facts_read"] == 0


def test_invalid_site_and_production_are_rejected():
    with pytest.raises(SystemExit):
        main(["knowledge-integration", "--site", "wrong", "--fixture", str(FIXTURE)])
    with pytest.raises(SystemExit):
        main(
            [
                "knowledge-integration",
                "--site",
                "appliance-repair-base",
                "--environment",
                "production",
                "--fixture",
                str(FIXTURE),
            ]
        )


def test_strict_write_boundary_and_migration_security():
    forbidden = {
        "brands",
        "categories",
        "models",
        "model_variants",
        "product_codes",
        "error_codes",
        "faults",
        "guides",
        "articles",
        "url_registry",
        "url_redirects",
    }
    assert IntegrationRepository.WRITABLE_TABLES.isdisjoint(forbidden)
    sql = (
        Path(__file__).parents[1] / "db/migrations/023_knowledge_integration_worker.sql"
    ).read_text(encoding="utf-8")
    assert "ON DELETE CASCADE" not in sql and "FORCE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL" in sql and "'approved'" in sql and "'applied'" in sql
