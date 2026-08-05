from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from urllib.parse import urlparse


APPLIANCE_PRODUCTION_HOST = "api.appliancerepairbase.com"
MARINE_PRODUCTION_HOST = "api.marinerepairbase.com"
RETIRED_SUPABASE_HOST = "jqepafrexisjmzoefvpr.supabase.co"
DEV_HOSTS = {"127.0.0.1", "localhost"}
DEV_PORT = 18080
PRODUCTION_DATABASE_MARKERS = {"appliancedb", "marinerepairbase"}


class TargetSafetyError(RuntimeError):
    pass


class TargetKind(str, Enum):
    DEVELOPMENT = "development"
    APPLIANCE_PRODUCTION = "appliance-production"
    MARINE_PRODUCTION = "marine-production"
    RETIRED = "retired"
    PRODUCTION_DATABASE = "production-database"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProductionApproval:
    allow_environment: bool = False
    command_flag: bool = False
    configured_token: str = ""
    supplied_token: str = ""

    @property
    def complete(self) -> bool:
        return bool(
            self.allow_environment
            and self.command_flag
            and self.configured_token
            and self.supplied_token
            and self.configured_token == self.supplied_token
        )


def classify_target(target: str) -> TargetKind:
    try:
        parsed = urlparse(target)
        if (
            parsed.scheme not in {"http", "https", "postgres", "postgresql"}
            or not parsed.hostname
        ):
            return TargetKind.UNKNOWN
        host = parsed.hostname.lower()
        if host == RETIRED_SUPABASE_HOST:
            return TargetKind.RETIRED
        if host == MARINE_PRODUCTION_HOST:
            return TargetKind.MARINE_PRODUCTION
        if host == APPLIANCE_PRODUCTION_HOST:
            return TargetKind.APPLIANCE_PRODUCTION
        database = parsed.path.strip("/").lower()
        if (
            parsed.scheme in {"postgres", "postgresql"}
            and database in PRODUCTION_DATABASE_MARKERS
        ):
            return TargetKind.PRODUCTION_DATABASE
        if host in DEV_HOSTS and parsed.port == DEV_PORT:
            return TargetKind.DEVELOPMENT
        if (
            host in DEV_HOSTS
            and parsed.scheme in {"postgres", "postgresql"}
            and parsed.port == 15432
            and database == "repair_appliance_dev"
        ):
            return TargetKind.DEVELOPMENT
        return TargetKind.UNKNOWN
    except (TypeError, ValueError):
        return TargetKind.UNKNOWN


def assert_safe_target(
    target: str,
    *,
    app_env: str,
    operation: str = "read",
    approval: ProductionApproval | None = None,
) -> TargetKind:
    kind = classify_target(target)
    environment = app_env.strip().lower()
    action = operation.strip().lower()
    if action not in {"read", "write"}:
        raise TargetSafetyError(f"Unsupported operation: {operation!r}")
    if kind in {TargetKind.UNKNOWN, TargetKind.RETIRED, TargetKind.MARINE_PRODUCTION}:
        raise TargetSafetyError(f"Blocked target classification: {kind.value}")
    if environment == "development":
        if kind is not TargetKind.DEVELOPMENT:
            raise TargetSafetyError(f"Development cannot access {kind.value}")
        return kind
    if environment != "production":
        raise TargetSafetyError(f"Unsupported APP_ENV: {app_env!r}")
    if kind is TargetKind.DEVELOPMENT:
        return kind
    if kind not in {TargetKind.APPLIANCE_PRODUCTION, TargetKind.PRODUCTION_DATABASE}:
        raise TargetSafetyError(
            f"Production target is not Appliance production: {kind.value}"
        )
    if action == "write" and not (approval and approval.complete):
        raise TargetSafetyError("Production write requires every approval factor")
    return kind


def production_approval_from_env(
    *, command_flag: bool, supplied_token: str
) -> ProductionApproval:
    """Build a ProductionApproval from the two env-configured approval factors.

    ALLOW_PRODUCTION_WRITE and PRODUCTION_WRITE_CONFIRMATION are set once by
    whoever administers the box (an infrastructure-level switch), not by the
    worker invocation itself. supplied_token comes from the CLI invocation
    (e.g. --production-token) and must match the configured token exactly.
    """
    return ProductionApproval(
        allow_environment=os.getenv("ALLOW_PRODUCTION_WRITE", "").strip().lower()
        in {"1", "true", "yes"},
        command_flag=command_flag,
        configured_token=os.getenv("PRODUCTION_WRITE_CONFIRMATION", "").strip(),
        supplied_token=supplied_token.strip(),
    )


def assert_configured_development_target(
    target: str,
    *,
    app_env: str,
    operation: str = "read",
    approval: ProductionApproval | None = None,
) -> TargetKind:
    """Allow external dev Postgres only when its identity is predeclared."""
    if operation.strip().lower() not in {"read", "write"}:
        raise TargetSafetyError(f"Unsupported operation: {operation!r}")
    try:
        return assert_safe_target(
            target, app_env=app_env, operation=operation, approval=approval
        )
    except TargetSafetyError:
        pass
    if app_env.strip().lower() != "development":
        raise TargetSafetyError(
            "External development target requires APP_ENV=development"
        )
    parsed = urlparse(target)
    expected = (
        os.getenv("REPAIRBASE_DEV_DB_HOST", "").strip().lower(),
        os.getenv("REPAIRBASE_DEV_DB_NAME", "").strip().lower(),
        os.getenv("REPAIRBASE_DEV_DB_USER", "").strip(),
    )
    if not all(expected):
        raise TargetSafetyError("External development target identity is incomplete")
    actual = (
        (parsed.hostname or "").lower(),
        parsed.path.strip("/").lower(),
        parsed.username or "",
    )
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise TargetSafetyError("External development target must be PostgreSQL")
    if (
        actual[0]
        in {APPLIANCE_PRODUCTION_HOST, MARINE_PRODUCTION_HOST, RETIRED_SUPABASE_HOST}
        or actual[1] in PRODUCTION_DATABASE_MARKERS
    ):
        raise TargetSafetyError("Known production or retired database is blocked")
    if actual != expected:
        raise TargetSafetyError("Development DSN does not match declared identity")
    return TargetKind.DEVELOPMENT
