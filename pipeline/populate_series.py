"""
pipeline/populate_series.py

Derives and populates the `series` column on the models table.

Series is the short model-family key used for UI grouping, e.g.:
  WW80K, WW90T, WF45T  (new Samsung style)
  B1045, B1245, J1055   (old Samsung B/F/J style)
  FlexWash WV60M        (FlexWash sub-brand)
  WF                    (legacy WF - style)

The derivation is intentionally conservative — when uncertain it falls
back to the first 5 characters of base_model so nothing is left NULL.
Rows can be manually corrected in the DB without re-running this script.

Usage:
    python -m pipeline.populate_series                              # all brands/categories
    python -m pipeline.populate_series --brand samsung             # one brand, all categories
    python -m pipeline.populate_series --brand samsung --category washing-machines
    python -m pipeline.populate_series --overwrite                 # re-derive already-set rows
    python -m pipeline.populate_series --dry-run                   # print without writing
"""

import re
import argparse
import collections
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase, ACTIVE_BRAND_SLUGS, ACTIVE_CATEGORY_SLUGS

console = Console()


# ── Series derivation ──────────────────────────────────────────────────────────

def derive_series(base_model: Optional[str]) -> Optional[str]:
    """
    Extract the series key from a base_model string.
    Returns None only if base_model is empty.
    """
    n = (base_model or "").strip()
    if not n:
        return None

    # Strip known marketing prefixes so the model number drives the series
    n_clean = re.sub(r"^(FlexWash|AddWash|BESPOKE|ECOBUBBLE|QuickDrive)\s+", "", n, flags=re.I)

    # New Samsung / LG style: 2 letters + 2 digits + letter  e.g. WW80K, WF45T, WV60M
    m = re.match(r"^([A-Z]{2}\d{2}[A-Z])", n_clean)
    if m:
        prefix = m.group(1)
        # If a marketing word was stripped, include it for readability
        stripped = n[: len(n) - len(n_clean)].strip()
        return f"{stripped} {prefix}" if stripped else prefix

    # Old Samsung dryer style: 2 letters + 3 digits + letter  e.g. DV220A, DV410A, DV419A
    m = re.match(r"^([A-Z]{2}\d{3}[A-Z]?)", n_clean)
    if m and len(m.group(1)) >= 5:
        return m.group(1)

    # Old Samsung / European B/F/J/Q/P style: letter + 4 digits  e.g. B1045, F1245, J1055
    m = re.match(r"^([A-Z]\d{4})", n_clean)
    if m:
        return m.group(1)

    # Miele G-series: "G 5000 SC", "G 6000" → "G 5000", "G 6000"
    m = re.match(r"^(G\s*\d{4})", n_clean)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()

    # WF - legacy style:  "WF - 0702NBS"  →  "WF"
    if re.match(r"^WF\s*-", n_clean):
        return "WF"

    # Hyphenated commercial/portable series: P-WM, SWF-P
    m = re.match(r"^([A-Z]{1,3}-[A-Z]{1,4})", n_clean)
    if m:
        return m.group(1)

    # Alphanumeric prefix before digits: SW70, SWF, etc.
    m = re.match(r"^([A-Z]{2,5})\d", n_clean)
    if m:
        return m.group(1)

    # Fallback: first 5 characters
    return n_clean[:5] if len(n_clean) >= 5 else n_clean


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_brand_ids(brand_slug: Optional[str]) -> list[tuple[int, str]]:
    if brand_slug:
        res = supabase.table("brands").select("id,slug").eq("slug", brand_slug).execute()
    else:
        res = supabase.table("brands").select("id,slug").in_("slug", ACTIVE_BRAND_SLUGS).execute()
    return [(r["id"], r["slug"]) for r in (res.data or [])]


def _get_category_ids(category_slug: Optional[str]) -> list[int]:
    if category_slug:
        res = supabase.table("categories").select("id").eq("slug_en", category_slug).execute()
    else:
        res = supabase.table("categories").select("id").in_("slug_en", ACTIVE_CATEGORY_SLUGS).execute()
    return [r["id"] for r in (res.data or [])]


# ── Main ───────────────────────────────────────────────────────────────────────

def run(
    brand_slug: Optional[str] = None,
    category_slug: Optional[str] = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> None:
    brand_ids   = _get_brand_ids(brand_slug)
    category_ids = _get_category_ids(category_slug)

    if not brand_ids or not category_ids:
        console.print("[red]No matching brands or categories found[/red]")
        return

    all_brand_ids = [b[0] for b in brand_ids]

    q = supabase.table("models").select("id,name,base_model,series")
    if len(all_brand_ids) == 1:
        q = q.eq("brand_id", all_brand_ids[0])
    else:
        q = q.in_("brand_id", all_brand_ids)
    if len(category_ids) == 1:
        q = q.eq("category_id", category_ids[0])
    else:
        q = q.in_("category_id", category_ids)
    if not overwrite:
        q = q.is_("series", "null")

    models = q.execute().data or []

    console.print(f"\n[bold]Populate series[/bold] — {len(models)} models to process"
                  + (" [dim](DRY RUN)[/dim]" if dry_run else "")
                  + (" [dim](overwrite)[/dim]" if overwrite else "") + "\n")

    if not models:
        console.print("[dim]Nothing to do.[/dim]")
        return

    # Derive series for each model
    updates: list[tuple[int, str]] = []
    no_series: list[str] = []
    series_counts: collections.Counter = collections.Counter()

    for m in models:
        s = derive_series(m["base_model"] or m["name"])
        if s:
            updates.append((m["id"], s))
            series_counts[s] += 1
        else:
            no_series.append(m["name"])

    console.print(f"  Derived {len(updates)} series values, {len(no_series)} could not be derived")
    console.print(f"  Unique series: {len(series_counts)}\n")

    if not dry_run:
        # Batch updates — Supabase REST doesn't support bulk updates, do in batches
        ok = 0
        for model_id, series in updates:
            res = supabase.table("models").update({"series": series}).eq("id", model_id).execute()
            if res.data:
                ok += 1
        console.print(f"[green]Updated {ok}/{len(updates)} models[/green]")
    else:
        # Show preview table of top series
        t = Table(title="Series preview (top 25)", box=box.SIMPLE)
        t.add_column("Series", style="bold")
        t.add_column("Models", justify="right")
        for series, count in series_counts.most_common(25):
            t.add_row(series, str(count))
        console.print(t)

    if no_series:
        console.print(f"\n[yellow]Could not derive series for:[/yellow]")
        for name in no_series[:20]:
            console.print(f"  {name}")
        if len(no_series) > 20:
            console.print(f"  ... and {len(no_series) - 20} more")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Populate models.series from base_model")
    parser.add_argument("--brand",     default=None, help="Brand slug (default: all active)")
    parser.add_argument("--category",  default=None, help="Category slug (default: all active)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-derive even rows that already have a series value")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Print preview without writing to DB")
    args = parser.parse_args()

    run(
        brand_slug=args.brand,
        category_slug=args.category,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
