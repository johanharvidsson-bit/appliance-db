"""
scrapers/appliancepartspros.py

Enumerates Samsung washing machine models from AppliancePartsPros (US market)
and upserts them as models + product_code rows with market='US'.

APPROACH:
  AppliancePartsPros does not have a model listing page but exposes a
  search autocomplete endpoint (/search-autocomplete.ashx?ajax=1&q=...) that
  returns up to 5 Samsung model suggestions per prefix query.

  We use a BFS over known Samsung US washer model prefixes (WF, WA, WV, WD)
  starting at 3-character depth.  Any prefix that saturates the 5-result cap
  is expanded one character further until results are <5 or depth=8.

  The endpoint is accessible directly via httpx (no JS required).

  Model page URL: https://www.appliancepartspros.com/parts-for-samsung-{slug}.html

Market: 'US'

Note: US model codes differ from EU/GB codes for the same physical machine.

Usage:
    python -m scrapers.appliancepartspros
    python -m scrapers.appliancepartspros --brand samsung --category washing-machines
"""

import re
import argparse
import time
from collections import deque
from typing import Optional

import httpx
from loguru import logger
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn

from config.settings import supabase, REQUEST_DELAY, APPP_PREFIXES, APPP_PAGE_URLS
from scrapers.base_scraper import upsert_model_and_code, create_scrape_job, start_scrape_job, complete_scrape_job, fail_scrape_job

console = Console()

BASE_URL  = "https://www.appliancepartspros.com"
MARKET    = "US"
AC_URL    = f"{BASE_URL}/search-autocomplete.ashx"
MAX_DEPTH = 8   # maximum prefix length for BFS
MAX_CALLS = 4_000
DELAY     = 0.12  # seconds between autocomplete calls

_BFS_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_brand_id(brand_slug: str) -> Optional[int]:
    res = supabase.table("brands").select("id").eq("slug", brand_slug).single().execute()
    return res.data["id"] if res.data else None


def _get_category_id(category_slug: str) -> Optional[int]:
    res = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()
    return res.data["id"] if res.data else None




# ── Autocomplete enumeration ───────────────────────────────────────────────────

def _query_autocomplete(client: httpx.Client, prefix: str, brand_slug: str) -> tuple[list[str], int]:
    """
    Query the autocomplete API for `prefix`.
    Returns (brand_model_codes, total_result_count).
    """
    try:
        r = client.get(AC_URL, params={"ajax": "1", "q": prefix})
        all_models = re.findall(r"data-q=([^>]+)>", r.text)
        brand_models = []
        for m in all_models:
            slug = re.sub(r"[^a-z0-9]+", "-", m.lower()).strip("-")
            if f"parts-for-{brand_slug}-{slug}" in r.text.lower():
                brand_models.append(m)
        return brand_models, len(all_models)
    except Exception as exc:
        logger.debug(f"AppliancePartsPros autocomplete error for {prefix!r}: {exc}")
        return [], 0


def _enumerate_models(brand_slug: str, root_prefixes: list[str], page_url: str, limit: int = 0) -> list[str]:
    """
    BFS over model prefixes via autocomplete API.
    Returns a deduplicated list of model codes.
    If limit > 0, stops once that many codes have been collected.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer":    f"{BASE_URL}{page_url}",
        "Accept":     "*/*",
        "X-Requested-With": "XMLHttpRequest",
    }
    client = httpx.Client(
        timeout=15,
        follow_redirects=True,
        headers=headers,
        limits=httpx.Limits(max_connections=3),
    )

    all_codes: set[str] = set()
    seen_prefixes: set[str] = set()
    calls = 0

    # Start BFS from 3-character prefixes (2-char roots + one expansion)
    queue: deque[str] = deque()
    for root in root_prefixes:
        if len(root) >= 3:
            queue.append(root)
        else:
            for c in _BFS_CHARS:
                queue.append(root + c)

    while queue and calls < MAX_CALLS:
        if limit > 0 and len(all_codes) >= limit:
            break

        prefix = queue.popleft()
        if prefix in seen_prefixes or len(prefix) > MAX_DEPTH:
            continue
        seen_prefixes.add(prefix)

        models, total = _query_autocomplete(client, prefix, brand_slug)
        calls += 1
        time.sleep(DELAY)

        for m in models:
            all_codes.add(m)

        # Saturated result cap → drill deeper
        if total >= 5 and len(prefix) < MAX_DEPTH:
            for c in _BFS_CHARS:
                nxt = prefix + c
                if nxt not in seen_prefixes:
                    queue.append(nxt)

    client.close()
    codes = sorted(all_codes)
    if limit > 0:
        codes = codes[:limit]
    logger.info(
        f"AppliancePartsPros: BFS complete — {calls} API calls, "
        f"{len(codes)} unique {brand_slug} models found"
    )
    return codes


# ── Main scraper ───────────────────────────────────────────────────────────────

def scrape_all(brand_slug: str = "samsung", category_slug: str = "washing-machines", limit: int = 0) -> int:
    """
    Enumerate all models for a brand/category from AppliancePartsPros and
    upsert them as models + US product_codes.
    If limit > 0, stop after collecting that many codes.
    Returns count of new product_code rows inserted.
    """
    root_prefixes = APPP_PREFIXES.get((brand_slug, category_slug))
    if not root_prefixes:
        logger.warning(
            f"AppliancePartsPros: no prefix config for {brand_slug}/{category_slug} — skipping. "
            f"Add an entry to APPP_PREFIXES in config/settings.py."
        )
        return 0

    page_url = APPP_PAGE_URLS.get(
        (brand_slug, category_slug),
        f"/{brand_slug}-{category_slug.replace('-', '')}-parts.html",
    )

    brand_id    = _get_brand_id(brand_slug)
    category_id = _get_category_id(category_slug)
    if not brand_id or not category_id:
        logger.error(f"Brand '{brand_slug}' or category '{category_slug}' not found in DB")
        return 0

    job_id = create_scrape_job("product_code", f"{BASE_URL}{page_url}")
    start_scrape_job(job_id)

    console.print(f"[bold blue]AppliancePartsPros:[/bold blue] running BFS autocomplete enumeration for {brand_slug}/{category_slug}…")

    try:
        codes = _enumerate_models(brand_slug, root_prefixes, page_url, limit=limit)
        logger.info(f"AppliancePartsPros: {len(codes)} unique model codes collected")
    except Exception as exc:
        fail_scrape_job(job_id, str(exc))
        logger.error(f"AppliancePartsPros: enumeration failed: {exc}")
        return 0

    inserted = 0
    skipped  = 0

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("AppliancePartsPros upsert", total=len(codes))

        for code in codes:
            if upsert_model_and_code(brand_id, category_id, code, MARKET, match_existing_only=True):
                inserted += 1
            else:
                skipped += 1
            progress.advance(task)

    complete_scrape_job(job_id, parsed_json={"inserted": inserted, "skipped": skipped, "total": len(codes)})
    console.print(
        f"\n[bold]AppliancePartsPros done:[/bold] {inserted} new US product_codes inserted, "
        f"{skipped} already existed ({len(codes)} total codes fetched)"
    )
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AppliancePartsPros Samsung model enumerator")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--limit",    type=int, default=0, help="Stop after N codes (0 = unlimited)")
    args = parser.parse_args()
    scrape_all(args.brand, args.category, limit=args.limit)
