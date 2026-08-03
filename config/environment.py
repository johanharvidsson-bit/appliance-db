from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import dotenv_values

from config.paths import BASE_DIR, resolve_project_path


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    supabase_url: str
    supabase_service_key: str
    supabase_db_url: str
    allow_production_write: bool
    production_write_confirmation: str
    request_delay: float
    max_retries: int
    scrape_do_api_key: str
    download_manuals: bool
    manual_dir: Path
    log_dir: Path
    log_level: str
    tesseract_cmd: str

    def require_postgrest(self) -> "Settings":
        missing = [name for name, value in (("SUPABASE_URL", self.supabase_url), ("SUPABASE_SERVICE_KEY", self.supabase_service_key)) if not value]
        if missing:
            raise RuntimeError("Missing required settings: " + ", ".join(missing))
        return self

    def require_database(self) -> "Settings":
        if not self.supabase_db_url:
            raise RuntimeError("Missing required setting: SUPABASE_DB_URL")
        return self


def load_settings(env_file: Path | None = None) -> Settings:
    source = {k: str(v) for k, v in dotenv_values(env_file or BASE_DIR / ".env").items() if v is not None}
    source.update(os.environ)
    get = source.get
    return Settings(
        app_env=(get("APP_ENV") or "development").strip().lower(),
        supabase_url=(get("SUPABASE_URL") or "").strip(),
        supabase_service_key=(get("SUPABASE_SERVICE_KEY") or "").strip(),
        supabase_db_url=(get("SUPABASE_DB_URL") or "").strip(),
        allow_production_write=_bool(get("ALLOW_PRODUCTION_WRITE")),
        production_write_confirmation=(get("PRODUCTION_WRITE_CONFIRMATION") or "").strip(),
        request_delay=float(get("REQUEST_DELAY_SECONDS") or "2.0"),
        max_retries=int(get("MAX_RETRIES") or "3"),
        scrape_do_api_key=(get("SCRAPE_DO_API_KEY") or get("SCRAPE_DO_API_Key2") or get("SCRAPE_DO_API_Key") or "").strip(),
        download_manuals=_bool(get("DOWNLOAD_MANUALS"), True),
        manual_dir=resolve_project_path(get("MANUAL_DOWNLOAD_DIR") or "", "data/manuals"),
        log_dir=resolve_project_path(get("LOG_DIR") or "", "logs"),
        log_level=(get("LOG_LEVEL") or "INFO").strip(),
        tesseract_cmd=(get("TESSERACT_CMD") or "").strip(),
    )
