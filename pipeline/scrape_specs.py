"""
pipeline/scrape_specs.py

Populates model_specs (generic JSONB specs table, see migration 010) for all
models of a given brand. Wraps the brand-specific scraper and writes results
back to Supabase.

Usage:
    python -m pipeline.scrape_specs --brand samsung --category washing-machines
    python -m pipeline.scrape_specs --brand samsung --category washing-machines --limit 10
    python -m pipeline.scrape_specs --brand samsung --category washing-machines --dry-run
    python -m pipeline.scrape_specs --brand samsung --category washing-machines --rescrape
"""

import argparse
from datetime import datetime, timezone

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn

from config.settings import supabase, refresh_client
from scrapers.samsung_specs import scrape_model_specs as scrape_samsung_specs
from scrapers.bsh_specs import scrape_bosch_specs, scrape_siemens_specs
from scrapers.electrolux_specs import scrape_model_specs as scrape_electrolux_specs

console = Console()

SCRAPER_MAP = {
    "samsung":   scrape_samsung_specs,
    "bosch":     scrape_bosch_specs,
    "siemens":   scrape_siemens_specs,
    "electrolux": scrape_electrolux_specs,
}

SPEC_FIELDS = [
    "capacity_kg", "spin_speed_rpm", "energy_class",
    "width_mm", "height_mm", "depth_mm",
    "noise_spinning_db", "energy_consumption_kwh",
    "water_consumption_l", "door_type",
]


def _fetch_all_models(brand_id: int, category_id: int) -> list[dict]:
    """Fetch all models with pagination (Supabase default page = 1000 rows)."""
    PAGE = 1000
    all_models: list[dict] = []
    offset = 0
    while True:
        page = (
            supabase.table("models")
            .select("id,name,base_model,slug")
            .eq("brand_id", brand_id)
            .eq("category_id", category_id)
            .order("id")
            .range(offset, offset + PAGE - 1)
            .execute()
        ).data or []
        all_models.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
    return all_models


def _get_models(brand_id: int, category_id: int, rescrape: bool) -> list[dict]:
    """Return models to process. Skips models already scraped unless --rescrape."""
    all_models = _fetch_all_models(brand_id, category_id)
    if not all_models:
        return []

    if rescrape:
        return all_models

    # Exclude models already in model_specs
    model_ids = [m["id"] for m in all_models]
    already_scraped: set[int] = set()
    for i in range(0, len(model_ids), 500):
        batch = model_ids[i : i + 500]
        done = (
            supabase.table("model_specs")
            .select("model_id")
            .in_("model_id", batch)
            .execute()
        ).data or []
        already_scraped.update(r["model_id"] for r in done)

    return [m for m in all_models if m["id"] not in already_scraped]


_INT_FIELDS = {"spin_speed_rpm", "width_mm", "height_mm", "depth_mm"}


def _upsert_spec(model_id: int, specs: dict) -> None:
    """Write spec row. Idempotent via upsert on model_id (PK)."""
    coerced = {
        f: (int(round(v)) if f in _INT_FIELDS and v is not None else v)
        for f, v in specs.items()
    }
    specs_json = {f: coerced.get(f) for f in SPEC_FIELDS if coerced.get(f) is not None}
    row = {
        "model_id":   model_id,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "specs":      specs_json,
    }
    supabase.table("model_specs").upsert(
        row, on_conflict="model_id"
    ).execute()


def run(
    brand_slug: str,
    category_slug: str,
    limit: int = 0,
    dry_run: bool = False,
    rescrape: bool = False,
) -> None:
    brand = (
        supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    )
    category = (
        supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()
    )
    if not brand.data or not category.data:
        logger.error(f"Brand '{brand_slug}' or category '{category_slug}' not found")
        return

    brand_id    = brand.data["id"]
    brand_name  = brand.data["name"]
    category_id = category.data["id"]

    scrape_fn = SCRAPER_MAP.get(brand_slug)
    if not scrape_fn:
        logger.error(f"No spec scraper registered for brand '{brand_slug}'")
        logger.info(f"Available scrapers: {list(SCRAPER_MAP.keys())}")
        return

    models = _get_models(brand_id, category_id, rescrape)
    if limit:
        models = models[:limit]

    total = len(models)
    logger.info(
        f"Spec scrape: {brand_name} / {category_slug} — "
        f"{total} models to process ({'dry run' if dry_run else 'live'})"
    )

    if not models:
        console.print("[dim]Nothing to process.[/dim]")
        return

    processed = failed = skipped = 0
    total_fields_found = 0

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task(f"{brand_slug}/{category_slug} specs", total=total)

        for i, model in enumerate(models):
            model_id   = model["id"]
            base_model = model.get("base_model") or model["name"].split("/")[0].strip()

            # Refresh Supabase client every 200 models to avoid connection limits
            if i > 0 and i % 200 == 0:
                refresh_client()

            try:
                specs = scrape_fn(base_model)
                fields_found = len([v for v in specs.values() if v is not None])
                total_fields_found += fields_found

                if fields_found == 0:
                    logger.debug(f"  {base_model}: no specs found")
                    skipped += 1
                else:
                    logger.debug(
                        f"  {base_model}: {fields_found} fields — "
                        f"{', '.join(k for k, v in specs.items() if v is not None)}"
                    )
                    if not dry_run:
                        _upsert_spec(model_id, specs)
                    processed += 1

            except Exception as e:
                logger.error(f"  {base_model}: {type(e).__name__}: {e}")
                failed += 1

            progress.advance(task)

    # ── Summary ──────────────────────────────────────────────────────────────
    t = Table(title=f"Spec scrape summary — {brand_name} / {category_slug}", box=box.SIMPLE)
    t.add_column("Metric",     style="bold", width=30)
    t.add_column("Value",      width=12)
    t.add_row("Total models",        str(total))
    t.add_row("Specs found",         str(processed))
    t.add_row("No match / no data",  str(skipped))
    t.add_row("Errors",              str(failed))
    t.add_row("Total fields written", str(total_fields_found))
    if processed:
        t.add_row("Avg fields per model", f"{total_fields_found/processed:.1f}")
    console.print(t)

    if dry_run:
        console.print("[dim]Dry run — no DB writes.[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape appliance model specs")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--limit",    type=int, default=0,
                        help="Limit to N models (0 = all)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Scrape but do not write to DB")
    parser.add_argument("--rescrape", action="store_true",
                        help="Re-scrape models already in model_specs")
    args = parser.parse_args()
    run(args.brand, args.category, args.limit, args.dry_run, args.rescrape)


if __name__ == "__main__":
    main()
