from __future__ import annotations

import importlib
import sys

import pytest

from config.environment import Settings
from config.clients import GuardedClient, LazyClient
from config.target_safety import ProductionApproval, TargetSafetyError, assert_safe_target


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
    assert assert_safe_target(DEV, app_env="development", operation=operation).value == "development"


@pytest.mark.parametrize("target", [APPLIANCE, MARINE, RETIRED, "not a url", "https://unknown.invalid"])
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
        assert_safe_target(APPLIANCE, app_env="production", operation="write", approval=approval)


def test_fully_approved_production_guard_logic_only():
    approval = ProductionApproval(True, True, "separate-token", "separate-token")
    assert assert_safe_target(APPLIANCE, app_env="production", operation="write", approval=approval).value == "appliance-production"


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
    return Settings(app_env, url, "fake-key", "", False, "", 2.0, 3, "", False, Path("manuals"), Path("logs"), "INFO", "")


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
