from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "db/apply_migration.py").read_text(encoding="utf-8")


def test_database_url_is_preferred_with_legacy_fallback():
    assert 'os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")' in SOURCE


def test_vps_readiness_commands_exist():
    assert 'sys.argv[1] == "--check"' in SOURCE
    assert 'sys.argv[1] == "--verify-repairbase"' in SOURCE


def test_runner_discovers_numeric_migrations_and_rejects_duplicates():
    assert "def migration_files()" in SOURCE
    assert "files.sort(key=lambda path: (int(_version_from_path(path)), path.name))" in SOURCE
    assert "Duplicate migration versions" in SOURCE
    migration_names = sorted(
        path.name
        for path in (Path(__file__).resolve().parents[1] / "db/migrations").glob("*.sql")
    )
    assert migration_names[-3:] == [
        "011_repairbase_catalog_applicability.sql",
        "012_repairbase_evidence_specifications.sql",
        "013_repairbase_localization_publication.sql",
    ]


def test_tracking_failure_is_not_silently_rolled_back():
    record_body = SOURCE.split("def _record_applied", 1)[1].split(
        "def _version_from_path", 1
    )[0]
    assert "except psycopg2.errors.UndefinedTable" not in record_body
