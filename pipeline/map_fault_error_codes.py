"""
pipeline/map_fault_error_codes.py

Maps error codes to faults via a curated lookup table.
Populates the fault_error_code_map bridge table.
Idempotent — safe to re-run.

Usage:
    python -m pipeline.map_fault_error_codes --brand samsung --category washing-machines
    python -m pipeline.map_fault_error_codes --brand lg --category washing-machines
    python -m pipeline.map_fault_error_codes --brand samsung --category washing-machines --dry-run
"""

import argparse
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase

console = Console()

# ── Mapping: fault_slug -> list of error code strings ─────────────────────────
# These are the error codes that typically surface when the fault occurs.
# A fault can have zero codes (has_error_code=False) — those are omitted here.

FAULT_CODE_MAP: dict[tuple[str, str], dict[str, list[str]]] = {
    ("samsung", "washing-machines"): {
        "wont-drain":              ["5E", "SE", "5C", "SC", "OC", "OF"],
        "wont-spin":               ["UE", "Ub", "E4", "dc", "DS"],
        "wont-start":              ["dE", "dC", "dF", "d5", "DE"],
        "leaking-water":           ["LE", "LC", "1C"],
        "wont-fill":               ["4E", "4C", "E1"],
        "door-wont-open":          ["dE", "dC", "dF", "d5", "DE"],
        "not-heating-water":       ["tE", "tC", "HE", "HC", "HE1", "HE2", "H1", "H2"],
        "drum-not-turning":        ["3E", "3C", "CE", "EA"],
        "control-panel-unresponsive": ["6E", "bE", "bE1", "bE2", "bE3"],
        "too-much-foam":             ["SUd", "5D", "Sd"],
    },
    ("lg", "washing-machines"): {
        "wont-drain":         ["OE"],
        "wont-spin":          ["UE"],
        "wont-start":         ["dE", "dE1", "dE2"],
        "leaking-water":      ["FE"],
        "wont-fill":          ["IE"],
        "door-wont-open":     ["dE", "dE1", "dE2"],
        "not-heating-water":  ["tE", "tE1", "tE2", "tE3"],
        "drum-not-turning":   ["LE", "CE"],
        "bad-smell":          ["tCL"],
        "child-lock-stuck":   ["CL"],
        "error-code-on-display": ["AE", "EE", "PE", "PS"],
        "wont-complete-cycle":   ["PF"],
    },
    # BSH brands share the same error code set (Bosch and Siemens)
    ("bosch", "washing-machines"): {
        "wont-drain":               ["E20", "E21", "E23", "E24", "E25"],
        "wont-spin":                ["E50", "E52", "E54"],
        "leaking-water":            ["E18", "E27"],
        "wont-fill":                ["E16", "E17", "E18", "E19"],
        "door-wont-open":           ["E44", "E45", "E42"],
        "not-heating-water":        ["E60", "E61", "E62", "E63", "E64", "E65", "E66", "E67", "E68", "E69"],
        "drum-not-turning":         ["E50", "E52"],
        "control-panel-unresponsive": ["E91", "E92"],
        "trips-electrics":          ["E68"],
    },
    ("siemens", "washing-machines"): {
        "wont-drain":               ["E20", "E21", "E23", "E24", "E25"],
        "wont-spin":                ["E50", "E52", "E54"],
        "leaking-water":            ["E18", "E27"],
        "wont-fill":                ["E16", "E17", "E18", "E19"],
        "door-wont-open":           ["E44", "E45", "E42"],
        "not-heating-water":        ["E60", "E61", "E62", "E63", "E64", "E65", "E66", "E67", "E68", "E69"],
        "drum-not-turning":         ["E50", "E52"],
        "control-panel-unresponsive": ["E91", "E92"],
        "trips-electrics":          ["E68"],
    },
    ("electrolux", "washing-machines"): {
        "wont-drain":               ["E20", "E21", "E23", "E24", "E25"],
        "wont-spin":                ["E50", "E52", "E54", "E59"],
        "leaking-water":            ["E13", "EF0", "EF1"],
        "wont-fill":                ["E10", "E11"],
        "door-wont-open":           ["E40", "E41", "E42", "E44", "E45"],
        "not-heating-water":        ["E60", "E61", "E62", "E66", "E68", "E71"],
        "drum-not-turning":         ["E50", "E51", "E52", "E54"],
        "control-panel-unresponsive": ["E91", "E92", "E93", "E94"],
        "trips-electrics":          ["E68"],
        "wont-complete-cycle":      ["E30", "E31", "E35"],
    },
}


# ── Mapping logic ──────────────────────────────────────────────────────────────

def map_codes(brand_slug: str, category_slug: str, dry_run: bool = False) -> int:
    key = (brand_slug, category_slug)
    mapping = FAULT_CODE_MAP.get(key)
    if not mapping:
        console.print(f"[yellow]No mapping defined for {brand_slug}/{category_slug}[/yellow]")
        return 0

    brand    = supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    category = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()
    if not brand.data or not category.data:
        console.print(f"[red]Brand '{brand_slug}' or category '{category_slug}' not found[/red]")
        return 0

    brand_id    = brand.data["id"]
    category_id = category.data["id"]
    brand_name  = brand.data["name"]

    # Load all faults for this brand/category
    faults_res = (
        supabase.table("faults")
        .select("id,slug")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    )
    fault_by_slug = {r["slug"]: r["id"] for r in (faults_res.data or [])}

    # Load all error codes for this brand/category
    codes_res = (
        supabase.table("error_codes")
        .select("id,code")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    )
    code_by_name = {r["code"]: r["id"] for r in (codes_res.data or [])}

    # Build rows to insert
    rows_to_insert: list[dict] = []
    warnings: list[str] = []

    t = Table(title=f"Fault -> Error code mapping — {brand_name} / {category_slug}", box=box.SIMPLE)
    t.add_column("Fault slug",   style="bold", width=30)
    t.add_column("Error codes",  width=50)
    t.add_column("Missing",      style="yellow", width=20)

    for fault_slug, code_list in mapping.items():
        fault_id = fault_by_slug.get(fault_slug)
        if not fault_id:
            warnings.append(f"Fault '{fault_slug}' not found in DB — seed faults first")
            t.add_row(fault_slug, "-", "FAULT MISSING")
            continue

        found   = []
        missing = []
        for code_str in code_list:
            ec_id = code_by_name.get(code_str)
            if ec_id:
                found.append(code_str)
                rows_to_insert.append({"fault_id": fault_id, "error_code_id": ec_id})
            else:
                missing.append(code_str)

        t.add_row(
            fault_slug,
            ", ".join(found) if found else "[dim]none[/dim]",
            ", ".join(missing) if missing else "",
        )

    console.print(t)

    if warnings:
        console.print()
        for w in warnings:
            console.print(f"[yellow]Warning: {w}[/yellow]")

    console.print(f"\n{len(rows_to_insert)} fault-code links to insert.")

    if dry_run:
        console.print("[dim]Dry run — no DB writes.[/dim]")
        return 0

    if not rows_to_insert:
        console.print("[dim]Nothing to insert.[/dim]")
        return 0

    # Idempotent upsert in batches of 200
    BATCH = 200
    inserted = 0
    for i in range(0, len(rows_to_insert), BATCH):
        batch = rows_to_insert[i : i + BATCH]
        supabase.table("fault_error_code_map").upsert(batch, on_conflict="fault_id,error_code_id").execute()
        inserted += len(batch)

    console.print(f"[bold green]Inserted/updated {inserted} fault-error_code links.[/bold green]")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Map error codes to faults")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()
    map_codes(args.brand, args.category, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
