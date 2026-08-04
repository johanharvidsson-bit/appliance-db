from pathlib import Path


SQL = (
    (
        Path(__file__).parents[1]
        / "db/migrations/026_content_validation_safety_worker.sql"
    )
    .read_text(encoding="utf-8")
    .lower()
)


def test_migration_creates_versioned_validation_history():
    for table in (
        "content_validation_runs",
        "content_validation_results",
        "content_claim_checks",
        "content_safety_findings",
        "content_duplication_findings",
    ):
        assert f"create table public.{table}" in SQL
    assert "validation_identity_hash text not null unique" in SQL


def test_migration_denies_public_and_delete_access():
    assert "revoke all on public.%i from public,anon,authenticated" in SQL
    assert "revoke delete on public.%i from service_role" in SQL
    assert "force row level security" in SQL


def test_migration_limits_state_machine_and_registers_026():
    assert "validation_stale" in SQL
    assert "content_validation_needs_review" in SQL
    assert "values('026','026_content_validation_safety_worker.sql')" in SQL
