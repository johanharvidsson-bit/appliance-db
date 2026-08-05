from __future__ import annotations

import importlib
import sys

import pytest

from config.environment import Settings
from config.clients import GuardedClient, LazyClient
from config.target_safety import (
    ProductionApproval,
    TargetSafetyError,
    assert_configured_development_target,
    assert_safe_target,
    production_approval_from_env,
)


def test_declared_external_development_database_is_exact_match(monkeypatch):
    monkeypatch.setenv("REPAIRBASE_DEV_DB_HOST", "pooler.dev.example")
    monkeypatch.setenv("REPAIRBASE_DEV_DB_NAME", "repairbase_dev")
    monkeypatch.setenv("REPAIRBASE_DEV_DB_USER", "worker_dev")
    dsn = "postgresql://worker_dev:secret@pooler.dev.example:5432/repairbase_dev"
    assert (
        assert_configured_development_target(dsn, app_env="development").value
        == "development"
    )


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://wrong:secret@pooler.dev.example:5432/repairbase_dev",
        "postgresql://worker_dev:secret@other.example:5432/repairbase_dev",
        "postgresql://worker_dev:secret@pooler.dev.example:5432/other",
    ],
)
def test_external_development_database_identity_mismatch_blocks(monkeypatch, dsn):
    monkeypatch.setenv("REPAIRBASE_DEV_DB_HOST", "pooler.dev.example")
    monkeypatch.setenv("REPAIRBASE_DEV_DB_NAME", "repairbase_dev")
    monkeypatch.setenv("REPAIRBASE_DEV_DB_USER", "worker_dev")
    with pytest.raises(TargetSafetyError, match="does not match"):
        assert_configured_development_target(dsn, app_env="development")


def test_external_development_database_needs_complete_declaration(monkeypatch):
    for name in (
        "REPAIRBASE_DEV_DB_HOST",
        "REPAIRBASE_DEV_DB_NAME",
        "REPAIRBASE_DEV_DB_USER",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(TargetSafetyError, match="identity is incomplete"):
        assert_configured_development_target(
            "postgresql://worker:secret@pooler.dev.example/db",
            app_env="development",
        )


DEV = "http://127.0.0.1:18080"
APPLIANCE = "https://api.appliancerepairbase.com"
MARINE = "https://api.marinerepairbase.com"
RETIRED = "https://jqepafrexisjmzoefvpr.supabase.co"


def test_import_settings_has_no_files_clients_or_logging(tmp_path, monkeypatch):
    monkeypatch.setenv("REPAIRBASE_BASE_DIR", str(tmp_path))
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    before = set(tmp_path.iterdir())
    for name in ["config.settings", "config.paths", "config.environment"]:
        sys.modules.pop(name, None)
    module = importlib.import_module("config.settings")
    assert set(tmp_path.iterdir()) == before
    assert not module.supabase.initialized


def test_client_is_lazy():
    calls = []
    marker = object()
    lazy = LazyClient(lambda: calls.append(True) or marker)  # type: ignore[arg-type]
    assert not lazy.initialized
    assert calls == []
    assert lazy.get() is marker
    assert calls == [True]


@pytest.mark.parametrize("operation", ["read", "write"])
def test_development_target_allowed(operation):
    assert (
        assert_safe_target(DEV, app_env="development", operation=operation).value
        == "development"
    )


@pytest.mark.parametrize(
    "target", [APPLIANCE, MARINE, RETIRED, "not a url", "https://unknown.invalid"]
)
def test_unsafe_development_targets_blocked(target):
    with pytest.raises(TargetSafetyError):
        assert_safe_target(target, app_env="development")


@pytest.mark.parametrize(
    "approval",
    [
        None,
        ProductionApproval(False, True, "token", "token"),
        ProductionApproval(True, False, "token", "token"),
        ProductionApproval(True, True, "", "token"),
        ProductionApproval(True, True, "token", ""),
        ProductionApproval(True, True, "token-a", "token-b"),
    ],
)
def test_production_write_missing_factor_blocks(approval):
    with pytest.raises(TargetSafetyError):
        assert_safe_target(
            APPLIANCE, app_env="production", operation="write", approval=approval
        )


def test_fully_approved_production_guard_logic_only():
    approval = ProductionApproval(True, True, "separate-token", "separate-token")
    assert (
        assert_safe_target(
            APPLIANCE, app_env="production", operation="write", approval=approval
        ).value
        == "appliance-production"
    )


class FakeBuilder:
    def select(self, *_args, **_kwargs):
        return "selected"

    def update(self, *_args, **_kwargs):
        return "updated"


class FakeClient:
    def table(self, _name):
        return FakeBuilder()


def fake_settings(url: str, app_env: str) -> Settings:
    from pathlib import Path

    return Settings(
        app_env,
        url,
        "fake-key",
        "",
        False,
        "",
        2.0,
        3,
        "",
        False,
        Path("manuals"),
        Path("logs"),
        "INFO",
        "",
    )


def test_guarded_client_allows_read_without_network():
    guarded = GuardedClient(FakeClient(), fake_settings(APPLIANCE, "production"))  # type: ignore[arg-type]
    assert guarded.table("models").select("id") == "selected"


def test_guarded_client_blocks_unapproved_production_mutation_without_network():
    guarded = GuardedClient(FakeClient(), fake_settings(APPLIANCE, "production"))  # type: ignore[arg-type]
    with pytest.raises(TargetSafetyError):
        guarded.table("models").update({"name": "blocked"})


def test_guarded_client_allows_development_mutation_without_network():
    guarded = GuardedClient(FakeClient(), fake_settings(DEV, "development"))  # type: ignore[arg-type]
    assert guarded.table("models").update({"name": "dev"}) == "updated"


def test_production_approval_from_env_requires_both_factors_to_match(monkeypatch):
    monkeypatch.delenv("ALLOW_PRODUCTION_WRITE", raising=False)
    monkeypatch.delenv("PRODUCTION_WRITE_CONFIRMATION", raising=False)
    assert not production_approval_from_env(
        command_flag=True, supplied_token="anything"
    ).complete

    monkeypatch.setenv("ALLOW_PRODUCTION_WRITE", "true")
    monkeypatch.setenv("PRODUCTION_WRITE_CONFIRMATION", "the-real-token")
    assert not production_approval_from_env(
        command_flag=True, supplied_token="wrong-token"
    ).complete
    assert not production_approval_from_env(
        command_flag=False, supplied_token="the-real-token"
    ).complete
    assert production_approval_from_env(
        command_flag=True, supplied_token="the-real-token"
    ).complete


def test_assert_configured_development_target_accepts_a_complete_production_approval(
    monkeypatch,
):
    monkeypatch.setenv("ALLOW_PRODUCTION_WRITE", "true")
    monkeypatch.setenv("PRODUCTION_WRITE_CONFIRMATION", "the-real-token")
    approval = production_approval_from_env(
        command_flag=True, supplied_token="the-real-token"
    )
    # TEST-NET-3 (RFC 5737): non-routable, so this can never reach a real host;
    # the "appliancedb" database name alone is enough to classify as production.
    kind = assert_configured_development_target(
        "postgresql://u:p@203.0.113.1:5432/appliancedb",
        app_env="production",
        operation="write",
        approval=approval,
    )
    assert kind.value == "production-database"
