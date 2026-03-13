"""
pipeline/overnight_run.py

Master overnight orchestrator. Runs the full data pipeline for ALL
active brand × category combinations in sequence:

  1. Scrape model listings from ManualsLib
  2. Cleanup/deduplication (junk deletion + product_codes + product_lines)
  3. Error code extraction via Claude Vision on manual page images

Article generation is intentionally excluded (run separately after review).

Usage:
    python -m pipeline.overnight_run
    python -m pipeline.overnight_run --skip-models   # skip if already scraped
    python -m pipeline.overnight_run --skip-cleanup  # skip cleanup
"""

import argparse
import sys
import time
from datetime import datetime

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase, ACTIVE_BRAND_SLUGS, ACTIVE_CATEGORY_SLUGS
from scrapers.manualslib import scrape_brand_category
from pipeline.cleanup_models import analyse, execute as cleanup_execute
from scrapers.image_extractor import process_all_pending_models

console = Console()


# ── Per-combo pipeline ─────────────────────────────────────────────────────────

def run_combo(
    brand_slug: str,
    category_slug: str,
    skip_models: bool = False,
    skip_cleanup: bool = False,
) -> dict:
    """
    Run the full pipeline for one brand × category.
    Returns a summary dict.
    """
    result = {
        "brand": brand_slug,
        "category": category_slug,
        "models_upserted": 0,
        "junk_deleted": 0,
        "duplicates_removed": 0,
        "product_codes_added": 0,
        "product_lines_created": 0,
        "error_codes_extracted": "skipped",
        "status": "ok",
    }

    # Lookup brand/category IDs
    brand_row = supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    cat_row   = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()

    if not brand_row.data or not cat_row.data:
        logger.warning(f"[{brand_slug}/{category_slug}] Not found in DB, skipping")
        result["status"] = "not_in_db"
        return result

    brand_id    = brand_row.data["id"]
    category_id = cat_row.data["id"]

    # ── Step 1: Scrape models ──────────────────────────────────────────────────
    if not skip_models:
        try:
            count = scrape_brand_category(brand_slug, category_slug)
            result["models_upserted"] = count
            if count == 0:
                logger.info(f"[{brand_slug}/{category_slug}] No models found, skipping rest")
                result["status"] = "no_models"
                return result
        except Exception as e:
            logger.error(f"[{brand_slug}/{category_slug}] Scrape failed: {e}")
            result["status"] = f"scrape_error: {e}"
            return result
    else:
        # Count existing models
        n = supabase.table("models").select("id", count="exact").eq("brand_id", brand_id).eq("category_id", category_id).execute()
        result["models_upserted"] = n.count or 0
        if not result["models_upserted"]:
            result["status"] = "no_models"
            return result

    # ── Step 2: Cleanup / deduplication ───────────────────────────────────────
    if not skip_cleanup:
        try:
            analysis = analyse(brand_id, category_id)
            cleanup_execute(analysis, brand_id, category_id)
            result["junk_deleted"]        = len(analysis["junk"])
            result["duplicates_removed"]  = len(analysis["to_delete"])
            result["product_codes_added"] = len(analysis["product_codes_to_add"])
            result["product_lines_created"] = len([
                l for l in analysis["product_lines_to_create"] if len(l["members"]) >= 2
            ])
        except Exception as e:
            logger.error(f"[{brand_slug}/{category_slug}] Cleanup failed: {e}")
            result["status"] = f"cleanup_error: {e}"
            # Continue to error code extraction despite cleanup failure

    # ── Step 3: Error code extraction (image-based) ────────────────────────────
    try:
        process_all_pending_models(brand_slug, category_slug)
        ec_count = supabase.table("error_codes").select("id", count="exact").eq("brand_id", brand_id).eq("category_id", category_id).execute()
        result["error_codes_extracted"] = ec_count.count or 0
    except Exception as e:
        logger.error(f"[{brand_slug}/{category_slug}] Error code extraction failed: {e}")
        result["error_codes_extracted"] = f"error: {e}"

    return result


# ── Summary table ──────────────────────────────────────────────────────────────

def print_summary(results: list[dict]) -> None:
    t = Table(title="Overnight Run Summary", box=box.SIMPLE, show_header=True)
    t.add_column("Brand",     style="bold")
    t.add_column("Category")
    t.add_column("Models",    justify="right")
    t.add_column("Junk",      justify="right")
    t.add_column("Dups",      justify="right")
    t.add_column("Error codes", justify="right")
    t.add_column("Status")

    for r in results:
        status_color = "green" if r["status"] == "ok" else "yellow" if "no_models" in r["status"] else "red"
        t.add_row(
            r["brand"],
            r["category"],
            str(r["models_upserted"]),
            str(r["junk_deleted"]),
            str(r["duplicates_removed"]),
            str(r["error_codes_extracted"]),
            f"[{status_color}]{r['status']}[/{status_color}]",
        )

    console.print(t)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Overnight pipeline for all brands x categories")
    parser.add_argument("--skip-models",  action="store_true", help="Skip ManualsLib scraping (use existing models)")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip cleanup/deduplication")
    parser.add_argument("--brands",       nargs="+", default=ACTIVE_BRAND_SLUGS, help="Brand slugs to process")
    parser.add_argument("--categories",   nargs="+", default=ACTIVE_CATEGORY_SLUGS, help="Category slugs to process")
    args = parser.parse_args()

    combos = [(b, c) for b in args.brands for c in args.categories]
    total = len(combos)

    started = datetime.now()
    console.print(f"\n[bold]Overnight pipeline[/bold] – {total} brand/category combos")
    console.print(f"Brands:     {', '.join(args.brands)}")
    console.print(f"Categories: {', '.join(args.categories)}")
    console.print(f"Started:    {started.strftime('%Y-%m-%d %H:%M:%S')}\n")

    results = []
    for i, (brand_slug, category_slug) in enumerate(combos, 1):
        console.rule(f"[bold blue][{i}/{total}] {brand_slug} / {category_slug}")
        try:
            r = run_combo(
                brand_slug, category_slug,
                skip_models=args.skip_models,
                skip_cleanup=args.skip_cleanup,
            )
            results.append(r)
        except Exception as e:
            logger.error(f"Unhandled error for {brand_slug}/{category_slug}: {e}")
            results.append({
                "brand": brand_slug, "category": category_slug,
                "models_upserted": 0, "junk_deleted": 0,
                "duplicates_removed": 0, "product_codes_added": 0,
                "product_lines_created": 0, "error_codes_extracted": 0,
                "status": f"fatal: {e}",
            })

        # Brief pause between combos to be polite to ManualsLib
        time.sleep(3)

    elapsed = datetime.now() - started
    console.print(f"\n[bold]All combos complete in {elapsed}[/bold]\n")
    print_summary(results)

    # Overall totals
    total_models = sum(r["models_upserted"] for r in results)
    total_ec     = sum(r["error_codes_extracted"] if isinstance(r["error_codes_extracted"], int) else 0 for r in results)
    console.print(f"\nTotal: [green]{total_models}[/green] models, [green]{total_ec}[/green] error codes")
    console.print(f"\nNext step: python -m pipeline.run_all --step articles --brand <brand> --category <cat>")


if __name__ == "__main__":
    main()
