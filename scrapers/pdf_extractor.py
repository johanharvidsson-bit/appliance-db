"""
scrapers/pdf_extractor.py

Extracts error codes from appliance manual PDFs.

Strategy:
  1. Scan last 30% of pages (error code tables are almost always near end)
  2. Detect error code table by looking for patterns like E1/E2/F1/4C etc.
  3. Extract: code, description, suggested action
  4. Upsert into error_codes + link to all product_codes under the model
"""

import re
import json
from pathlib import Path
from typing import Optional

import pdfplumber
from loguru import logger

from config.settings import supabase, MANUAL_DIR
from scrapers.base_scraper import (
    download_file,
    create_scrape_job,
    start_scrape_job,
    complete_scrape_job,
    fail_scrape_job,
)

# ── Error code patterns ────────────────────────────────────────────────────────
# Covers Samsung (E1-E9, 4C, 5E, dE...), Bosch (F01-F99), Whirlpool (F1-F29 E1-E9)
ERROR_CODE_PATTERN = re.compile(
    r"""
    ^                           # start of cell/line
    \s*
    (                           # capture group = the code
        [EeFf]\s?\d{1,2}        # E1, E2, F01, F21
        | \d[A-Z]               # 4C, 5E, 9E (Samsung style)
        | [A-Z]{1,2}\d{1,2}     # dE, LE, UE
        | OE|IE|DE|PE|TE|CE     # named codes (LG style)
        | Er\s?\d{2}            # Er01 style
    )
    \s*$                        # end of cell/line
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Keywords that signal we're in or near an error code section
ERROR_SECTION_KEYWORDS = [
    "error code", "fault code", "error message", "trouble",
    "felkod", "fehlermeldung", "störungsanzeige",
    "display", "problem", "cause", "solution", "remedy",
]


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_model_info(model_id: int) -> Optional[dict]:
    res = (
        supabase.table("models")
        .select("id, brand_id, category_id, name, manual_pdf_path, manual_pdf_url")
        .eq("id", model_id)
        .single()
        .execute()
    )
    return res.data


def _get_product_code_ids(model_id: int) -> list[int]:
    res = (
        supabase.table("product_codes")
        .select("id")
        .eq("model_id", model_id)
        .execute()
    )
    return [r["id"] for r in (res.data or [])]


def _upsert_error_code(
    brand_id: int,
    category_id: int,
    code: str,
    display_text: str,
    source_url: str,
) -> int:
    """Upsert error_code row, return id."""
    res = (
        supabase.table("error_codes")
        .upsert(
            {
                "brand_id":     brand_id,
                "category_id":  category_id,
                "code":         code.upper().strip(),
                "display_text": display_text[:500],
                "source":       source_url,
                "scrape_status": "done",
            },
            on_conflict="brand_id,category_id,code",
        )
        .execute()
    )
    return res.data[0]["id"]


def _link_error_to_product_codes(
    error_code_id: int,
    product_code_ids: list[int],
) -> None:
    """Link error_code to all product_codes under the model."""
    if not product_code_ids:
        return
    rows = [
        {"error_code_id": error_code_id, "product_code_id": pc_id}
        for pc_id in product_code_ids
    ]
    supabase.table("error_code_product_codes").upsert(
        rows, on_conflict="error_code_id,product_code_id"
    ).execute()


# ── PDF parsing ────────────────────────────────────────────────────────────────

def _is_error_table_page(page_text: str) -> bool:
    """Return True if this page likely contains an error code table."""
    text_lower = page_text.lower()
    return any(kw in text_lower for kw in ERROR_SECTION_KEYWORDS)


def _parse_error_table_from_text(text: str) -> list[dict]:
    """
    Parse error codes from raw page text.
    Handles two layouts:
      A) Table-like: code | cause | solution  (columns separated by 2+ spaces)
      B) List-like:  E2 – Drainage problem
    Returns list of { code, description }
    """
    results = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line starts with / is an error code
        code_match = ERROR_CODE_PATTERN.match(line)

        if code_match:
            code = code_match.group(1).replace(" ", "").upper()

            # Gather description from remaining columns / next lines
            description_parts = []

            # Same line: everything after the code
            rest = line[code_match.end():].strip(" -–:").strip()
            if rest:
                description_parts.append(rest)

            # Look ahead: grab up to 3 continuation lines that aren't new codes
            j = i + 1
            while j < min(i + 4, len(lines)):
                next_line = lines[j]
                if ERROR_CODE_PATTERN.match(next_line):
                    break
                if next_line and not next_line.lower().startswith(("page ", "•")):
                    description_parts.append(next_line)
                j += 1

            description = " ".join(description_parts).strip()
            if description:
                results.append({"code": code, "description": description})
                i = j
                continue

        i += 1

    return results


def _parse_error_table_from_table(tables: list) -> list[dict]:
    """
    Parse structured PDF tables (pdfplumber table extraction).
    Each table is a list of rows; each row is a list of cell strings.
    """
    results = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        # Try to identify which column is the code and which is description
        # by checking first data row against error code pattern
        code_col = None
        desc_col = None

        for row in table[1:4]:   # sample first few data rows
            for ci, cell in enumerate(row):
                if cell and ERROR_CODE_PATTERN.match(str(cell).strip()):
                    code_col = ci
                    # description is usually the next non-empty column
                    for di in range(ci + 1, len(row)):
                        if row[di]:
                            desc_col = di
                            break
                    break
            if code_col is not None:
                break

        if code_col is None:
            continue

        for row in table[1:]:   # skip header
            try:
                code = str(row[code_col] or "").strip()
                desc = str(row[desc_col] or "").strip() if desc_col is not None else ""
                if ERROR_CODE_PATTERN.match(code) and desc:
                    results.append({
                        "code": code.replace(" ", "").upper(),
                        "description": desc[:500],
                    })
            except IndexError:
                continue

    return results


def extract_error_codes_from_pdf(pdf_path: Path, source_url: str = "") -> list[dict]:
    """
    Main extraction function.
    Returns list of { code, description }.
    """
    all_codes: dict[str, str] = {}   # code → description (dedup)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            # Focus on last 40% of pages where error tables live
            start_page = max(0, int(total_pages * 0.60))

            logger.debug(f"PDF has {total_pages} pages, scanning {start_page}–{total_pages}")

            for page_num in range(start_page, total_pages):
                page = pdf.pages[page_num]
                text = page.extract_text() or ""

                if not _is_error_table_page(text):
                    continue

                logger.debug(f"  Page {page_num + 1}: looks like error section")

                # Try table extraction first (more accurate)
                tables = page.extract_tables()
                if tables:
                    table_codes = _parse_error_table_from_table(tables)
                    for item in table_codes:
                        if item["code"] not in all_codes:
                            all_codes[item["code"]] = item["description"]

                # Fallback: text parsing
                if not tables or not all_codes:
                    text_codes = _parse_error_table_from_text(text)
                    for item in text_codes:
                        if item["code"] not in all_codes:
                            all_codes[item["code"]] = item["description"]

    except Exception as e:
        logger.error(f"PDF extraction failed for {pdf_path}: {e}")

    results = [{"code": k, "description": v} for k, v in all_codes.items()]
    logger.info(f"Extracted {len(results)} error codes from {pdf_path.name}")
    return results


# ── Model-level orchestration ─────────────────────────────────────────────────

def process_model(model_id: int) -> int:
    """
    Download manual PDF (if needed), extract error codes, upsert to DB.
    Returns count of error codes upserted.
    """
    model = _get_model_info(model_id)
    if not model:
        logger.error(f"Model id={model_id} not found")
        return 0

    pdf_url  = model.get("manual_pdf_url")
    pdf_path_str = model.get("manual_pdf_path")

    # Determine local PDF path
    if pdf_path_str:
        pdf_path = Path(pdf_path_str)
    elif pdf_url:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", model["name"])[:80]
        pdf_path = MANUAL_DIR / f"{safe_name}_{model_id}.pdf"
    else:
        logger.warning(f"Model id={model_id} ({model['name']}): no PDF URL, skipping")
        return 0

    # Download if not already on disk
    if not pdf_path.exists():
        if not pdf_url:
            logger.warning(f"No PDF URL for model id={model_id}")
            return 0
        job_id = create_scrape_job("manual_pdf", pdf_url, model_id)
        start_scrape_job(job_id)
        success = download_file(pdf_url, pdf_path)
        if not success:
            fail_scrape_job(job_id, "Download failed")
            return 0
        # Save path back to DB
        supabase.table("models").update({
            "manual_pdf_path": str(pdf_path),
        }).eq("id", model_id).execute()
        complete_scrape_job(job_id)

    # Extract error codes
    job_id = create_scrape_job("error_code", str(pdf_path), model_id)
    start_scrape_job(job_id)

    try:
        codes = extract_error_codes_from_pdf(pdf_path, source_url=pdf_url or "")
    except Exception as e:
        fail_scrape_job(job_id, str(e))
        return 0

    if not codes:
        logger.warning(f"No error codes found in PDF for model id={model_id}")
        complete_scrape_job(job_id, parsed_json={"count": 0})
        supabase.table("models").update({"scrape_status": "done"}).eq("id", model_id).execute()
        return 0

    # Upsert to DB
    product_code_ids = _get_product_code_ids(model_id)
    upserted = 0

    for item in codes:
        ec_id = _upsert_error_code(
            brand_id=model["brand_id"],
            category_id=model["category_id"],
            code=item["code"],
            display_text=item["description"],
            source_url=pdf_url or str(pdf_path),
        )
        _link_error_to_product_codes(ec_id, product_code_ids)
        upserted += 1

    complete_scrape_job(job_id, parsed_json={"count": upserted, "codes": [c["code"] for c in codes]})
    supabase.table("models").update({"scrape_status": "done"}).eq("id", model_id).execute()

    logger.success(f"Model id={model_id} ({model['name']}): {upserted} error codes upserted")
    return upserted


def process_all_pending_models(brand_slug: str = "samsung", category_slug: str = "washing-machines") -> None:
    """Process all models with scrape_status='pending' for a brand/category."""
    brand    = supabase.table("brands").select("id").eq("slug", brand_slug).single().execute()
    category = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()

    if not brand.data or not category.data:
        logger.error("Brand or category not found")
        return

    models = (
        supabase.table("models")
        .select("id, name")
        .eq("brand_id", brand.data["id"])
        .eq("category_id", category.data["id"])
        .eq("scrape_status", "pending")
        .execute()
    )

    total = len(models.data or [])
    logger.info(f"Processing {total} pending models for {brand_slug}/{category_slug}")

    total_codes = 0
    for i, model in enumerate(models.data or [], 1):
        logger.info(f"[{i}/{total}] {model['name']}")
        total_codes += process_model(model["id"])

    logger.success(f"Done. Total error codes extracted: {total_codes}")


if __name__ == "__main__":
    process_all_pending_models()
