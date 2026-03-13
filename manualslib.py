"""
scrapers/manualslib.py

Scrapes ManualsLib for:
  1. All models for a given brand × category
  2. Manual page URL + direct PDF URL per model

ManualsLib URL pattern:
  https://www.manualslib.com/brand/samsung/washing-machines/?p=1

Each model listing links to a manual page:
  https://www.manualslib.com/manual/1234567/Samsung-Ww90t986dsh.html

The manual page contains the direct PDF download link.
"""

import re
import time
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from config.settings import (
    supabase,
    MANUALSLIB_BRAND_SLUGS,
    MANUALSLIB_CATEGORY_PATHS,
    ACTIVE_BRAND_SLUGS,
    ACTIVE_CATEGORY_SLUGS,
)
from scrapers.base_scraper import (
    fetch_soup,
    create_scrape_job,
    start_scrape_job,
    complete_scrape_job,
    fail_scrape_job,
)

MANUALSLIB_BASE = "https://www.manualslib.com"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_brand_id(brand_slug: str) -> Optional[int]:
    res = supabase.table("brands").select("id").eq("slug", brand_slug).single().execute()
    return res.data["id"] if res.data else None


def _get_category_id(category_slug: str) -> Optional[int]:
    res = (
        supabase.table("categories")
        .select("id")
        .eq("slug_en", category_slug)
        .single()
        .execute()
    )
    return res.data["id"] if res.data else None


def _upsert_model(
    brand_id: int,
    category_id: int,
    name: str,
    manual_url: str,
) -> int:
    """Insert or update a model row. Returns the model id."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    res = (
        supabase.table("models")
        .upsert(
            {
                "brand_id":    brand_id,
                "category_id": category_id,
                "name":        name,
                "slug":        slug,
                "manual_url":  manual_url,
                "scrape_status": "pending",
            },
            on_conflict="brand_id,category_id,slug",
        )
        .execute()
    )
    return res.data[0]["id"]


# ── Page scrapers ──────────────────────────────────────────────────────────────

def _scrape_listing_page(url: str) -> tuple[list[dict], Optional[str]]:
    """
    Scrape one listing page.
    Returns:
        models   – list of { name, manual_page_url }
        next_url – URL of next page, or None
    """
    soup = fetch_soup(url)
    models = []

    # ManualsLib listing: each manual is in a <div class="result"> or similar
    # Selector verified against live site structure (may need adjustment)
    for item in soup.select("div.result-row, li.result-manual, div.manualRow"):
        link = item.select_one("a.manualTitle, a[href*='/manual/']")
        if not link:
            continue
        name = link.get_text(strip=True)
        href = link.get("href", "")
        if not href or not name:
            continue
        manual_page_url = urljoin(MANUALSLIB_BASE, href)
        models.append({"name": name, "manual_page_url": manual_page_url})

    # Pagination: find "Next" link
    next_link = soup.select_one("a.next, a[rel='next'], li.next a")
    next_url = urljoin(MANUALSLIB_BASE, next_link["href"]) if next_link and next_link.get("href") else None

    logger.debug(f"Listing page {url}: found {len(models)} models, next={next_url}")
    return models, next_url


def _scrape_manual_page(manual_page_url: str) -> dict:
    """
    Scrape individual manual page to extract:
      - PDF download URL
      - release year (if in title/metadata)
    """
    result = {"pdf_url": None, "release_year": None}
    try:
        soup = fetch_soup(manual_page_url)

        # PDF link – ManualsLib has a "Download" button
        pdf_link = soup.select_one(
            "a.download-button, a[href*='.pdf'], a#downloadLink"
        )
        if pdf_link and pdf_link.get("href"):
            href = pdf_link["href"]
            result["pdf_url"] = href if href.startswith("http") else urljoin(MANUALSLIB_BASE, href)

        # Year – often in page title or breadcrumb
        title = soup.find("title")
        if title:
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", title.get_text())
            if year_match:
                result["release_year"] = int(year_match.group())

    except Exception as e:
        logger.warning(f"Could not scrape manual page {manual_page_url}: {e}")

    return result


# ── Main public function ───────────────────────────────────────────────────────

def scrape_brand_category(brand_slug: str, category_slug: str) -> int:
    """
    Scrape all models for brand × category from ManualsLib.
    Inserts models into DB and creates scrape_job entries.
    Returns count of models upserted.
    """
    brand_id    = _get_brand_id(brand_slug)
    category_id = _get_category_id(category_slug)

    if not brand_id or not category_id:
        logger.error(f"Unknown brand={brand_slug} or category={category_slug}")
        return 0

    ml_brand    = MANUALSLIB_BRAND_SLUGS.get(brand_slug, brand_slug)
    ml_category = MANUALSLIB_CATEGORY_PATHS.get(category_slug, category_slug)
    start_url   = f"{MANUALSLIB_BASE}/brand/{ml_brand}/{ml_category}/?p=1"

    logger.info(f"Starting ManualsLib scrape: {brand_slug} / {category_slug}")
    logger.info(f"URL: {start_url}")

    total_upserted = 0
    page_url: Optional[str] = start_url
    page_num = 1

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        task = progress.add_task(f"{brand_slug}/{category_slug}", total=None)

        while page_url:
            job_id = create_scrape_job("model", page_url)
            start_scrape_job(job_id)

            try:
                models_on_page, next_url = _scrape_listing_page(page_url)
            except Exception as e:
                fail_scrape_job(job_id, str(e))
                logger.error(f"Failed listing page {page_url}: {e}")
                break

            if not models_on_page:
                logger.warning(f"No models found on page {page_num} – stopping pagination")
                complete_scrape_job(job_id)
                break

            for m in models_on_page:
                model_id = _upsert_model(
                    brand_id, category_id, m["name"], m["manual_page_url"]
                )

                # Scrape the individual manual page for PDF URL
                manual_info = _scrape_manual_page(m["manual_page_url"])
                update_fields: dict = {}
                if manual_info["pdf_url"]:
                    update_fields["manual_pdf_url"] = manual_info["pdf_url"]
                if manual_info["release_year"]:
                    update_fields["release_year"] = manual_info["release_year"]
                if update_fields:
                    supabase.table("models").update(update_fields).eq("id", model_id).execute()

                total_upserted += 1
                progress.advance(task)

            complete_scrape_job(job_id, parsed_json={"count": len(models_on_page), "page": page_num})
            logger.info(f"Page {page_num}: {len(models_on_page)} models (total so far: {total_upserted})")

            page_url = next_url
            page_num += 1

    # Mark brand scrape_status as done for this run
    supabase.table("brands").update({
        "scrape_status":  "done",
        "last_scraped_at": "now()",
    }).eq("id", brand_id).execute()

    logger.success(
        f"ManualsLib scrape complete: {brand_slug}/{category_slug} → {total_upserted} models"
    )
    return total_upserted


def run_active_brands() -> None:
    """
    Entry point: scrape all active brand × category combinations.
    Respects ACTIVE_BRAND_SLUGS and ACTIVE_CATEGORY_SLUGS from settings.
    """
    for brand_slug in ACTIVE_BRAND_SLUGS:
        for category_slug in ACTIVE_CATEGORY_SLUGS:
            logger.info(f"═══ {brand_slug.upper()} / {category_slug} ═══")
            count = scrape_brand_category(brand_slug, category_slug)
            logger.info(f"Result: {count} models upserted\n")
            time.sleep(5)   # pause between brand/category combos


if __name__ == "__main__":
    run_active_brands()
