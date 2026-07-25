"""
pipeline/extract_error_codes.py

Dispatcher: routes each pending model to the right error-code extractor.

Priority:
  1. PDF    — if manual_pdf_url or manual_pdf_path is set, use pdf_extractor.
              Highest fidelity: full text extraction, no API cost.
  2. Image  — if manual_url (ManualsLib viewer) is set, use image_extractor
              (pytesseract OCR on CDN page images). Free, no API cost.
  3. Skip   — neither source available; mark model as 'skipped'.

Usage:
    python -m pipeline.extract_error_codes
    python -m pipeline.extract_error_codes --brand samsung --category washing-machines
    python -m pipeline.extract_error_codes --brand lg --category dryers
    python -m pipeline.extract_error_codes --dry-run   # report only, no extraction
"""

import argparse
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase, refresh_client

console = Console()


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_brand(slug: str) -> Optional[tuple[int, str]]:
    res = supabase.table("brands").select("id,name").eq("slug", slug).single().execute()
    return (res.data["id"], res.data["name"]) if res.data else None


def _get_category_id(slug: str) -> Optional[int]:
    res = supabase.table("categories").select("id").eq("slug_en", slug).single().execute()
    return res.data["id"] if res.data else None


def _pending_models(brand_id: int, category_id: int) -> list[dict]:
    return (
        supabase.table("models")
        .select("id,name,manual_pdf_url,manual_pdf_path,manual_url,scrape_status")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .eq("scrape_status", "pending")
        .execute()
    ).data or []


# ── Routing logic ──────────────────────────────────────────────────────────────

def _route(model: dict) -> str:
    """Return 'pdf', 'image', or 'skip' for this model."""
    if model.get("manual_pdf_url") or model.get("manual_pdf_path"):
        return "pdf"
    if model.get("manual_url"):
        return "image"
    return "skip"


# ── Main dispatcher ────────────────────────────────────────────────────────────

def run(
    brand_slug: str = "samsung",
    category_slug: str = "washing-machines",
    dry_run: bool = False,
) -> None:
    brand_info = _get_brand(brand_slug)
    category_id = _get_category_id(category_slug)

    if not brand_info or not category_id:
        console.print(f"[red]Brand '{brand_slug}' or category '{category_slug}' not found in DB[/red]")
        return

    brand_id, brand_name = brand_info
    models = _pending_models(brand_id, category_id)

    console.print(f"\n[bold]Error code extraction — {brand_slug} / {category_slug}[/bold]")
    console.print(f"Pending models: {len(models)}"
                  + (" [dim](DRY RUN — no extraction)[/dim]" if dry_run else "") + "\n")

    if not models:
        console.print("[dim]Nothing to do.[/dim]")
        return

    # Tally routes
    pdf_models   = [m for m in models if _route(m) == "pdf"]
    image_models = [m for m in models if _route(m) == "image"]
    skip_models  = [m for m in models if _route(m) == "skip"]

    console.print(f"  PDF extraction:   {len(pdf_models)} models")
    console.print(f"  Image extraction: {len(image_models)} models")
    console.print(f"  No source (skip): {len(skip_models)} models\n")

    if dry_run:
        _print_dry_run_table(pdf_models, image_models, skip_models)
        return

    total_codes = 0
    total_errors = 0

    # ── 1. PDF extraction ──────────────────────────────────────────────────────
    if pdf_models:
        console.print("[bold cyan]--- PDF extraction ---[/bold cyan]")
        from scrapers.pdf_extractor import process_model as pdf_process_model

        for i, model in enumerate(pdf_models, 1):
            console.print(f"  [{i}/{len(pdf_models)}] {model['name'][:50]}", end="")
            try:
                count = pdf_process_model(model["id"])
                total_codes += count
                console.print(f" -> [green]{count} codes[/green]")
            except Exception as exc:
                total_errors += 1
                console.print(f" -> [red]ERROR: {exc}[/red]")
                logger.exception(f"PDF extraction failed for model {model['id']}")

            # Refresh Supabase client every 50 models to avoid connection limits
            if i % 50 == 0:
                refresh_client()

    # ── 2. Image extraction ────────────────────────────────────────────────────
    if image_models:
        console.print("\n[bold cyan]--- Image (OCR) extraction ---[/bold cyan]")
        from scrapers.image_extractor import extract_error_codes_for_model

        for i, model in enumerate(image_models, 1):
            console.print(f"  [{i}/{len(image_models)}] {model['name'][:50]}", end="")
            try:
                count = extract_error_codes_for_model(model, brand_id, category_id)
                total_codes += count
                console.print(f" -> [green]{count} codes[/green]")
            except Exception as exc:
                total_errors += 1
                console.print(f" -> [red]ERROR: {exc}[/red]")
                logger.exception(f"Image extraction failed for model {model['id']}")

            if i % 50 == 0:
                refresh_client()

    # ── 3. Mark skipped models ─────────────────────────────────────────────────
    if skip_models:
        ids = [m["id"] for m in skip_models]
        supabase.table("models").update({"scrape_status": "skipped"}).in_("id", ids).execute()
        console.print(f"\n[dim]Marked {len(skip_models)} models as 'skipped' (no PDF or viewer URL)[/dim]")

    console.print(
        f"\n[bold]Done.[/bold] {total_codes} error codes extracted, "
        f"{total_errors} errors, {len(skip_models)} skipped."
    )


def _print_dry_run_table(
    pdf_models: list[dict],
    image_models: list[dict],
    skip_models: list[dict],
) -> None:
    t = Table(title="Extraction plan (dry run)", box=box.SIMPLE, show_header=True)
    t.add_column("Method", width=8)
    t.add_column("Model", width=40)
    t.add_column("Source", width=60)

    for m in pdf_models:
        src = m.get("manual_pdf_url") or m.get("manual_pdf_path") or ""
        t.add_row("[cyan]PDF[/cyan]", m["name"][:40], str(src)[-60:])

    for m in image_models:
        src = m.get("manual_url") or ""
        t.add_row("[blue]Image[/blue]", m["name"][:40], str(src)[-60:])

    for m in skip_models:
        t.add_row("[red]skip[/red]", m["name"][:40], "(no source)")

    console.print(t)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Route pending models to the right error-code extractor"
    )
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Show extraction plan without running anything")
    args = parser.parse_args()

    run(brand_slug=args.brand, category_slug=args.category, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
