from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
        if parsed.scheme not in {"http", "https", "postgres", "postgresql"} or not parsed.hostname:
            return TargetKind.UNKNOWN
        host = parsed.hostname.lower()
        if host == RETIRED_SUPABASE_HOST:
            return TargetKind.RETIRED
        if host == MARINE_PRODUCTION_HOST:
            return TargetKind.MARINE_PRODUCTION
        if host == APPLIANCE_PRODUCTION_HOST:
            return TargetKind.APPLIANCE_PRODUCTION
        database = parsed.path.strip("/").lower()
        if parsed.scheme in {"postgres", "postgresql"} and database in PRODUCTION_DATABASE_MARKERS:
            return TargetKind.PRODUCTION_DATABASE
        if host in DEV_HOSTS and parsed.port == DEV_PORT:
            return TargetKind.DEVELOPMENT
        if host in DEV_HOSTS and parsed.scheme in {"postgres", "postgresql"} and parsed.port == 15432 and database == "repair_appliance_dev":
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
        raise TargetSafetyError(f"Production target is not Appliance production: {kind.value}")
    if action == "write" and not (approval and approval.complete):
        raise TargetSafetyError("Production write requires every approval factor")
    return kind
