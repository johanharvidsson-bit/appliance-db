"""
pipeline/run_all.py

Master pipeline orchestrator.
Runs all scrape steps in the correct order for a given brand × category.

Usage:
    python -m pipeline.run_all
    python -m pipeline.run_all --brand samsung --category washing-machines
    python -m pipeline.run_all --step models   # run only one step
"""

import argparse
import sys
from datetime import datetime

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase, ACTIVE_BRAND_SLUGS, ACTIVE_CATEGORY_SLUGS
from scrapers.manualslib import scrape_brand_category
from scrapers.pdf_extractor import process_all_pending_models
from pipeline.article_generator import process_all as generate_articles

console = Console()


# ── Status report ──────────────────────────────────────────────────────────────

def print_status(brand_slug: str, category_slug: str) -> None:
    """Print a summary table of current DB state for brand/category."""
    brand    = supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    category = supabase.table("categories").select("id,slug_en").eq("slug_en", category_slug).single().execute()

    if not brand.data or not category.data:
        console.print("[red]Brand or category not found[/red]")
        return

    brand_id    = brand.data["id"]
    category_id = category.data["id"]

    models = supabase.table("models").select("id,scrape_status").eq("brand_id", brand_id).eq("category_id", category_id).execute()
    product_codes = supabase.table("product_codes").select("id,model_id").execute()
    error_codes   = supabase.table("error_codes").select("id").eq("brand_id", brand_id).eq("category_id", category_id).execute()
    articles      = supabase.table("articles").select("id,status").execute()

    model_ids = {m["id"] for m in (models.data or [])}
    pc_count  = sum(1 for pc in (product_codes.data or []) if pc["model_id"] in model_ids)

    models_done    = sum(1 for m in (models.data or []) if m["scrape_status"] == "done")
    models_pending = sum(1 for m in (models.data or []) if m["scrape_status"] == "pending")

    table = Table(
        title=f"DB Status – {brand.data['name']} / {category_slug}",
        box=box.ROUNDED,
        show_header=True,
    )
    table.add_column("Entity",  style="bold")
    table.add_column("Count",   justify="right")
    table.add_column("Details", style="dim")

    table.add_row("Models",        str(len(models.data or [])),     f"{models_done} done / {models_pending} pending")
    table.add_row("Product codes", str(pc_count),                   "")
    table.add_row("Error codes",   str(len(error_codes.data or [])), "")
    table.add_row("Articles",      str(len(articles.data or [])),    "")

    console.print(table)


# ── Pipeline steps ─────────────────────────────────────────────────────────────

def step_models(brand_slug: str, category_slug: str) -> None:
    console.rule(f"[bold blue]Step 1: Scrape models from ManualsLib")
    count = scrape_brand_category(brand_slug, category_slug)
    console.print(f"[green]OK {count} models upserted[/green]\n")


def step_error_codes(brand_slug: str, category_slug: str) -> None:
    console.rule(f"[bold blue]Step 2: Extract error codes from PDFs")
    process_all_pending_models(brand_slug, category_slug)
    console.print(f"[green]OK Error code extraction complete[/green]\n")


def step_articles(brand_slug: str, category_slug: str) -> None:
    console.rule("[bold blue]Step 3: Generate articles via Claude API")
    generate_articles(brand_slug, category_slug)
    console.print("[green]OK Article generation complete[/green]\n")


def step_status(brand_slug: str, category_slug: str) -> None:
    console.rule("[bold blue]Current status")
    print_status(brand_slug, category_slug)


# ── Entry point ────────────────────────────────────────────────────────────────

STEPS = {
    "models":       step_models,
    "error_codes":  step_error_codes,
    "articles":     step_articles,
    "status":       step_status,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Appliance DB pipeline")
    parser.add_argument("--brand",    default="samsung",          help="Brand slug")
    parser.add_argument("--category", default="washing-machines", help="Category slug")
    parser.add_argument("--step",     default="all",              help=f"One of: {list(STEPS)} or 'all'")
    args = parser.parse_args()

    started = datetime.now()
    console.print(f"\n[bold]Appliance DB pipeline[/bold] – {args.brand} / {args.category}")
    console.print(f"Started at {started.strftime('%Y-%m-%d %H:%M:%S')}\n")

    if args.step == "all":
        for name, fn in STEPS.items():
            if name == "status":
                continue  # print status at end only
            fn(args.brand, args.category)
        step_status(args.brand, args.category)
    elif args.step in STEPS:
        STEPS[args.step](args.brand, args.category)
    else:
        console.print(f"[red]Unknown step '{args.step}'. Choose from: {list(STEPS)} or 'all'[/red]")
        sys.exit(1)

    elapsed = datetime.now() - started
    console.print(f"\n[bold green]Pipeline complete in {elapsed}[/bold green]")


if __name__ == "__main__":
    main()
