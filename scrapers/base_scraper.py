"""
scrapers/base_scraper.py
Shared HTTP logic: rate limiting, retries, rotating headers,
scrape_job logging to Supabase.
"""

import time
import random
from datetime import datetime, timezone
from typing import Optional

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

from config.settings import supabase, REQUEST_DELAY, MAX_RETRIES

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
