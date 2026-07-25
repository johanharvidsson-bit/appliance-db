"""
scrapers/espares.py

Enumerates all Samsung washing machine models from eSpares (espares.co.uk)
and upserts them as models + product_code rows with market='GB'.

APPROACH:
  eSpares lists Samsung washing machine models on a paginated catalogue page
  (5 pages × 20 models = ~100 models). We use Playwright with stealth
  settings to bypass CloudFront bot detection.

  Model page URL pattern (verified 2026-03-15):
    https://www.espares.co.uk/washing-machine/{slug}/catalogue.pl?shop=samsung&path=127481&model_ref={id}

Market: 'GB'

Usage:
    python -m scrapers.espares
    python -m scrapers.espares --brand samsung --category washing-machines
"""

import re
import argparse
from typing import Optional

from playwright.sync_api import sync_playwright
from loguru import logger
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn

from config.settings import supabase, get_client, ESPARES_CONFIG
from scrapers.base_scraper import upsert_model_and_code, create_scrape_job, start_scrape_job, complete_scrape_job, fail_scrape_job

console = Console()

BASE_URL = "https://www.espares.co.uk"
MARKET   = "GB"


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_brand_id(brand_slug: str) -> Optional[int]:
    res = supabase.table("brands").select("id").eq("slug", brand_slug).single().execute()
    return res.data["id"] if res.data else None


def _get_category_id(category_slug: str) -> Optional[int]:
    res = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()
    return res.data["id"] if res.data else None


# ── eSpares enumeration ────────────────────────────────────────────────────────

def _fetch_all_codes_via_playwright(models_url: str, category_slug: str) -> list[str]:
    """
    Use Playwright with stealth settings to enumerate all models for a brand/category
    from eSpares' paginated catalogue listing.
    Returns a deduplicated list of model name strings.
    """
    codes: list[str] = []
    seen:  set[str]  = set()

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
        page = ctx.new_page()

        # Build a URL selector that matches the eSpares category path for model links
        # e.g. for "washing-machine" → href contains "/washing-machine/"
        espares_cat = category_slug  # already the eSpares-format slug from config

        pg = 1
        while True:
            url = models_url if pg == 1 else f"{models_url}&m_page={pg}"
            logger.debug(f"eSpares: fetching model page {pg}: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            except Exception as exc:
                logger.warning(f"eSpares: page {pg} load error: {exc} — stopping")
                break
            page.wait_for_timeout(500)

            links = page.query_selector_all(
                f'a[href*="/{espares_cat}/"][href*="model_ref="]'
            )
            if not links:
                break

            page_codes = 0
            for link in links:
                text = link.inner_text().strip()
                if text and text not in seen:
                    seen.add(text)
                    codes.append(text)
                    page_codes += 1

            logger.debug(f"eSpares: page {pg} → {page_codes} new codes ({len(codes)} total)")

            # Check for a next page link
            next_link = page.query_selector(f'a[href*="m_page={pg + 1}"]')
            if not next_link:
                break
            pg += 1

        browser.close()

    return codes


# ── Main scraper ───────────────────────────────────────────────────────────────

def scrape_all(brand_slug: str = "samsung", category_slug: str = "washing-machines") -> int:
    """
    Enumerate all models for a brand/category from eSpares and upsert
    them as models + GB product_codes.
    Returns count of new product_code rows inserted.
    """
    cfg = ESPARES_CONFIG.get((brand_slug, category_slug))
    if not cfg:
        logger.warning(
            f"eSpares: no config for {brand_slug}/{category_slug} — skipping. "
            f"Add an entry to ESPARES_CONFIG in config/settings.py."
        )
        return 0

    espares_brand, espares_category, espares_path_id = cfg
    models_url = (
        f"{BASE_URL}/{espares_brand}/{espares_category}/catalogue-models.pl"
        f"?shop={espares_brand}&path={espares_path_id}"
    )

    brand_id    = _get_brand_id(brand_slug)
    category_id = _get_category_id(category_slug)
    if not brand_id or not category_id:
        logger.error(f"Brand '{brand_slug}' or category '{category_slug}' not found in DB")
        return 0

    job_id = create_scrape_job("product_code", models_url)
    start_scrape_job(job_id)

    try:
        codes = _fetch_all_codes_via_playwright(models_url, espares_category)
        logger.info(f"eSpares: fetched {len(codes)} unique model codes")
    except Exception as exc:
        fail_scrape_job(job_id, str(exc))
        logger.error(f"eSpares: enumeration failed: {exc}")
        return 0

    inserted = 0
    skipped  = 0
    RECONNECT_EVERY = 500

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("eSpares upsert", total=len(codes))

        for i, code in enumerate(codes):
            if i > 0 and i % RECONNECT_EVERY == 0:
                from config.settings import refresh_client
                refresh_client()
                logger.debug(f"eSpares: refreshed Supabase connection at model {i}")

            if upsert_model_and_code(brand_id, category_id, code, MARKET, match_existing_only=True):
                inserted += 1
            else:
                skipped += 1
            progress.advance(task)

    complete_scrape_job(job_id, parsed_json={"inserted": inserted, "skipped": skipped, "total": len(codes)})
    console.print(
        f"\n[bold]eSpares done:[/bold] {inserted} new GB product_codes inserted, "
        f"{skipped} already existed ({len(codes)} total codes fetched)"
    )
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="eSpares Samsung model enumerator")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    args = parser.parse_args()
    scrape_all(args.brand, args.category)
