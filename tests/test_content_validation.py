from copy import deepcopy
import json
from pathlib import Path

from workers.content_validation import RULE_CATALOG, ValidationEngine, _hash, _steps
from workers.validation_cli import _fixture_draft, _summary
from workers.validation_repository import ValidationRepository


FIXTURE = Path(__file__).parent / "fixtures" / "content_validation.json"


def drafts():
    values = json.loads(FIXTURE.read_text(encoding="utf-8"))["drafts"]
    result = [_fixture_draft(value) for value in values]
    result[7]["validation_context"]["existing_drafts"][0]["procedure_hash"] = _hash(
        _steps(result[7])
    )
    return result


def validate(index):
    draft = drafts()[index]
    context = draft.pop("validation_context", {})
    return ValidationEngine().validate(draft, context)


def test_valid_overview_passes():
    assert validate(0)["overall_result"] == "pass"


def test_unsupported_marketing_claim_fails():
    result = validate(1)
    assert result["overall_result"] == "fail"
    assert "missing_evidence" in result["summary"]["issue_codes"]


def test_error_code_without_guide_is_valid():
    assert validate(2)["overall_result"] == "pass"


def test_safety_guide_requires_review_not_publication():
    result = validate(3)
    assert result["overall_result"] == "needs_review"
    assert result["publication_readiness_result"] == "requires_review"
    assert result["safety_findings"]


def test_missing_required_warning_fails():
    result = validate(4)
    assert result["overall_result"] == "fail"
    assert "missing_safety_warning" in result["summary"]["issue_codes"]


def test_stale_translation_needs_review():
    result = validate(5)
    assert result["overall_result"] == "needs_review"
    assert result["translation_result"] == "needs_review"


def test_identifier_mismatch_fails():
    assert validate(6)["overall_result"] == "fail"


def test_duplicate_procedure_needs_review():
    result = validate(7)
    assert result["overall_result"] == "needs_review"
    assert result["duplication_findings"][0]["match_type"] == "procedure_duplicate"


def test_validator_does_not_mutate_draft():
    draft = drafts()[0]
    before = deepcopy(draft)
    ValidationEngine().validate(draft)
    assert draft == before


def test_identity_is_deterministic_and_changes_with_ruleset_inputs():
    draft = drafts()[0]
    first = ValidationEngine().validate(draft)
    second = ValidationEngine().validate(draft)
    assert first["validation_identity_hash"] == second["validation_identity_hash"]
    draft["sections"][0]["evidence"].append({"source_evidence_id": 9})
    assert (
        ValidationEngine().validate(draft)["validation_identity_hash"]
        != first["validation_identity_hash"]
    )


def test_rule_catalog_is_auditable():
    assert RULE_CATALOG
    assert all(
        {"effect", "false_positive_risk", "remediation"} <= value.keys()
        for value in RULE_CATALOG.values()
    )


def test_repository_write_allowlist_excludes_draft_content_tables():
    assert "content_draft_sections" not in ValidationRepository.WRITABLE_TABLES
    assert "content_draft_evidence" not in ValidationRepository.WRITABLE_TABLES


def test_repository_uses_unambiguous_filtered_section_alias():
    source = Path(ValidationRepository.__module__.replace(".", "/") + ".py").read_text(
        encoding="utf-8"
    )
    assert "AS draft_sections" in source
    assert "FILTER (WHERE s.id IS NOT NULL)" in source
    assert 'section["section_status"] in {"assembled", "needs_review"}' in source


def test_summary_counts_outcomes():
    rows = [{"result": validate(0)}, {"result": validate(3)}, {"result": validate(4)}]
    assert _summary(rows, 3)["passed"] == 1
    assert _summary(rows, 3)["needs_review"] == 1
    assert _summary(rows, 3)["failed"] == 1
