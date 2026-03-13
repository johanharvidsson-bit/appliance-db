"""
config/settings.py
Central configuration – loaded once at startup.
All other modules import `settings` and `supabase_client` from here.
"""

import os
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
    """Return a Supabase client using the service role key (full DB access)."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Singleton – import this everywhere
supabase: Client = get_client()

# ── Scraping ───────────────────────────────────────────────────────────────────
REQUEST_DELAY: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))
MAX_RETRIES: int     = int(os.getenv("MAX_RETRIES", "3"))
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

# ── Phase-1 scope (used by scrapers to filter) ─────────────────────────────────
ACTIVE_BRAND_SLUGS    = ["samsung"]
ACTIVE_CATEGORY_SLUGS = [
    "washing-machines",
    "dryers",
    "dishwashers",
    "refrigerators",
    "freezers",
    "ovens",
    "microwaves",
]

# ManualsLib brand slugs (keyed by our brand slug)
MANUALSLIB_BRAND_SLUGS = {
    "samsung":    "samsung",
    "lg":         "lg",
    "bosch":      "bosch",
    "whirlpool":  "whirlpool",
    "aeg":        "aeg",
    "electrolux": "electrolux",
    "siemens":    "siemens",
    "miele":      "miele",
    "ge":         "ge",
    "beko":       "beko",
    "kitchenaid": "kitchenaid",
    "hotpoint":   "hotpoint",
}

# ManualsLib category paths (keyed by our category slug)
MANUALSLIB_CATEGORY_PATHS = {
    "washing-machines": "washing-machines",
    "dryers":           "dryers",
    "dishwashers":      "dishwashers",
    "refrigerators":    "refrigerators",
    "freezers":         "freezers",
    "ovens":            "ranges",
    "microwaves":       "microwave-ovens",
}
