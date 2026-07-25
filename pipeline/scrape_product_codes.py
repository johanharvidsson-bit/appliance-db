"""
pipeline/scrape_product_codes.py

Unified runner for all marketplace product-code scrapers:
  - eSpares    (espares.co.uk)   → market='GB'
  - FixPart    (fixpart.co.uk)   → market='EU'
  - AppliancePartsPros           → market='US'

For each brand × category combination (filtered to those with known config),
runs each scraper in sequence and reports totals.

Usage:
    python -m pipeline.scrape_product_codes
    python -m pipeline.scrape_product_codes --brands samsung lg --categories washing-machines
    python -m pipeline.scrape_product_codes --sources espares fixpart
    python -m pipeline.scrape_product_codes --brands samsung --categories washing-machines dryers
"""

import argparse
import time
from datetime import datetime

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import (
    ACTIVE_BRAND_SLUGS,
    ACTIVE_CATEGORY_SLUGS,
    ESPARES_CONFIG,
    FIXPART_CATEGORY_PATHS,
    FIXPART_BRAND_NAMES,
    APPP_PREFIXES,
)

console = Console()

ALL_SOURCES = ["espares", "fixpart", "appliancepartspros"]


def _run_espares(brand_slug: str, category_slug: str) -> int:
    from scrapers.espares import scrape_all
    return scrape_all(brand_slug, category_slug)


def _run_fixpart(brand_slug: str, category_slug: str) -> int:
    from scrapers.fixpart import scrape_all
    return scrape_all(brand_slug, category_slug)


def _run_appliancepartspros(brand_slug: str, category_slug: str) -> int:
    from scrapers.appliancepartspros import scrape_all
    return scrape_all(brand_slug, category_slug)


_SOURCE_FNS = {
    "espares":           _run_espares,
    "fixpart":           _run_fixpart,
    "appliancepartspros": _run_appliancepartspros,
}


def _is_configured(source: str, brand_slug: str, category_slug: str) -> bool:
    """Return True if this source has config for this brand/category combo."""
    if source == "espares":
        return (brand_slug, category_slug) in ESPARES_CONFIG
    if source == "fixpart":
        return (
            category_slug in FIXPART_CATEGORY_PATHS
            and brand_slug in FIXPART_BRAND_NAMES
        )
    if source == "appliancepartspros":
        return (brand_slug, category_slug) in APPP_PREFIXES
    return False


def run_all(
    brands: list[str],
    categories: list[str],
    sources: list[str],
) -> list[dict]:
    """
    Run the specified marketplace scrapers for all brand × category combos.
    Returns a list of result dicts.
    """
    results = []

    combos = [(b, c) for b in brands for c in categories]
    total = len(combos) * len(sources)
    done = 0

    started = datetime.now()
    console.print(f"\n[bold]Product code scrape[/bold] — {len(combos)} combos × {len(sources)} sources = {total} runs")
    console.print(f"Brands:     {', '.join(brands)}")
    console.print(f"Categories: {', '.join(categories)}")
    console.print(f"Sources:    {', '.join(sources)}")
    console.print(f"Started:    {started.strftime('%Y-%m-%d %H:%M:%S')}\n")

    for brand_slug, category_slug in combos:
        combo_result = {
            "brand":    brand_slug,
            "category": category_slug,
        }
        for source in sources:
            done += 1
            console.rule(f"[bold blue][{done}/{total}] {source} — {brand_slug} / {category_slug}")

            if not _is_configured(source, brand_slug, category_slug):
                console.print(f"  [dim]No config for {source} {brand_slug}/{category_slug} — skipped[/dim]")
                combo_result[source] = "no_config"
                continue

            try:
                inserted = _SOURCE_FNS[source](brand_slug, category_slug)
                combo_result[source] = inserted
            except Exception as exc:
                logger.error(f"{source} {brand_slug}/{category_slug} failed: {exc}")
                combo_result[source] = f"error: {exc}"

            time.sleep(2)

        results.append(combo_result)

    return results


def print_summary(results: list[dict], sources: list[str]) -> None:
    t = Table(title="Product Code Scrape Summary", box=box.SIMPLE, show_header=True)
    t.add_column("Brand",    style="bold")
    t.add_column("Category")
    for source in sources:
        t.add_column(source.capitalize(), justify="right")

    for r in results:
        row_vals = [r["brand"], r["category"]]
        for source in sources:
            val = r.get(source, "—")
            if isinstance(val, int):
                color = "green" if val > 0 else "dim"
                row_vals.append(f"[{color}]+{val}[/{color}]")
            elif val == "no_config":
                row_vals.append("[dim]—[/dim]")
            else:
                row_vals.append(f"[red]{str(val)[:20]}[/red]")
        t.add_row(*row_vals)

    console.print(t)

    # Totals
    for source in sources:
        total = sum(r.get(source, 0) for r in results if isinstance(r.get(source), int))
        console.print(f"  {source}: [green]+{total}[/green] new product_codes")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape product codes from all marketplaces")
    parser.add_argument("--brands",     nargs="+", default=ACTIVE_BRAND_SLUGS)
    parser.add_argument("--categories", nargs="+", default=ACTIVE_CATEGORY_SLUGS)
    parser.add_argument(
        "--sources", nargs="+", default=ALL_SOURCES,
        choices=ALL_SOURCES,
        help="Which sources to scrape (default: all)",
    )
    args = parser.parse_args()

    results = run_all(args.brands, args.categories, args.sources)

    elapsed = datetime.now() - datetime.now()  # placeholder
    console.print(f"\n[bold]Done.[/bold]\n")
    print_summary(results, args.sources)


if __name__ == "__main__":
    main()
