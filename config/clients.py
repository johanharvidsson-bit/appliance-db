from __future__ import annotations

from typing import Any, Callable

from supabase import Client, create_client

from config.environment import Settings, load_settings
from config.target_safety import ProductionApproval, assert_safe_target


_client_creation_count = 0
_production_approval = ProductionApproval()


def configure_production_approval(*, command_flag: bool, supplied_token: str, settings: Settings | None = None) -> None:
    global _production_approval
    current = settings or load_settings()
    _production_approval = ProductionApproval(
        allow_environment=current.allow_production_write,
        command_flag=command_flag,
        configured_token=current.production_write_confirmation,
        supplied_token=supplied_token,
    )


class GuardedTable:
    _WRITE_METHODS = {"insert", "update", "upsert", "delete"}

    def __init__(self, builder: Any, settings: Settings):
        self._builder = builder
        self._settings = settings

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._builder, name)
        if name not in self._WRITE_METHODS:
            return attribute

        def guarded(*args: Any, **kwargs: Any) -> Any:
            assert_safe_target(
                self._settings.supabase_url,
                app_env=self._settings.app_env,
                operation="write",
                approval=_production_approval,
            )
            return attribute(*args, **kwargs)

        return guarded


class GuardedClient:
    def __init__(self, client: Client, settings: Settings):
        self._client = client
        self._settings = settings

    def table(self, name: str) -> GuardedTable:
        return GuardedTable(self._client.table(name), self._settings)

    def from_(self, name: str) -> GuardedTable:
        return GuardedTable(self._client.from_(name), self._settings)

    def rpc(self, *args: Any, **kwargs: Any) -> Any:
        assert_safe_target(
            self._settings.supabase_url,
            app_env=self._settings.app_env,
            operation="write",
            approval=_production_approval,
        )
        return self._client.rpc(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def create_postgrest_client(settings: Settings | None = None, *, operation: str = "read") -> GuardedClient:
    global _client_creation_count
    current = (settings or load_settings()).require_postgrest()
    assert_safe_target(current.supabase_url, app_env=current.app_env, operation=operation)
    _client_creation_count += 1
    return GuardedClient(create_client(current.supabase_url, current.supabase_service_key), current)


def client_creation_count() -> int:
    return _client_creation_count


class LazyClient:
    def __init__(self, factory: Callable[[], Client] = create_postgrest_client):
        self._factory = factory
        self._client: Client | None = None

    @property
    def initialized(self) -> bool:
        return self._client is not None

    def get(self) -> Client:
        if self._client is None:
            self._client = self._factory()
        return self._client

    def reset(self) -> None:
        self._client = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.get(), name)
