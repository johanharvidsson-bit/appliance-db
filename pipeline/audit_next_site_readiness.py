"""Read-only structural readiness audit for beginning the next site frontend."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

import psycopg2

from config.site_contract import validate_site_contract
from config.target_safety import assert_safe_target


REQUIRED_MIGRATIONS = {"015", "016", "017", "018", "019"}
REQUIRED_TABLES = {
    "model_variants", "guides", "guide_translations", "sources", "source_evidence",
    "url_registry", "entity_url_bindings", "worker_batches", "worker_jobs",
    "worker_observations", "worker_events", "sites", "site_locales", "site_entity_publications",
}
REQUIRED_VIEWS = {
    "model_variants_v1", "model_content_v1", "guides_v1", "model_page_guides_v1",
    "sites_v1", "site_models_v1", "site_guides_v1", "site_sitemap_entries_v1",
}


@dataclass(frozen=True)
class AuditCheck:
    name: str
    passed: bool
    detail: str


def audit(dsn: str, contract_path: Path) -> dict:
    assert_safe_target(dsn, app_env="development", operation="read")
    checks: list[AuditCheck] = []
    try:
        contract = validate_site_contract(json.loads(contract_path.read_text(encoding="utf-8")))
        checks.append(AuditCheck("site_contract", True, contract["site_id"]))
    except Exception as error:
        checks.append(AuditCheck("site_contract", False, type(error).__name__))

    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version FROM schema_migrations WHERE version=ANY(%s)", (list(REQUIRED_MIGRATIONS),))
            migrations = {row[0] for row in cursor.fetchall()}
            checks.append(AuditCheck("migration_chain", migrations == REQUIRED_MIGRATIONS, ",".join(sorted(migrations))))
            cursor.execute(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relkind='r' AND c.relname=ANY(%s)",
                (list(REQUIRED_TABLES),),
            )
            tables = {row[0] for row in cursor.fetchall()}
            checks.append(AuditCheck("platform_tables", tables == REQUIRED_TABLES, f"{len(tables)}/{len(REQUIRED_TABLES)}"))
            cursor.execute("SELECT table_name FROM information_schema.views WHERE table_schema='api_public' AND table_name=ANY(%s)", (list(REQUIRED_VIEWS),))
            views = {row[0] for row in cursor.fetchall()}
            checks.append(AuditCheck("public_contract_views", views == REQUIRED_VIEWS, f"{len(views)}/{len(REQUIRED_VIEWS)}"))
            cursor.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relname=ANY(%s) AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)",
                (list(REQUIRED_TABLES - {"url_registry", "entity_url_bindings"}),),
            )
            insecure = cursor.fetchone()[0]
            checks.append(AuditCheck("forced_rls", insecure == 0, f"insecure={insecure}"))
            cursor.execute(
                "SELECT count(*) FROM unnest(%s::text[]) t(name) "
                "WHERE has_table_privilege('anon','public.'||name,'SELECT,INSERT,UPDATE,DELETE') "
                "OR has_table_privilege('authenticated','public.'||name,'SELECT,INSERT,UPDATE,DELETE')",
                (list(REQUIRED_TABLES),),
            )
            public_leaks = cursor.fetchone()[0]
            checks.append(AuditCheck("no_base_table_public_access", public_leaks == 0, f"leaks={public_leaks}"))
            cursor.execute("SELECT count(*) FROM api_public.site_sitemap_entries_v1 WHERE canonical_path IS NULL OR canonical_path NOT LIKE '/%'")
            invalid_sitemap = cursor.fetchone()[0]
            checks.append(AuditCheck("site_sitemap_contract", invalid_sitemap == 0, f"invalid={invalid_sitemap}"))
            cursor.execute("SELECT count(*) FROM legacy_model_mapping_candidates WHERE candidate_status<>'candidate'")
            checks.append(AuditCheck("pilot_candidates_non_authoritative", cursor.fetchone()[0] == 0, "review state preserved"))
            cursor.execute("SELECT count(*) FROM worker_jobs WHERE status='running' AND (leased_at IS NULL OR lease_owner IS NULL)")
            invalid_leases = cursor.fetchone()[0]
            checks.append(AuditCheck("worker_lease_invariant", invalid_leases == 0, f"invalid={invalid_leases}"))
            cursor.execute(
                "SELECT count(*) FROM site_entity_publications p JOIN url_registry u ON u.id=p.canonical_url_id "
                "WHERE p.site_id<>u.site_id"
            )
            cross_site = cursor.fetchone()[0]
            checks.append(AuditCheck("site_url_isolation", cross_site == 0, f"cross_site={cross_site}"))

    result = {"ready": all(check.passed for check in checks), "checks": [asdict(check) for check in checks]}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="audit next-site technical readiness")
    parser.add_argument("--contract", type=Path, default=Path("site_templates/example-next-site.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--database-url-env", default="REPAIRBASE_SECURITY_TEST_DB_URL")
    args = parser.parse_args(argv)
    dsn = os.getenv(args.database_url_env, "").strip()
    if not dsn:
        raise RuntimeError(f"missing database URL environment variable: {args.database_url_env}")
    result = audit(dsn, args.contract)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
