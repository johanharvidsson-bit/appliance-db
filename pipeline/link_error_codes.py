"""
pipeline/link_error_codes.py

Populates the error_code_product_codes bridge table.

Error codes are stored at brand/category level. This script links every
error code to every product code in the same brand/category — i.e. all
Samsung washing-machine error codes apply to all Samsung washing-machine
product codes.

Safe to re-run (uses ON CONFLICT DO NOTHING).

Usage:
    python -m pipeline.link_error_codes
    python -m pipeline.link_error_codes --brand samsung --category washing-machines
    python -m pipeline.link_error_codes --dry-run
"""

import argparse
from loguru import logger
from rich.console import Console

from config.settings import supabase

console = Console()


def run(brand_slug: str = "samsung", category_slug: str = "washing-machines", dry_run: bool = False) -> int:
    brand    = supabase.table("brands").select("id").eq("slug", brand_slug).single().execute()
    category = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()

    if not brand.data or not category.data:
        console.print(f"[red]Brand '{brand_slug}' or category '{category_slug}' not found[/red]")
        return 0

    brand_id    = brand.data["id"]
    category_id = category.data["id"]

    # Fetch all error code IDs for this brand/category
    ecs = (
        supabase.table("error_codes")
        .select("id,code")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    ).data or []

    if not ecs:
        console.print("[yellow]No error codes found — nothing to link.[/yellow]")
        return 0

    # Fetch all model IDs for this brand/category
    models = (
        supabase.table("models")
        .select("id")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    ).data or []

    model_ids = [m["id"] for m in models]
    if not model_ids:
        console.print("[yellow]No models found — nothing to link.[/yellow]")
        return 0

    # Fetch all product code IDs for those models (in batches to avoid URL limits)
    all_pcs: list[dict] = []
    batch = 200
    for i in range(0, len(model_ids), batch):
        chunk = (
            supabase.table("product_codes")
            .select("id")
            .in_("model_id", model_ids[i:i+batch])
            .execute()
        ).data or []
        all_pcs.extend(chunk)

    if not all_pcs:
        console.print("[yellow]No product codes found — nothing to link.[/yellow]")
        return 0

    pc_ids = [pc["id"] for pc in all_pcs]
    ec_ids = [ec["id"] for ec in ecs]

    console.print(
        f"\n[bold]Link error codes -> product codes[/bold]  "
        f"({brand_slug} / {category_slug})"
    )
    console.print(f"  Error codes:   {len(ec_ids)}")
    console.print(f"  Product codes: {len(pc_ids)}")
    console.print(f"  Pairs to link: {len(ec_ids) * len(pc_ids):,}")

    if dry_run:
        console.print("\n[dim]Dry run — no DB writes.[/dim]")
        return 0

    # Check how many links already exist
    existing = (
        supabase.table("error_code_product_codes")
        .select("error_code_id", count="exact")
        .in_("error_code_id", ec_ids[:200])
        .execute()
    )
    already = existing.count or 0
    if already > 0:
        console.print(f"  [dim]{already} links already exist — inserting missing ones[/dim]")

    # Build and insert all pairs in batches
    rows = [
        {"error_code_id": ec_id, "product_code_id": pc_id}
        for ec_id in ec_ids
        for pc_id in pc_ids
    ]

    inserted = 0
    insert_batch = 500
    for i in range(0, len(rows), insert_batch):
        supabase.table("error_code_product_codes").upsert(
            rows[i:i+insert_batch],
            on_conflict="error_code_id,product_code_id",
            ignore_duplicates=True,
        ).execute()
        inserted += len(rows[i:i+insert_batch])
        logger.debug(f"Inserted batch {i // insert_batch + 1}, {inserted}/{len(rows)} rows")

    console.print(f"\n[bold green]Done.[/bold green] {len(rows):,} links written.")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Link error codes to product codes")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()
    run(args.brand, args.category, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
