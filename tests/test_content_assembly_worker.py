from __future__ import annotations
import json
from pathlib import Path
import pytest
from workers.__main__ import main
from workers.assembly_cli import _domain_item
from workers.assembly_repository import AssemblyRepository
from workers.content_assembly import ASSEMBLER_VERSION, AssemblyEngine, TEMPLATES

FIXTURE = Path(__file__).parent / "fixtures" / "content_assembly.json"


def data():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def draft(index, template=None):
    return AssemblyEngine().assemble(data()["items"][index], template)


def test_template_registry_is_versioned_bounded_and_not_series_dependent():
    assert set(TEMPLATES) == {
        "model_overview_v1",
        "error_code_description_v1",
        "fault_summary_v1",
        "troubleshooting_guide_v1",
        "translation_v1",
        "faq_candidate_v1",
    }
    assert all(
        t.version and t.sections and "series" not in t.required
        for t in TEMPLATES.values()
    )


def test_model_overview_has_stable_sections_evidence_and_no_filler():
    d = draft(0)
    assert d["status"] == "assembled" and d["template_id"] == "model_overview_v1"
    assert list(d["rendered_content"]) == [
        "short_summary",
        "overview",
        "key_specifications",
        "variants_summary",
    ]
    assert all(
        s["evidence"] for s in d["sections"] if s["section_status"] == "assembled"
    )
    text = json.dumps(d["rendered_content"]).lower()
    assert "coming soon" not in text and "placeholder" not in text


def test_model_specs_only_is_partial_and_empty_sections_are_omitted():
    item = data()["items"][0]
    item["facts"] = [
        x for x in item["facts"] if x["key"] in {"model_name", "specifications"}
    ]
    d = AssemblyEngine().assemble(item)
    assert d["status"] == "partial"
    assert (
        next(s for s in d["sections"] if s["section_key"] == "overview")[
            "section_status"
        ]
        == "omitted_no_data"
    )


def test_error_code_missing_meaning_is_blocked_without_placeholder():
    d = draft(1)
    assert d["status"] == "blocked" and any(
        i["issue_type"] == "missing_required_fact" for i in d["issues"]
    )
    assert "meaning" not in d["rendered_content"]
    assert d["validation_state"] == "validation_failed"


def test_applied_error_fact_evidence_covers_code_and_meaning():
    item = _domain_item(
        {
            "backlog_id": 4,
            "entity_type": "error_code",
            "entity_id": "19",
            "locale": "en",
            "action_type": "describe_error_code",
            "entity_name": "4C",
            "brand_name": "Samsung",
            "category_name": "washing_machine",
            "entity_evidence": [],
            "integrated_facts": [
                {
                    "candidate_fact_id": 6,
                    "source_document_id": 3,
                    "fact_type": "error_code",
                    "predicate": "meaning",
                    "value": {"code": "4C", "meaning": "Water supply issue."},
                    "proposed_value": {
                        "field": "description",
                        "value": "Water supply issue.",
                    },
                    "evidence_id": 6,
                    "locator": "main > p",
                    "page_number": None,
                }
            ],
        }
    )
    assembled = AssemblyEngine().assemble(item)
    assert assembled["status"] == "assembled"
    assert all(
        section["evidence"]
        for section in assembled["sections"]
        if section["required"]
    )


def test_error_code_without_guide_is_valid_and_guide_section_omitted():
    d = draft(2)
    assert d["status"] == "assembled"
    guide = next(s for s in d["sections"] if s["section_key"] == "related_guides")
    assert guide["section_status"] == "omitted_no_data"


def test_first_checks_without_evidence_are_blocked_not_rendered():
    item = data()["items"][2]
    item["facts"].append(
        {"key": "first_safe_checks", "value": ["Reset unit"], "evidence": []}
    )
    d = AssemblyEngine().assemble(item)
    section = next(s for s in d["sections"] if s["section_key"] == "first_safe_checks")
    assert (
        section["section_status"] == "blocked_missing_evidence"
        and "first_safe_checks" not in d["rendered_content"]
    )


def test_guide_preserves_order_and_flags_safety_review():
    d = draft(3)
    assert d["risk_level"] == "safety_review" and d["review_state"] == "unreviewed"
    assert [x["step_number"] for x in d["rendered_content"]["steps"]["steps"]] == [
        1,
        2,
        3,
    ]
    assert any(i["issue_type"] == "safety_review_required" for i in d["issues"])


def test_guide_missing_or_vague_procedure_is_blocked():
    item = data()["items"][3]
    item["facts"] = [x for x in item["facts"] if x["key"] != "steps"]
    assert AssemblyEngine().assemble(item)["status"] == "blocked"
    item = data()["items"][3]
    next(x for x in item["facts"] if x["key"] == "steps")["value"] = [
        {"step_number": 1, "instruction": "Check it"}
    ]
    assert AssemblyEngine().assemble(item)["status"] == "blocked"


def test_translation_keeps_source_hash_identifiers_and_is_review_only():
    d = draft(4)
    assert d["draft_type"] == "translation" and d["status"] == "partial"
    assert (
        d["rendered_content"]["translation_metadata"]["source_content_hash"]
        == "sha256:abc"
    )
    assert (
        "CE" in json.dumps(d["rendered_content"], ensure_ascii=False)
        and d["review_state"] == "unreviewed"
    )


def test_translation_locale_mismatch_blocks():
    item = data()["items"][4]
    item["locale"] = "de"
    assert AssemblyEngine().assemble(item)["status"] == "blocked"


def test_conflicting_facts_block_normal_draft_and_retain_all_evidence():
    d = draft(5)
    assert (
        d["status"] == "blocked"
        and d["sections"][0]["section_status"] == "blocked_conflict"
    )
    assert len(d["sections"][0]["evidence"]) == 2


def test_unsupported_claim_is_blocked():
    item = data()["items"][0]
    item["facts"].append(
        {
            "key": "typical_lifespan",
            "value": "10 years",
            "evidence": [{"source_evidence_id": 99}],
        }
    )
    assert AssemblyEngine().assemble(item)["status"] == "blocked"


def test_idempotency_changes_with_fact_template_or_assembler_input():
    item = data()["items"][0]
    first = AssemblyEngine().assemble(item)
    again = AssemblyEngine().assemble(item)
    assert (
        first["source_input_hash"] == again["source_input_hash"]
        and first["content_hash"] == again["content_hash"]
    )
    item["facts"][3]["value"] = "Changed"
    assert (
        AssemblyEngine().assemble(item)["source_input_hash"]
        != first["source_input_hash"]
    )
    assert ASSEMBLER_VERSION == "1.0.0"


def test_existing_content_same_does_not_require_duplicate_content():
    item = data()["items"][0]
    first = AssemblyEngine().assemble(item)
    item["existing_content"] = first["rendered_content"]
    assert AssemblyEngine().assemble(item)["comparison_class"] == "same_as_existing"


def test_fixture_cli_filters_and_reports(tmp_path, capsys):
    rc = main(
        [
            "content-assembly",
            "--site",
            "appliance-repair-base",
            "--fixture",
            str(FIXTURE),
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert rc == 0
    output = json.loads(capsys.readouterr().out)
    assert output["backlog_items_read"] == 6 and output["drafts_blocked"] == 2
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert report["safety_review_drafts"] == 1


def test_only_blocked_batch_has_blocked_exit_code(tmp_path, capsys):
    rc = main(
        [
            "content-assembly",
            "--site",
            "appliance-repair-base",
            "--fixture",
            str(FIXTURE),
            "--backlog-id",
            "2",
            "--output-dir",
            str(tmp_path),
        ]
    )
    capsys.readouterr()
    assert rc == 3


def test_invalid_site_is_rejected_and_fixture_mode_ignores_environment():
    with pytest.raises(SystemExit):
        main(["content-assembly", "--site", "wrong", "--fixture", str(FIXTURE)])
    # Fixture mode never touches a database or network regardless of
    # --environment, so production is not blanket-rejected here - only a real,
    # unapproved production *write* is (see config/target_safety.py).
    main(
        [
            "content-assembly",
            "--site",
            "appliance-repair-base",
            "--environment",
            "production",
            "--fixture",
            str(FIXTURE),
        ]
    )


def test_strict_write_boundary():
    forbidden = {
        "models",
        "error_codes",
        "faults",
        "guides",
        "model_content_translations",
        "article_translations",
        "url_registry",
        "url_redirects",
    }
    assert AssemblyRepository.WRITABLE_TABLES.isdisjoint(forbidden)


def test_migration_security_and_no_public_status():
    sql = (
        Path(__file__).parents[1] / "db/migrations/025_content_assembly_worker.sql"
    ).read_text(encoding="utf-8")
    assert (
        "ON DELETE CASCADE" not in sql
        and "FORCE ROW LEVEL SECURITY" in sql
        and "REVOKE ALL" in sql
    )
    assert "'published'" not in sql and "'validated'" not in sql


def test_database_adapter_preserves_aggregated_evidence_chain():
    row = {
        "backlog_id": 9,
        "entity_type": "model",
        "entity_id": "1",
        "locale": "en",
        "action_type": "create_model_overview",
        "entity_name": "DV80",
        "brand_name": "Samsung",
        "category_name": "dryer",
        "entity_evidence": [{"source_evidence_id": 1}],
        "integrated_facts": [
            {
                "candidate_fact_id": 2,
                "source_document_id": 3,
                "evidence_id": 4,
                "fact_type": "specification",
                "predicate": "capacity",
                "value": "8",
                "proposed_value": {"value": "8"},
                "locator": "page:1",
                "page_number": 1,
            }
        ],
    }
    item = _domain_item(row)
    facts = {x["key"]: x for x in item["facts"]}
    assert facts["model_name"]["evidence"][0]["source_evidence_id"] == 1
    assert facts["specifications"]["evidence"][0]["candidate_fact_id"] == 2


def test_guide_created_from_a_translate_backlog_item_is_reattributed_to_the_guide():
    # apply-integration's create_reviewed_guide targets the backlog item's own
    # topic (e.g. an error_code), not the guide it actually creates - there is
    # nothing existing to target yet. The resulting draft must describe the
    # guide, not the error_code that happened to spawn it.
    row = {
        "backlog_id": 7,
        "entity_type": "error_code",
        "entity_id": "294",
        "locale": "en",
        "action_type": "translate_error_code",
        "entity_name": "5E",
        "brand_name": "Samsung",
        "category_name": "washing_machine",
        "entity_evidence": [],
        "resolved_guide_id": 1,
        "resolved_guide_title": "Error Code 294 repair guide",
        "integrated_facts": [
            {
                "candidate_fact_id": 10,
                "source_document_id": 11,
                "evidence_id": 12,
                "fact_type": "guide_step",
                "predicate": "instruction",
                "value": {"step_number": 1, "instruction": "Unplug the appliance"},
                "proposed_value": {"step_number": 1, "instruction": "Unplug the appliance"},
                "locator": "page:1",
                "page_number": 1,
            },
            {
                "candidate_fact_id": 13,
                "source_document_id": 11,
                "evidence_id": 14,
                "fact_type": "guide_step",
                "predicate": "instruction",
                "value": {"step_number": 2, "instruction": "Clean the drain filter"},
                "proposed_value": {"step_number": 2, "instruction": "Clean the drain filter"},
                "locator": "page:1",
                "page_number": 1,
            },
        ],
    }
    item = _domain_item(row)
    assert item["entity_type"] == "guide" and item["entity_id"] == "1"
    facts = {x["key"]: x for x in item["facts"]}
    assert facts["title"]["value"] == "Error Code 294 repair guide"
    assert "code" not in facts
    assert [s["step_number"] for s in facts["steps"]["value"]] == [1, 2]
    draft = AssemblyEngine().assemble(item)
    assert draft["draft_type"] == "troubleshooting_guide"
    assert draft["entity_type"] == "guide" and draft["entity_id"] == "1"
