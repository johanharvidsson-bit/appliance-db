"""
db/apply_migration.py

Applies SQL migration files against the Supabase Postgres database.
Uses a direct psycopg2 connection (requires SUPABASE_DB_URL in .env).

SUPABASE_DB_URL format:
  postgresql://postgres.{project_ref}:{password}@aws-0-{region}.pooler.supabase.com:6543/postgres
  (find it in: Supabase Dashboard → Settings → Database → Connection string → Pooler)

Migration tracking:
  Applied migrations are recorded in the schema_migrations table.
  Running a migration that's already in schema_migrations is a no-op (safe to re-run).

Usage:
    python -m db.apply_migration db/migrations/004_migration_tracking_and_error_code_fields.sql
    python -m db.apply_migration --list        # show all .sql migrations + applied status
    python -m db.apply_migration --all         # apply all unapplied migrations in order
"""

import os
import sys
from pathlib import Path

import psycopg2
from loguru import logger

from config.environment import load_settings
from config.paths import BASE_DIR
from config.target_safety import (
    assert_configured_development_target,
    production_approval_from_env,
)

_MISSING_URL_MSG = (
    "SUPABASE_DB_URL not set in .env\n"
    "Get it from: Supabase Dashboard -> Settings -> Database -> Connection string -> Pooler\n"
    "Format: SUPABASE_DB_URL=postgresql://postgres.{ref}:{password}@aws-0-{region}.pooler.supabase.com:6543/postgres"
)


def get_connection(*, operation: str = "read"):
    settings = load_settings()
    target = (
        os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL", "").strip()
        or settings.supabase_db_url
    )
    if not target:
        logger.error(_MISSING_URL_MSG)
        sys.exit(1)
    approval = None
    if settings.app_env.strip().lower() == "production":
        # Second factor beyond ALLOW_PRODUCTION_WRITE/PRODUCTION_WRITE_CONFIRMATION:
        # applying a migration has no --production-token CLI flag (this script
        # takes a file path, not worker-style args), so the explicit
        # confirmation must be a separate env var an operator sets by hand for
        # this invocation, not one that's already sitting in the same .env as
        # PRODUCTION_WRITE_CONFIRMATION.
        approval = production_approval_from_env(
            command_flag=True,
            supplied_token=os.getenv("PRODUCTION_MIGRATION_CONFIRM", ""),
        )
    assert_configured_development_target(
        target,
        app_env=settings.app_env,
        operation=operation,
        approval=approval,
    )
    return psycopg2.connect(target)


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
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO schema_migrations (version, filename) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
                (version, filename),
            )
    except psycopg2.errors.UndefinedTable:
        # schema_migrations not yet created (will be created by the current migration)
        conn.rollback()


def _version_from_path(sql_path: Path) -> str:
    """Extract version prefix from filename, e.g. '004' from '004_something.sql'."""
    return sql_path.stem.split("_")[0]


def apply(sql_path: Path, skip_if_applied: bool = True) -> bool:
    """
    Apply one migration file.
    Returns True if the migration was applied, False if it was skipped.
    """
    version = _version_from_path(sql_path)
    sql = sql_path.read_text(encoding="utf-8")
    conn = get_connection(operation="write")
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
    files = sorted(mig_dir.glob("*.sql"))
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
    files = sorted(mig_dir.glob("*.sql"))

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
        pass  # SUPABASE_DB_URL not set — just list files without status

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

    path = Path(sys.argv[1])
    if not path.exists():
        path = BASE_DIR / path
    if not path.exists():
        logger.error(f"Migration file not found: {sys.argv[1]}")
        sys.exit(1)

    apply(path)
