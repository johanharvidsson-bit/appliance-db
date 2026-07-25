"""
scrapers/image_extractor.py

Extracts error codes from appliance manuals using the ManualsLib viewer
page images + Claude Vision API.

Flow per model:
  1. Fetch ManualsLib viewer page (manual_url) to get CDN image path pattern
  2. Determine total page count
  3. Download the last 30% of pages as PNG images from CDN (free, no auth)
  4. Send batches of 4 pages to Claude Vision (claude-haiku) for extraction
  5. Return list of {"code": ..., "display_text": ...} dicts

CDN image URLs follow the pattern:
  https://static-data2.manualslib.com/storage/pdf75/{c1}/{c2}/{id}/images/{slug}_{N}_bg.png

  where c1 = ceil(id / 10000), c2 = ceil(id / 100)
  and slug is derived from the viewer page HTML (extracted via regex).
"""

import re
import math
import json
import base64
import concurrent.futures
from typing import Optional

import httpx
import anthropic
from loguru import logger

from config.settings import supabase
from scrapers.base_scraper import fetch_soup_unblocked, create_scrape_job, start_scrape_job, complete_scrape_job, fail_scrape_job

# ── Constants ──────────────────────────────────────────────────────────────────

CDN_BASE = "https://static-data2.manualslib.com/storage"
MAX_PAGES_TO_CHECK = 12        # max page images to download per manual
PAGES_START_FRACTION = 0.15    # skip first 15% (cover/TOC)
PAGES_END_FRACTION   = 0.85    # skip last 15% (back matter/warranty)
MAX_WORKERS = 5                # parallel image downloads
VISION_BATCH_SIZE = 4          # pages per Claude Vision call

_claude = anthropic.Anthropic()

_VISION_PROMPT = """\
These are pages from a home appliance (washing machine / dryer / dishwasher) manual.
Carefully look for any error code table or troubleshooting section that lists fault codes.

Extract every error code / fault code you can see together with its description.

Return ONLY a JSON array — no other text:
[{"code": "E17", "description": "Water inlet fault — check water supply"}, ...]

Rules:
- Include codes like E01, F23, E:17, 4C, OE, dE, Er05 etc.
- If the same code appears multiple times keep the most descriptive entry.
- If no error codes are visible on these pages return exactly: []
"""

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.manualslib.com/",
}


# ── CDN URL derivation ─────────────────────────────────────────────────────────

def _cdn_url_from_viewer_page(manual_url: str) -> Optional[dict]:
    """
    Fetch the viewer page HTML and extract the CDN image URL template.
    Handles both CDN formats:
      New: storage/pdf75/{c1}/{c2}/{id}/images/{slug}_{N}_bg.png
      Old: pdf3/{c1}/{c2}/{id}-{brand}/images/{slug}_{N}_bg.jpg
    Returns {"cdn_template": "https://.../{N}_bg.EXT", "total_pages": N}
    or None on failure.
    """
    # Strip URL fragment (#product-...) — server ignores it but helps readability
    clean_url = manual_url.split("#")[0]
    try:
        soup = fetch_soup_unblocked(clean_url)
        html = str(soup)

        cdn_template = None

        # New format: storage/pdf{NN}/{c1}/{c2}/{id}/images/{slug}_1_bg.png
        m = re.search(
            r'storage/(pdf\d+)/(\d+)/(\d+)/(\d+)/images/([^\"\'>\s]+?)_1_bg\.(png|jpg)',
            html,
        )
        if m:
            pdf_ver, c1, c2, manual_id, slug, ext = m.groups()
            cdn_template = (
                f"{CDN_BASE}/{pdf_ver}/{c1}/{c2}/{manual_id}/images/{slug}_{{N}}_bg.{ext}"
            )

        # Old format: pdf3/{c1}/{c2}/{id}-{brand}/images/{slug}_1_bg.jpg
        # Note: page 1 cover is .jpg but pages 2+ are always .png — force png.
        if not cdn_template:
            m = re.search(
                r'pdf\d+/(\d+)/(\d+)/(\d+-[a-z]+)/images/([^\"\'>\s]+?)_1_bg\.(png|jpg)',
                html,
            )
            if m:
                c1, c2, id_brand, slug, _ext = m.groups()
                cdn_template = (
                    f"https://static-data2.manualslib.com/pdf3/{c1}/{c2}/{id_brand}/images/{slug}_{{N}}_bg.png"
                )

        if not cdn_template:
            logger.debug(f"No bg image pattern found in {clean_url}")
            return None

        # Page count: "N pages" text, data-page attrs, or thumb count
        page_count = 0
        pm = re.search(r'\b(\d{1,3})\s+pages?\b', soup.get_text(), re.I)
        if pm:
            page_count = int(pm.group(1))

        data_pages = [
            int(el.get("data-page", 0))
            for el in soup.find_all(attrs={"data-page": True})
            if el.get("data-page", "").isdigit()
        ]
        if data_pages:
            page_count = max(page_count, max(data_pages))

        if not page_count:
            thumbs = re.findall(r'_(\d+)_(?:thumb|bg)\.(?:png|jpg)', html)
            if thumbs:
                page_count = max(int(x) for x in thumbs)

        if not page_count:
            page_count = 50  # safe default

        logger.debug(f"CDN template: {cdn_template} ({page_count} pages)")
        return {"cdn_template": cdn_template, "total_pages": page_count}

    except Exception as e:
        logger.warning(f"Could not extract CDN info from {manual_url}: {e}")
        return None


def _choose_pages(total_pages: int) -> list[int]:
    """Select which page numbers to download (middle portion of manual, skipping cover/back matter)."""
    start = max(1, math.ceil(total_pages * PAGES_START_FRACTION))
    end   = min(total_pages, math.floor(total_pages * PAGES_END_FRACTION))
    pages = list(range(start, end + 1))
    # Cap to MAX_PAGES_TO_CHECK, evenly spaced if too many
    if len(pages) > MAX_PAGES_TO_CHECK:
        step = len(pages) / MAX_PAGES_TO_CHECK
        pages = [pages[round(i * step)] for i in range(MAX_PAGES_TO_CHECK)]
    return pages


def _download_page_image(cdn_template: str, page_num: int) -> Optional[bytes]:
    """Download one page bg image from CDN. Returns bytes or None."""
    url = cdn_template.replace("{N}", str(page_num))
    try:
        r = httpx.get(url, headers=_HTTP_HEADERS, timeout=15, follow_redirects=True)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            return r.content
        # Old CDN: page 1 cover is .jpg while content pages are .png — try alternate ext
        if r.status_code == 404 and url.endswith(".png"):
            alt_url = url[:-4] + ".jpg"
            r2 = httpx.get(alt_url, headers=_HTTP_HEADERS, timeout=15, follow_redirects=True)
            if r2.status_code == 200 and r2.headers.get("content-type", "").startswith("image"):
                return r2.content
        logger.debug(f"Page {page_num} returned {r.status_code}")
    except Exception as e:
        logger.debug(f"Failed to download page {page_num} from {url}: {e}")
    return None


def _download_pages_parallel(cdn_template: str, page_nums: list[int]) -> list[bytes]:
    """Download multiple page images in parallel. Returns list of non-None bytes."""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_download_page_image, cdn_template, n): n for n in page_nums}
        for future in concurrent.futures.as_completed(futures):
            img = future.result()
            if img:
                results.append(img)
    return results


# ── Claude Vision extraction ───────────────────────────────────────────────────

def _image_content_block(img_bytes: bytes) -> dict:
    """Build an Anthropic image content block from raw image bytes."""
    media_type = "image/png" if img_bytes[:4] == b"\x89PNG" else "image/jpeg"
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(img_bytes).decode(),
        },
    }


def _call_vision_batch(images: list[bytes]) -> list[dict]:
    """Send a batch of page images to Claude Vision and return extracted codes."""
    import time as _time
    content = [_image_content_block(img) for img in images]
    content.append({"type": "text", "text": _VISION_PROMPT})
    for attempt in range(3):
        try:
            resp = _claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
            )
            text = resp.content[0].text.strip()
            logger.debug(f"Vision response: {text[:200]}")
            m = re.search(r"\[.*\]", text, re.DOTALL)
            if not m:
                return []
            items = json.loads(m.group())
            results = []
            for item in items:
                code = str(item.get("code", "")).strip().upper().replace(" ", "").replace(":", "")
                desc = str(item.get("description", "")).strip()
                if code and 2 <= len(code) <= 10 and desc:
                    results.append({"code": code, "display_text": desc})
            return results
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = 60 * (attempt + 1)
                logger.warning(f"Vision rate limit, waiting {wait}s (attempt {attempt+1}/3)")
                _time.sleep(wait)
            else:
                logger.warning(f"Vision API call failed: {e}")
                return []
    return []


def _run_vision_on_pages(images: list[bytes]) -> list[dict]:
    """Send page images to Claude Vision in batches and deduplicate results."""
    all_codes: dict[str, str] = {}
    for i in range(0, len(images), VISION_BATCH_SIZE):
        batch = images[i : i + VISION_BATCH_SIZE]
        for item in _call_vision_batch(batch):
            code = item["code"]
            desc = item["display_text"]
            if len(desc) > len(all_codes.get(code, "")):
                all_codes[code] = desc
    return [{"code": k, "display_text": v} for k, v in all_codes.items()]


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _upsert_error_codes(brand_id: int, category_id: int, model_id: int, codes: list[dict]) -> int:
    """Insert error codes and link them to the model. Returns count inserted."""
    inserted = 0
    for item in codes:
        code = item.get("code", "").strip()
        if not code:
            continue

        # Upsert error code
        ec_res = supabase.table("error_codes").upsert(
            {
                "brand_id":    brand_id,
                "category_id": category_id,
                "code":        code,
                "display_text": item.get("display_text", "")[:500],
            },
            on_conflict="brand_id,category_id,code",
        ).execute()

        if not ec_res.data:
            continue
        ec_id = ec_res.data[0]["id"]

        # Link error code to model via product_code
        # Find or create the canonical product_code for this model
        pc_res = supabase.table("product_codes").select("id").eq("model_id", model_id).limit(1).execute()
        if pc_res.data:
            pc_id = pc_res.data[0]["id"]
            supabase.table("error_code_product_codes").upsert(
                {"error_code_id": ec_id, "product_code_id": pc_id},
                on_conflict="error_code_id,product_code_id",
            ).execute()
        inserted += 1

    return inserted


# ── Main public API ────────────────────────────────────────────────────────────

def extract_error_codes_for_model(
    model: dict,
    brand_id: int,
    category_id: int,
) -> int:
    """
    Extract error codes for a single model using viewer page images.
    Returns count of error codes inserted.
    """
    manual_url = model.get("manual_url")
    if not manual_url:
        logger.debug(f"Model {model['id']} has no manual_url, skipping")
        return 0

    job_id = create_scrape_job("error_code", manual_url, model["id"])
    start_scrape_job(job_id)

    try:
        cdn_info = _cdn_url_from_viewer_page(manual_url)
        if not cdn_info:
            fail_scrape_job(job_id, "Could not determine CDN URL from viewer page")
            supabase.table("models").update({"scrape_status": "skipped"}).eq("id", model["id"]).execute()
            return 0

        page_nums = _choose_pages(cdn_info["total_pages"])
        images = _download_pages_parallel(cdn_info["cdn_template"], page_nums)

        if not images:
            fail_scrape_job(job_id, "No page images downloaded")
            return 0

        codes = _run_vision_on_pages(images)
        count = _upsert_error_codes(brand_id, category_id, model["id"], codes)

        # Mark model as done
        supabase.table("models").update({"scrape_status": "done"}).eq("id", model["id"]).execute()
        complete_scrape_job(job_id, parsed_json={"codes": count, "pages_checked": len(images)})
        logger.success(f"  Model {model['id']} ({model.get('name','')}): {count} error codes from {len(images)} pages")
        return count

    except Exception as e:
        fail_scrape_job(job_id, str(e))
        logger.error(f"  Model {model['id']}: {type(e).__name__}: {e}")
        return 0


def process_all_pending_models(brand_slug: str, category_slug: str) -> None:
    """
    Run image-based error code extraction for all pending models of a brand/category.
    Groups models by unique manual_url so each viewer page is fetched only once.
    """
    brand = supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    category = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()

    if not brand.data or not category.data:
        logger.error(f"Brand '{brand_slug}' or category '{category_slug}' not found")
        return

    brand_id = brand.data["id"]
    category_id = category.data["id"]

    models = (
        supabase.table("models")
        .select("id,name,manual_url,scrape_status")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .eq("scrape_status", "pending")
        .execute()
    ).data or []

    logger.info(f"Image extraction: {len(models)} pending models for {brand_slug}/{category_slug}")

    if not models:
        logger.info("No pending models, nothing to do")
        return

    # Group by unique manual_url to avoid re-fetching viewer page for variants
    by_url: dict[str, list[dict]] = {}
    no_url: list[dict] = []
    for m in models:
        url = m.get("manual_url")
        if url:
            by_url.setdefault(url, []).append(m)
        else:
            no_url.append(m)

    logger.info(f"  {len(by_url)} unique viewer pages, {len(no_url)} models without URL")

    total_codes = 0
    processed = 0

    for manual_url, group in by_url.items():
        # Process using the first model in the group; share result with all variants
        primary = group[0]
        count = extract_error_codes_for_model(primary, brand_id, category_id)
        total_codes += count
        processed += 1

        # Mark remaining variants as done (they share the same manual)
        for variant in group[1:]:
            supabase.table("models").update({"scrape_status": "done"}).eq("id", variant["id"]).execute()

        if processed % 10 == 0:
            logger.info(f"  Progress: {processed}/{len(by_url)} manuals, {total_codes} codes so far")

    for m in no_url:
        supabase.table("models").update({"scrape_status": "skipped"}).eq("id", m["id"]).execute()

    logger.success(
        f"Image extraction complete for {brand_slug}/{category_slug}: "
        f"{total_codes} error codes from {processed} unique manuals"
    )
