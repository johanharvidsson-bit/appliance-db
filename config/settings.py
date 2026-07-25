"""
config/settings.py
Central configuration – loaded once at startup.
All other modules import `settings` and `supabase_client` from here.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from loguru import logger

# ── Load .env ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ── Supabase ───────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]

def get_client() -> Client:
    """Return a new Supabase client using the service role key (full DB access)."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# Module-level singleton — import `supabase` for normal use.
# For long-running loops that hit connection limits, call refresh_client()
# instead of `global supabase; supabase = get_client()` inside each module.
supabase: Client = get_client()


def refresh_client() -> Client:
    """
    Replace the module-level Supabase singleton with a fresh connection.
    Call this every N iterations in long-running scrape loops to avoid
    HTTP/2 connection-limit errors.

    Usage:
        from config.settings import refresh_client
        refresh_client()   # subsequent calls to `supabase` use the new client
    """
    global supabase
    supabase = get_client()
    # Also refresh the reference held by base_scraper and any other module
    # that imported `supabase` directly — they must re-import after this call,
    # so scrapers should use `from config.settings import supabase` at call
    # sites rather than binding it once at module level.
    import scrapers.base_scraper as _bs
    _bs.supabase = supabase
    return supabase

# ── Scraping ───────────────────────────────────────────────────────────────────
REQUEST_DELAY: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))
MAX_RETRIES: int     = int(os.getenv("MAX_RETRIES", "3"))
SCRAPE_DO_API_KEY: str = os.getenv("SCRAPE_DO_API_Key2") or os.getenv("SCRAPE_DO_API_Key", "")
DOWNLOAD_MANUALS: bool = os.getenv("DOWNLOAD_MANUALS", "true").lower() == "true"
MANUAL_DIR: Path     = BASE_DIR / os.getenv("MANUAL_DOWNLOAD_DIR", "data/manuals")
MANUAL_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.add(
    LOG_DIR / "scraper_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="{time:HH:mm:ss} | {level:<8} | {name}:{line} – {message}",
)

# ── Tesseract (OCR) ────────────────────────────────────────────────────────────
import pytesseract
pytesseract.pytesseract.tesseract_cmd = os.getenv(
    "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# ── Phase-1 scope (used by scrapers to filter) ─────────────────────────────────
ACTIVE_BRAND_SLUGS    = [
    "samsung", "lg", "bosch", "whirlpool", "aeg",
    "electrolux", "siemens", "miele", "ge", "beko",
    "kitchenaid", "hotpoint",
]
ACTIVE_CATEGORY_SLUGS = [
    "washing-machines",
    "dryers",
    "dishwashers",
    "refrigerators",
    "freezers",
    "ovens",
    "microwaves",
]

# ── Scraper site configuration (loaded from JSON) ──────────────────────────────
# Edit config/scraper_sites.json to add new brands, categories, or sites.
# Tuple-keyed dicts use "brand|category" string keys in the JSON file.

def _load_scraper_config() -> dict:
    cfg_path = BASE_DIR / "config" / "scraper_sites.json"
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)

_SC = _load_scraper_config()

# ManualsLib
MANUALSLIB_BRAND_SLUGS:    dict[str, str] = _SC["manualslib"]["brand_slugs"]
MANUALSLIB_CATEGORY_PATHS: dict[str, str] = _SC["manualslib"]["category_paths"]

# eSpares: (brand, category) -> (espares_brand, espares_category, path_id)
ESPARES_CONFIG: dict[tuple[str, str], tuple[str, str, str]] = {
    tuple(k.split("|")): tuple(v)  # type: ignore[misc]
    for k, v in _SC["espares"]["entries"].items()
}

# FixPart
FIXPART_CATEGORY_PATHS:   dict[str, str] = _SC["fixpart"]["category_paths"]
FIXPART_APPLIANCE_GROUPS: dict[str, str] = _SC["fixpart"]["appliance_groups"]
FIXPART_BRAND_NAMES:      dict[str, str] = _SC["fixpart"]["brand_names"]

# AppliancePartsPros: (brand, category) -> [prefixes] / url_path
APPP_PREFIXES: dict[tuple[str, str], list[str]] = {
    tuple(k.split("|")): v  # type: ignore[misc]
    for k, v in _SC["appliancepartspros"]["prefixes"].items()
}
APPP_PAGE_URLS: dict[tuple[str, str], str] = {
    tuple(k.split("|")): v  # type: ignore[misc]
    for k, v in _SC["appliancepartspros"]["page_urls"].items()
}
