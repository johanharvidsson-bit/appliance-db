"""
db/apply_migration.py

Applies SQL migration files against a standard PostgreSQL database.
Uses a direct psycopg2 connection (requires DATABASE_URL in .env).

DATABASE_URL format:
  postgresql://repairbase:password@db-host:5432/repairbase

Migration tracking:
  Applied migrations are recorded in the schema_migrations table.
  Running a migration that's already in schema_migrations is a no-op (safe to re-run).

Usage:
    python -m db.apply_migration db/migrations/004_migration_tracking_and_error_code_fields.sql
    python -m db.apply_migration --list        # show all .sql migrations + applied status
    python -m db.apply_migration --all         # apply all unapplied migrations in order
    python -m db.apply_migration --check       # connection + server readiness
    python -m db.apply_migration --verify-repairbase  # rollback-only phase-1 fixture
"""

import sys
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

_MISSING_URL_MSG = (
    "DATABASE_URL not set in .env\n"
    "Format: DATABASE_URL=postgresql://repairbase:password@db-host:5432/repairbase\n"
    "SUPABASE_DB_URL remains a temporary fallback for the legacy deployment."
)


def get_connection():
    url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not url:
        logger.error(_MISSING_URL_MSG)
        sys.exit(1)
    return psycopg2.connect(url)


def check_connection() -> None:
    """Verify connectivity and print only non-sensitive server metadata."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database(), current_user, "
                "current_setting('server_version'), pg_is_in_recovery()"
            )
            database, user, version, in_recovery = cur.fetchone()
        logger.success(
            "Connected to database={} user={} PostgreSQL={} read_only_replica={}",
            database, user, version, in_recovery,
        )
    finally:
        conn.close()


def verify_repairbase() -> None:
    """Execute the rollback-only phase-1 fixture against PostgreSQL."""
    fixture = BASE_DIR / "tests" / "fixtures" / "repairbase_phase1.sql"
    if not fixture.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture}")
    conn = get_connection()
    try:
        # The fixture owns its BEGIN/ROLLBACK boundary.
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(fixture.read_text(encoding="utf-8"))
        logger.success("RepairBase phase-1 fixture passed and was rolled back")
    finally:
        conn.close()


def _is_applied(conn, version: str) -> bool:
    """Check if a migration version is already recorded in schema_migrations."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s", (version,)
            )
            return cur.fetchone() is not None
    except psycopg2.errors.UndefinedTable:
        # schema_migrations doesn't exist yet — this is the bootstrap migration
        conn.rollback()
        return False


def _record_applied(conn, version: str, filename: str) -> None:
    """Insert a row into schema_migrations to mark this migration as applied."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO schema_migrations (version, filename) VALUES (%s, %s) "
            "ON CONFLICT (version) DO NOTHING",
            (version, filename),
        )


def _version_from_path(sql_path: Path) -> str:
    """Extract version prefix from filename, e.g. '004' from '004_something.sql'."""
    return sql_path.stem.split("_")[0]


def migration_files() -> list[Path]:
    """Return migrations in numeric order and reject ambiguous versions."""
    mig_dir = BASE_DIR / "db" / "migrations"
    files = list(mig_dir.glob("*.sql"))
    invalid = [path.name for path in files if not _version_from_path(path).isdigit()]
    if invalid:
        raise ValueError(f"Migration filenames must start with digits: {invalid}")
    files.sort(key=lambda path: (int(_version_from_path(path)), path.name))
    versions = [_version_from_path(path) for path in files]
    duplicates = sorted({version for version in versions if versions.count(version) > 1})
    if duplicates:
        raise ValueError(f"Duplicate migration versions: {duplicates}")
    return files


def apply(sql_path: Path, skip_if_applied: bool = True) -> bool:
    """
    Apply one migration file.
    Returns True if the migration was applied, False if it was skipped.
    """
    version = _version_from_path(sql_path)
    sql = sql_path.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        if skip_if_applied and _is_applied(conn, version):
            logger.info(f"Skipping {sql_path.name} (already applied)")
            return False

        logger.info(f"Applying migration {version}: {sql_path.name}")
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            _record_applied(conn, version, sql_path.name)
        logger.success(f"Migration {version} applied: {sql_path.name}")
        return True
    finally:
        conn.close()


def apply_all() -> None:
    """Apply all unapplied migrations in db/migrations/ in version order."""
    mig_dir = BASE_DIR / "db" / "migrations"
    files = migration_files()
    if not files:
        logger.warning(f"No migration files found in {mig_dir}")
        return

    applied = 0
    skipped = 0
    for f in files:
        if apply(f, skip_if_applied=True):
            applied += 1
        else:
            skipped += 1

    logger.info(f"apply_all complete: {applied} applied, {skipped} already done")


def list_migrations() -> None:
    mig_dir = BASE_DIR / "db" / "migrations"
    files = migration_files()

    # Try to check applied status; fall back gracefully if DB unreachable
    applied_versions: set[str] = set()
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version FROM schema_migrations")
                applied_versions = {row[0] for row in cur.fetchall()}
        except psycopg2.errors.UndefinedTable:
            pass
        finally:
            conn.close()
    except SystemExit:
        pass  # DATABASE_URL not set — just list files without database status

    print(f"\nMigrations in {mig_dir}:")
    for f in files:
        version = _version_from_path(f)
        status = "[applied]" if version in applied_versions else "[pending]"
        print(f"  {status:12}  {f.name}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        list_migrations()
        sys.exit(0)

    if sys.argv[1] == "--all":
        apply_all()
        sys.exit(0)

    if sys.argv[1] == "--check":
        check_connection()
        sys.exit(0)

    if sys.argv[1] == "--verify-repairbase":
        verify_repairbase()
        sys.exit(0)

    path = Path(sys.argv[1])
    if not path.exists():
        path = BASE_DIR / path
    if not path.exists():
        logger.error(f"Migration file not found: {sys.argv[1]}")
        sys.exit(1)

    apply(path)
