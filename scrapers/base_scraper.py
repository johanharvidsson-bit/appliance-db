"""
scrapers/base_scraper.py
Shared HTTP logic: rate limiting, retries, rotating headers,
scrape_job logging to Supabase.
"""

import time
import random
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from loguru import logger

import re
from typing import Optional

from config.settings import supabase, REQUEST_DELAY, MAX_RETRIES, SCRAPE_DO_API_KEY

# ── User-agent pool ────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
    "Gecko/20100101 Firefox/124.0",
]


def _headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }


# ── HTTP client (shared, connection pooling) ───────────────────────────────────
_client = httpx.Client(
    timeout=30,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
)


# ── Core fetch with retry ──────────────────────────────────────────────────────
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=True,
)
def fetch(url: str, delay: float = REQUEST_DELAY) -> httpx.Response:
    """
    Fetch a URL with rate limiting and retries.
    Raises httpx.HTTPStatusError for 4xx/5xx responses.
    """
    time.sleep(delay + random.uniform(0, 1.0))   # jitter
    response = _client.get(url, headers=_headers())
    response.raise_for_status()
    logger.debug(f"GET {url} → {response.status_code}")
    return response


def fetch_soup(url: str, delay: float = REQUEST_DELAY) -> BeautifulSoup:
    """Fetch and parse HTML into BeautifulSoup."""
    resp = fetch(url, delay)
    return BeautifulSoup(resp.text, "lxml")


_IP_BLOCK_MARKER = "Your ip  blocked"


def fetch_soup_unblocked(url: str) -> BeautifulSoup:
    """
    Fetch a page that may be IP-blocked.
    Tries a direct request first; if the response contains the ManualsLib
    IP-block message, retries via scrape.do (if API key is configured).
    Raises RuntimeError if both attempts fail or no API key is available.
    """
    import urllib.parse

    # 1. Direct attempt (no delay — caller controls pacing)
    try:
        resp = _client.get(url, headers=_headers())
        if _IP_BLOCK_MARKER not in resp.text:
            return BeautifulSoup(resp.text, "lxml")
        logger.debug(f"IP-blocked on direct fetch: {url}")
    except Exception as e:
        logger.debug(f"Direct fetch failed ({url}): {e}")

    # 2. Fallback via scrape.do
    if not SCRAPE_DO_API_KEY:
        raise RuntimeError(f"IP-blocked and SCRAPE_DO_API_KEY is not set — cannot fetch {url}")

    proxy_url = f"https://api.scrape.do/?token={SCRAPE_DO_API_KEY}&url={urllib.parse.quote(url, safe='')}"
    logger.debug(f"Retrying via scrape.do: {url}")
    try:
        resp = httpx.get(proxy_url, timeout=30)
        resp.raise_for_status()
        if _IP_BLOCK_MARKER in resp.text:
            raise RuntimeError(f"scrape.do also returned IP-block response for {url}")
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        raise RuntimeError(f"scrape.do fetch failed for {url}: {e}") from e


def download_file(url: str, dest_path) -> bool:
    """
    Download a binary file (PDF) to dest_path.
    Returns True on success, False on failure.
    """
    try:
        resp = fetch(url, delay=REQUEST_DELAY)
        with open(dest_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"Downloaded {url} → {dest_path}")
        return True
    except Exception as e:
        logger.error(f"Download failed {url}: {e}")
        return False


# ── Shared model+product_code upsert ─────────────────────────────────────────

def upsert_model_and_code(
    brand_id: int,
    category_id: int,
    code: str,
    market: Optional[str],
    match_existing_only: bool = False,
) -> bool:
    """
    Ensure a models row exists for `code`, then add a product_codes row for
    the given market.  Returns True if a new product_code was inserted.

    Used by all marketplace scrapers (eSpares, FixPart, AppliancePartsPros).
    base_model is derived here so it is always set consistently.

    match_existing_only=True (used by marketplace scrapers): never create a new
    model row.  Instead, try to link the code to an existing canonical model by:
      1. Exact name match
      2. base_model prefix match (e.g. "WAK20200GB/01" -> model "WAK20200IR")
    If no match is found, the code is silently skipped.  This prevents
    marketplace scrapers from polluting the models table with stub rows.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-")
    base_model = code.split("/")[0].strip()

    # 1. Try exact name match
    res = (
        supabase.table("models")
        .select("id")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .eq("name", code)
        .execute()
    )
    if res.data:
        model_id = res.data[0]["id"]
    elif match_existing_only:
        # 2. Try base_model prefix match (strip variant suffix /XX from code)
        if "/" in code:
            by_base = (
                supabase.table("models")
                .select("id")
                .eq("brand_id", brand_id)
                .eq("category_id", category_id)
                .eq("base_model", base_model)
                .limit(1)
                .execute()
            )
            if by_base.data:
                model_id = by_base.data[0]["id"]
            else:
                logger.debug(f"upsert_model_and_code: no existing model for {code!r}, skipping")
                return False
        else:
            logger.debug(f"upsert_model_and_code: no existing model for {code!r}, skipping")
            return False
    else:
        # 2. Insert; fall back to slug lookup on constraint violation
        try:
            ins = supabase.table("models").insert({
                "brand_id":    brand_id,
                "category_id": category_id,
                "name":        code,
                "slug":        slug,
                "base_model":  base_model,
                "scrape_status": "pending",
            }).execute()
            model_id = ins.data[0]["id"]
        except Exception:
            by_slug = (
                supabase.table("models")
                .select("id")
                .eq("brand_id", brand_id)
                .eq("category_id", category_id)
                .eq("slug", slug)
                .single()
                .execute()
            )
            if not by_slug.data:
                logger.warning(f"upsert_model_and_code: could not find or create model {code!r}")
                return False
            model_id = by_slug.data["id"]

    # 3. Idempotent product_code insert
    if market:
        existing = (
            supabase.table("product_codes")
            .select("id")
            .eq("model_id", model_id)
            .eq("market", market)
            .execute()
        )
        if existing.data:
            return False

    supabase.table("product_codes").upsert(
        {
            "model_id":      model_id,
            "code":          code,
            "market":        market,
            "scrape_status": "done",
        },
        on_conflict="code",
        ignore_duplicates=True,
    ).execute()
    return True


# ── scrape_jobs table helpers ─────────────────────────────────────────────────

def create_scrape_job(
    target_type: str,
    source_url: str,
    target_id: Optional[int] = None,
) -> int:
    """Insert a queued scrape_job and return its id."""
    row = (
        supabase.table("scrape_jobs")
        .insert({
            "target_type": target_type,
            "target_id":   target_id,
            "source_url":  source_url,
            "job_status":  "queued",
        })
        .execute()
    )
    job_id = row.data[0]["id"]
    logger.debug(f"scrape_job created id={job_id} type={target_type} url={source_url}")
    return job_id


def start_scrape_job(job_id: int) -> None:
    supabase.table("scrape_jobs").update({
        "job_status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()


def complete_scrape_job(
    job_id: int,
    parsed_json: Optional[dict] = None,
    raw_data: Optional[str] = None,
) -> None:
    supabase.table("scrape_jobs").update({
        "job_status":   "done",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "parsed_json":  parsed_json,
        "raw_data":     raw_data[:5000] if raw_data else None,  # cap stored raw
    }).eq("id", job_id).execute()


def fail_scrape_job(job_id: int, error: str) -> None:
    # increment retry_count and set status
    current = (
        supabase.table("scrape_jobs")
        .select("retry_count")
        .eq("id", job_id)
        .single()
        .execute()
    )
    retry_count = (current.data or {}).get("retry_count", 0) + 1
    status = "failed" if retry_count >= 3 else "queued"

    supabase.table("scrape_jobs").update({
        "job_status":   status,
        "error_log":    str(error)[:2000],
        "retry_count":  retry_count,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()
    logger.warning(f"scrape_job id={job_id} failed (attempt {retry_count}): {error}")
