from __future__ import annotations

from collections.abc import Iterator, Mapping
import json
from pathlib import Path
from typing import Any

from config.clients import LazyClient, create_postgrest_client
from config.environment import load_settings
from config.paths import BASE_DIR


_settings = load_settings()

SUPABASE_URL = _settings.supabase_url
SUPABASE_SERVICE_KEY = _settings.supabase_service_key
SUPABASE_DB_URL = _settings.supabase_db_url
APP_ENV = _settings.app_env
REQUEST_DELAY = _settings.request_delay
MAX_RETRIES = _settings.max_retries
SCRAPE_DO_API_KEY = _settings.scrape_do_api_key
DOWNLOAD_MANUALS = _settings.download_manuals
MANUAL_DIR = _settings.manual_dir
LOG_DIR = _settings.log_dir
LOG_LEVEL = _settings.log_level
TESSERACT_CMD = _settings.tesseract_cmd

supabase = LazyClient()


def get_client():
    return create_postgrest_client(load_settings())


def refresh_client():
    supabase.reset()
    return supabase.get()


def configure_tesseract() -> None:
    if not TESSERACT_CMD:
        return
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


class LazyScraperMapping(Mapping[Any, Any]):
    def __init__(self, section: str, key: str, *, tuple_keys: bool = False, tuple_values: bool = False):
        self.section = section
        self.key = key
        self.tuple_keys = tuple_keys
        self.tuple_values = tuple_values
        self._data: dict[Any, Any] | None = None

    def _load(self) -> dict[Any, Any]:
        if self._data is None:
            raw = json.loads((BASE_DIR / "config/scraper_sites.json").read_text(encoding="utf-8"))[self.section][self.key]
            self._data = {
                tuple(k.split("|")) if self.tuple_keys else k: tuple(v) if self.tuple_values else v
                for k, v in raw.items()
            }
        return self._data

    def __getitem__(self, key: Any) -> Any:
        return self._load()[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())


MANUALSLIB_BRAND_SLUGS = LazyScraperMapping("manualslib", "brand_slugs")
MANUALSLIB_CATEGORY_PATHS = LazyScraperMapping("manualslib", "category_paths")
ESPARES_CONFIG = LazyScraperMapping("espares", "entries", tuple_keys=True, tuple_values=True)
FIXPART_CATEGORY_PATHS = LazyScraperMapping("fixpart", "category_paths")
FIXPART_APPLIANCE_GROUPS = LazyScraperMapping("fixpart", "appliance_groups")
FIXPART_BRAND_NAMES = LazyScraperMapping("fixpart", "brand_names")
APPP_PREFIXES = LazyScraperMapping("appliancepartspros", "prefixes", tuple_keys=True)
APPP_PAGE_URLS = LazyScraperMapping("appliancepartspros", "page_urls", tuple_keys=True)

ACTIVE_BRAND_SLUGS = ["samsung", "lg", "bosch", "whirlpool", "aeg", "electrolux", "siemens", "miele", "ge", "beko", "kitchenaid", "hotpoint"]
ACTIVE_CATEGORY_SLUGS = ["washing-machines", "dryers", "dishwashers", "refrigerators", "freezers", "ovens", "microwaves"]
