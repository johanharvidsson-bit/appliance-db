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

def _scrape_listing_page(url: str) -> list[dict]:
    """
    Scrape the brand/category listing page.
    ManualsLib loads all results on a single page (no server-side pagination).

    DOM structure:
      div.row.tabled
        div.col-sm-2.mname > a  ← model name
        div.col-sm-10.mlinks
          div.fdiv > div.mdiv > a[href*="/manual/"]  ← one link per manual type

    Returns list of { name, manual_page_url }.
    """
    soup = fetch_soup(url)
    models = []

    for row in soup.select("div.row.tabled"):
        name_el = row.select_one("div.mname a")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name:
            continue

        # Collect all manual links; prefer Service Manual (more likely to contain
        # error code tables), fall back to any manual link.
        manual_links = row.select("div.mdiv a[href*='/manual/']")
        if not manual_links:
            continue

        service_link = next(
            (a for a in manual_links if "service" in a.get_text(strip=True).lower()),
            None,
        )
        chosen_link = service_link or manual_links[0]
        manual_page_url = urljoin(MANUALSLIB_BASE, chosen_link["href"])

        models.append({"name": name, "manual_page_url": manual_page_url})

    logger.debug(f"Listing page {url}: found {len(models)} models")
    return models


def _scrape_manual_page(manual_page_url: str) -> dict:
    """
    Scrape individual manual page to extract:
      - PDF download URL
      - release year (if in title/metadata)
    """
    result = {"pdf_url": None, "release_year": None}
    try:
        soup = fetch_soup(manual_page_url)

        # PDF link – ManualsLib uses /download/{id}/{name}.html which redirects to PDF
        pdf_link = soup.select_one(
            "a[href*='/download/'], a.download-button, a[href*='.pdf'], a#downloadLink"
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
    # ManualsLib loads all results on a single .html page (no pagination)
    listing_url = f"{MANUALSLIB_BASE}/brand/{ml_brand}/{ml_category}.html"

    logger.info(f"Starting ManualsLib scrape: {brand_slug} / {category_slug}")
    logger.info(f"URL: {listing_url}")

    total_upserted = 0

    job_id = create_scrape_job("model", listing_url)
    start_scrape_job(job_id)

    try:
        all_models = _scrape_listing_page(listing_url)
    except Exception as e:
        fail_scrape_job(job_id, str(e))
        logger.error(f"Failed listing page {listing_url}: {e}")
        return 0

    if not all_models:
        logger.warning(f"No models found at {listing_url} – check the category URL slug")
        complete_scrape_job(job_id)
        return 0

    complete_scrape_job(job_id, parsed_json={"count": len(all_models)})
    logger.info(f"Found {len(all_models)} models on listing page")

    # Progress bar – avoid SpinnerColumn (Unicode encoding issues on Windows)
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        task = progress.add_task(f"{brand_slug}/{category_slug}", total=len(all_models))

        for m in all_models:
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
