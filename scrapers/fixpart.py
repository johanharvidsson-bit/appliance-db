"""
scrapers/fixpart.py

Enumerates all Samsung washing machine models from FixPart (fixpart.co.uk)
and upserts them as models + product_code rows with market='EU'.

APPROACH:
  FixPart exposes a POST API endpoint /api/appfinder_modelno that returns
  paginated JSON model lists (250 per page, ~36 pages for Samsung washers).
  The endpoint requires a CSRF token obtained from the page, so we use
  Playwright to load the page first, then issue the POST requests from
  within the browser context to inherit the session cookies and token.

  Model code cleaning: FixPart includes variant notes in parentheses,
  e.g. "WW9XT654ALH/S2 (0000 WW9XT654ALH)" — we strip the parenthetical
  and store the canonical code "WW9XT654ALH/S2".

Market: 'EU'

Usage:
    python -m scrapers.fixpart
    python -m scrapers.fixpart --brand samsung --category washing-machines
"""

import re
import argparse
import time
from typing import Optional

from playwright.sync_api import sync_playwright
from loguru import logger
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn

from config.settings import supabase, get_client, FIXPART_CATEGORY_PATHS, FIXPART_APPLIANCE_GROUPS, FIXPART_BRAND_NAMES
from scrapers.base_scraper import upsert_model_and_code, create_scrape_job, start_scrape_job, complete_scrape_job, fail_scrape_job

console = Console()

BASE_URL  = "https://fixpart.co.uk"
MARKET    = "EU"
PAGE_SIZE = 250   # results per API page
DELAY     = 0.4   # seconds between API pages


# ── Model code cleaning ────────────────────────────────────────────────────────

def _clean_code(text: str) -> str:
    """
    Strip parenthetical variant notes from FixPart model text.
    "WW9XT654ALH/S2 (0000 WW9XT654ALH)" → "WW9XT654ALH/S2"
    "B1045AFW/YIA (0000)"                → "B1045AFW/YIA"
    "WW90T986DSH/EN"                     → "WW90T986DSH/EN"
    """
    return text.split("(")[0].strip()


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_brand_id(brand_slug: str) -> Optional[int]:
    res = supabase.table("brands").select("id").eq("slug", brand_slug).single().execute()
    return res.data["id"] if res.data else None


def _get_category_id(category_slug: str) -> Optional[int]:
    res = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()
    return res.data["id"] if res.data else None



def _count_existing_eu_codes(brand_id: int, category_id: int) -> int:
    model_ids = [
        m["id"] for m in
        supabase.table("models").select("id")
        .eq("brand_id", brand_id).eq("category_id", category_id).execute().data or []
    ]
    if not model_ids:
        return 0
    result = supabase.table("product_codes").select("id") \
        .in_("model_id", model_ids[:500]).eq("market", MARKET).execute()
    return len(result.data or [])


# ── FixPart API enumeration ────────────────────────────────────────────────────

def _api_page(page, token: str, pg: int, appliance_group: str, brand_name: str) -> tuple[list[str], int]:
    """
    Fetch one page from the FixPart model API using the browser context.
    Returns (model_text_list, total_pages).
    """
    result = page.evaluate(
        """async ([token, pg, applianceGroup, brand]) => {
            const r = await fetch('/api/appfinder_modelno', {
                method:  'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept':           'application/json',
                    'Content-Type':     'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    applianceGroup: applianceGroup,
                    brand:          brand,
                    productGroup:   '',
                    term:           '',
                    _token:         token,
                    page:           String(pg),
                }).toString(),
            });
            if (!r.ok) return {texts: [], total: 0, status: r.status};
            const data = await r.json();
            return {
                texts: (data.results || []).map(x => x.text),
                total: data.total || 0,
                status: r.status,
            };
        }""",
        [token, pg, appliance_group, brand_name],
    )
    return result.get("texts", []), result.get("total", 0)


def _fetch_all_codes_via_playwright(
    category_url_path: str, appliance_group: str, brand_name: str
) -> list[str]:
    """
    Use Playwright to load the brand/category page, obtain the CSRF token,
    then POST to /api/appfinder_modelno for all pages.
    Returns a deduplicated list of clean model codes.
    """
    raw_texts: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-GB",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Intercept page-1 results from the initial page load (saves one API call)
        first_page_texts: list[str] = []

        def on_response(response):
            if "appfinder_modelno" in response.url:
                try:
                    import json as _json
                    data = _json.loads(response.body())
                    for item in data.get("results", []):
                        first_page_texts.append(item["text"])
                except Exception:
                    pass

        pw_page = ctx.new_page()
        ctx.on("response", on_response)

        logger.info(f"FixPart: loading category page {category_url_path}…")
        pw_page.goto(
            f"{BASE_URL}/{category_url_path}",
            wait_until="networkidle",
            timeout=30_000,
        )
        pw_page.wait_for_timeout(1_500)

        # Obtain CSRF token
        token = pw_page.evaluate(
            "() => { const m = document.querySelector('meta[name=csrf-token]'); return m ? m.content : ''; }"
        )

        if not token:
            logger.warning("FixPart: no CSRF token found — page may not have loaded correctly")
            browser.close()
            return []

        logger.info(f"FixPart: got CSRF token, first-page intercept yielded {len(first_page_texts)} models")

        # If the intercept got page 1, get total from an explicit call; else start at 1
        if first_page_texts:
            raw_texts.extend(first_page_texts)
            _, total_pages = _api_page(pw_page, token, 1, appliance_group, brand_name)
            start_pg = 2
        else:
            texts, total_pages = _api_page(pw_page, token, 1, appliance_group, brand_name)
            raw_texts.extend(texts)
            start_pg = 2

        if total_pages == 0:
            total_pages = 36  # fallback

        logger.info(f"FixPart: {total_pages} pages to fetch, starting from page {start_pg}")

        for pg in range(start_pg, total_pages + 1):
            time.sleep(DELAY)
            texts, _ = _api_page(pw_page, token, pg, appliance_group, brand_name)
            if not texts:
                logger.warning(f"FixPart: page {pg} returned no results — stopping")
                break
            raw_texts.extend(texts)
            logger.debug(f"FixPart: page {pg}/{total_pages} — {len(texts)} models (total so far: {len(raw_texts)})")

        browser.close()

    seen: set[str] = set()
    codes: list[str] = []
    for text in raw_texts:
        code = _clean_code(text)
        if code and code not in seen:
            seen.add(code)
            codes.append(code)

    return codes


# ── Main scraper ───────────────────────────────────────────────────────────────

def scrape_all(brand_slug: str = "samsung", category_slug: str = "washing-machines") -> int:
    """
    Enumerate all models for a brand/category from FixPart and upsert
    them as models + EU product_codes.
    Returns count of new product_code rows inserted.
    """
    category_path = FIXPART_CATEGORY_PATHS.get(category_slug)
    appliance_group = FIXPART_APPLIANCE_GROUPS.get(category_slug)
    brand_name = FIXPART_BRAND_NAMES.get(brand_slug)

    if not category_path or not appliance_group:
        logger.warning(
            f"FixPart: no category config for {category_slug} — skipping. "
            f"Add an entry to FIXPART_CATEGORY_PATHS and FIXPART_APPLIANCE_GROUPS in config/settings.py."
        )
        return 0
    if not brand_name:
        logger.warning(
            f"FixPart: no brand name config for {brand_slug} — skipping. "
            f"Add an entry to FIXPART_BRAND_NAMES in config/settings.py."
        )
        return 0

    category_url_path = f"{category_path}/{brand_slug}"

    brand_id    = _get_brand_id(brand_slug)
    category_id = _get_category_id(category_slug)
    if not brand_id or not category_id:
        logger.error(f"Brand '{brand_slug}' or category '{category_slug}' not found in DB")
        return 0

    existing = _count_existing_eu_codes(brand_id, category_id)
    logger.info(f"FixPart: {existing} EU product_codes already in DB")

    job_id = create_scrape_job("product_code", f"{BASE_URL}/{category_url_path}")
    start_scrape_job(job_id)

    try:
        codes = _fetch_all_codes_via_playwright(category_url_path, appliance_group, brand_name)
        logger.info(f"FixPart: fetched {len(codes)} unique model codes from API")
    except Exception as exc:
        fail_scrape_job(job_id, str(exc))
        logger.error(f"FixPart: enumeration failed: {exc}")
        return 0

    inserted = 0
    skipped  = 0
    # Refresh Supabase connection every N models to avoid HTTP/2 connection limits
    RECONNECT_EVERY = 500

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("FixPart upsert", total=len(codes))

        for i, code in enumerate(codes):
            if i > 0 and i % RECONNECT_EVERY == 0:
                from config.settings import refresh_client
                refresh_client()
                logger.debug(f"FixPart: refreshed Supabase connection at model {i}")

            if upsert_model_and_code(brand_id, category_id, code, MARKET, match_existing_only=True):
                inserted += 1
            else:
                skipped += 1
            progress.advance(task)

    complete_scrape_job(job_id, parsed_json={"inserted": inserted, "skipped": skipped, "total": len(codes)})
    console.print(
        f"\n[bold]FixPart done:[/bold] {inserted} new EU product_codes inserted, "
        f"{skipped} already existed ({len(codes)} total codes fetched)"
    )
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixPart Samsung model enumerator")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    args = parser.parse_args()
    scrape_all(args.brand, args.category)
