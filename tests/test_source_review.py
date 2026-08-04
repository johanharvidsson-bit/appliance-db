from pathlib import Path

import pytest

from workers.__main__ import main, parser
from workers.source_review import decision_key


MIGRATION = Path("db/migrations/027_gate_b_source_review.sql")


def test_source_review_contract_is_registered() -> None:
    parsed = parser().parse_args(["source-review", "--site", "pilot", "list"])
    assert parsed.review_action == "list"
    parsed = parser().parse_args(
        [
            "source-review",
            "--site",
            "pilot",
            "show",
            "--source-candidate-id",
            "7",
        ]
    )
    assert parsed.source_candidate_id == 7


def test_decide_requires_explicit_confirmation_before_database_access() -> None:
    with pytest.raises(SystemExit, match="requires --confirm"):
        main(
            [
                "source-review",
                "--site",
                "pilot",
                "decide",
                "--source-candidate-id",
                "7",
                "--decision",
                "accepted",
                "--reviewer",
                "reviewer@example.invalid",
                "--reason",
                "Exact manufacturer source",
            ]
        )


def test_decision_key_is_trimmed_deterministic_and_audit_sensitive() -> None:
    baseline = decision_key(7, "accepted", " reviewer ", " exact source ")
    assert baseline == decision_key(7, "accepted", "reviewer", "exact source")
    assert baseline != decision_key(7, "rejected", "reviewer", "exact source")
    assert baseline != decision_key(7, "accepted", "reviewer", "different reason")


def test_review_storage_is_append_only_and_publicly_hidden() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ON DELETE RESTRICT" in sql
    assert "GRANT SELECT,INSERT ON public.source_candidate_reviews TO service_role" in sql
    assert "REVOKE UPDATE,DELETE,TRUNCATE" in sql
    assert "REVOKE ALL ON public.source_candidate_reviews FROM PUBLIC,anon,authenticated" in sql
