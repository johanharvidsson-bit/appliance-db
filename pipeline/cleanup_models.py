"""
pipeline/cleanup_models.py

Cleans up the raw ManualsLib model data before error code extraction.

Three operations (dry-run by default, use --execute to commit):

  1. DELETE JUNK  – removes clearly invalid rows (wrong category, pure numbers,
                    part-number codes, etc.)

  2. DEDUPLICATE  – for each unique PDF URL, identifies distinct model families
                    sharing that PDF, keeps one canonical row per family, and
                    stores all other variant names as product_codes rows.

  3. PRODUCT LINES – groups canonical models by common prefix and creates
                     product_lines rows, linking each model to its line.

Usage:
    python -m pipeline.cleanup_models                  # dry-run report
    python -m pipeline.cleanup_models --execute        # commit changes
    python -m pipeline.cleanup_models --brand samsung --category washing-machines
"""

import argparse
import re
import collections
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase

console = Console()


# ── Junk detection ─────────────────────────────────────────────────────────────

def junk_reason(name: str) -> Optional[str]:
    n = name.strip()
    if n.startswith(")"):                           return "starts with )"
    if re.match(r"^\d+[A-Z]?$", n):                return "bare number code"
    if re.match(r"^\d+ ?[Ss]eries?$", n):          return "number + Series"
    if re.match(r"^[56789] [Ss]eries", n, re.I):   return "number + Series"
    if re.match(r"^592-", n):                       return "part-number pattern"
    if "SyncMaster" in n:                           return "wrong product (monitor)"
    if re.match(r"^[A-Z]\d+$", n) and len(n) <= 3: return "too short / generic"
    if re.match(r"^[WPQR]\d{3}$", n):              return "3-digit model fragment"
    return None


# ── Model family extraction ────────────────────────────────────────────────────

def model_family(name: str) -> str:
    """
    Extract the base family prefix from a model name so that colour/market
    variants cluster together.

    Examples:
      B1075C, B1075S, B1075V, B1075(V/S/C)  → "B1075"
      WF45T6000AW, WF45T6000AV               → "WF45T6000A"
      WF45T6000A Series                       → "WF45T6000A"
      Q1044(C/S/V), Q1044C, Q1044S           → "Q1044"
      B1445A, B1445AS, B1445AV               → "B1445A"  (A is base, S/V are variants)
    """
    n = name.strip()

    # Strip trailing market suffixes: /AA, /XAC, /US, etc.
    n = re.sub(r"\s*/[A-Z0-9]{2,4}$", "", n)
    # Strip "(V/S/C)" style variant specs
    n = re.sub(r"\s*\([^)]*[/][^)]*\)", "", n)
    # Strip "Series" suffix
    n = re.sub(r"\s+[Ss]eries$", "", n)
    n = n.strip()

    # Old Samsung style: letter + 4 digits + optional variant letters
    # B1075C → B1075 | B1445AS → B1445A | B1445A → B1445A
    m = re.match(r"^([A-Z]\d{4}[A-Z]?)[A-Z]{1,2}$", n)
    if m:
        return m.group(1)

    # Old Samsung bare base: B1075, B1445A → keep as-is
    if re.match(r"^[A-Z]\d{4}[A-Z]?$", n):
        return n

    # New Samsung / LG style: 2 letters + 2 digits + alphanumeric series
    # WF45T6000AW → WF45T6000A  (strip trailing 1-letter colour code)
    # WA47CG3500AVA4 → WA47CG3500A  (strip trailing market code)
    m = re.match(r"^([A-Z]{2}\d{2}[A-Z][0-9][0-9]{3}[A-Z])[A-Z0-9]{1,3}$", n)
    if m:
        return m.group(1)

    # Old Q/F/J series: Q1044C → Q1044
    m = re.match(r"^([QFJ]\d{4})[A-Z]{1,3}$", n)
    if m:
        return m.group(1)

    return n


# ── Canonical model selection ──────────────────────────────────────────────────

def pick_canonical(models: list[dict], pdf_url: str) -> dict:
    """
    From a list of model rows sharing one PDF + one family prefix,
    pick the single row that best represents the family.

    Preference order:
      1. Name ending in "Series"
      2. Name matching the PDF filename most closely
      3. Shortest name (most generic)
    """
    pdf_stem = (
        pdf_url.split("/")[-1]
        .replace(".html", "")
        .replace("Samsung-", "")
        .replace("-", "")
        .lower()
    )

    def score(row):
        n = row["name"]
        is_series = 10 if re.search(r"[Ss]eries$", n) else 0
        clean = re.sub(r"[\s()/]", "", n).lower()
        match_len = len(
            "".join(
                c for c, d in zip(clean, pdf_stem) if c == d
            )
        )
        length_penalty = len(n)
        return is_series * 100 + match_len * 5 - length_penalty

    return max(models, key=score)


# ── Main analysis ──────────────────────────────────────────────────────────────

def analyse(brand_id: int, category_id: int):
    """
    Returns a dict with all the planned operations.
    Nothing is written to the DB here.
    """
    models = (
        supabase.table("models")
        .select("id,name,slug,manual_pdf_url,product_line_id")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    ).data or []

    # --- Step 1: split junk vs valid ---
    junk_rows  = [r for r in models if junk_reason(r["name"])]
    valid_rows = [r for r in models if not junk_reason(r["name"])]

    # --- Step 2: group valid rows by PDF → family ---
    # Key: (pdf_url, family_prefix)
    clusters: dict[tuple, list] = collections.defaultdict(list)
    for row in valid_rows:
        family = model_family(row["name"])
        clusters[(row["manual_pdf_url"], family)].append(row)

    to_keep:   list[dict] = []   # one row per cluster (the canonical)
    to_delete: list[dict] = []   # duplicates → become product_codes
    product_codes_to_add: list[dict] = []  # (model_id_placeholder, name)

    for (pdf_url, family), members in clusters.items():
        canonical = pick_canonical(members, pdf_url or "")
        to_keep.append({**canonical, "_family": family, "_pdf": pdf_url, "_variants": members})
        for m in members:
            if m["id"] != canonical["id"]:
                to_delete.append(m)
                product_codes_to_add.append({
                    "canonical_name": canonical["name"],
                    "canonical_id":   canonical["id"],
                    "variant_name":   m["name"],
                })

    # --- Step 3: product lines ---
    # Group canonical models by family prefix → one product_line per group
    line_groups: dict[str, list] = collections.defaultdict(list)
    for row in to_keep:
        line_groups[row["_family"]].append(row)

    product_lines_to_create: list[dict] = []
    for family, members in line_groups.items():
        if len(members) > 0:
            product_lines_to_create.append({
                "family":  family,
                "slug":    re.sub(r"[^a-z0-9]+", "-", family.lower()).strip("-"),
                "members": members,
            })

    return {
        "total":                   len(models),
        "junk":                    junk_rows,
        "to_keep":                 to_keep,
        "to_delete":               to_delete,
        "product_codes_to_add":    product_codes_to_add,
        "product_lines_to_create": product_lines_to_create,
        "unique_pdfs":             len(set(r["manual_pdf_url"] for r in valid_rows)),
        "clusters":                len(clusters),
    }


# ── Report ─────────────────────────────────────────────────────────────────────

def print_report(result: dict, brand_slug: str, category_slug: str) -> None:
    console.print(f"\n[bold]Cleanup report - {brand_slug} / {category_slug}[/bold]\n")

    # Summary table
    t = Table(box=box.SIMPLE, show_header=True)
    t.add_column("Metric", style="bold")
    t.add_column("Count", justify="right")
    t.add_row("Total model rows (current)",              str(result["total"]))
    t.add_row("Junk rows to delete",                     f"[red]{len(result['junk'])}[/red]")
    t.add_row("Unique PDFs (valid rows)",                str(result["unique_pdfs"]))
    t.add_row("Model family clusters",                   str(result["clusters"]))
    t.add_row("Canonical models to keep",                f"[green]{len(result['to_keep'])}[/green]")
    t.add_row("Duplicate rows to remove",                f"[yellow]{len(result['to_delete'])}[/yellow]")
    t.add_row("Variant names -> product_codes",           str(len(result["product_codes_to_add"])))
    t.add_row("Product lines to create",                 str(len(result["product_lines_to_create"])))
    console.print(t)

    # Junk detail
    console.print("\n[bold red]Junk rows to delete:[/bold red]")
    for r in sorted(result["junk"], key=lambda x: x["name"]):
        console.print(f"  [{junk_reason(r['name'])}]  {r['name']}")

    # Largest clusters
    big_clusters = sorted(
        [r for r in result["to_keep"] if len(r["_variants"]) > 3],
        key=lambda x: len(x["_variants"]),
        reverse=True,
    )[:10]
    if big_clusters:
        console.print(f"\n[bold yellow]Largest clusters (canonical -> variants):[/bold yellow]")
        for row in big_clusters:
            variants = [v["name"] for v in row["_variants"] if v["id"] != row["id"]]
            console.print(f"  [green]{row['name']}[/green]  ({len(row['_variants'])} models in PDF)")
            console.print(f"    variants -> product_codes: {', '.join(variants[:6])}"
                          + (f" +{len(variants)-6} more" if len(variants) > 6 else ""))


# ── Execute ────────────────────────────────────────────────────────────────────

def execute(result: dict, brand_id: int, category_id: int) -> None:
    console.print("\n[bold]Executing cleanup...[/bold]")

    # 1. Delete junk
    junk_ids = [r["id"] for r in result["junk"]]
    if junk_ids:
        supabase.table("models").delete().in_("id", junk_ids).execute()
        console.print(f"  [red]Deleted {len(junk_ids)} junk rows[/red]")

    # 2. Delete duplicate models (variants), but first collect product_code inserts
    #    We need canonical IDs which are already correct (they stay in DB)
    pc_rows = [
        {
            "model_id":     pc["canonical_id"],
            "code":         pc["variant_name"][:100],
            "scrape_status": "done",
        }
        for pc in result["product_codes_to_add"]
    ]
    if pc_rows:
        # Batch upsert product_codes
        batch = 200
        for i in range(0, len(pc_rows), batch):
            supabase.table("product_codes").upsert(
                pc_rows[i:i+batch], on_conflict="model_id,code"
            ).execute()
        console.print(f"  [cyan]Inserted {len(pc_rows)} product_codes[/cyan]")

    dup_ids = [r["id"] for r in result["to_delete"]]
    if dup_ids:
        batch = 200
        for i in range(0, len(dup_ids), batch):
            supabase.table("models").delete().in_("id", dup_ids[i:i+batch]).execute()
        console.print(f"  [yellow]Deleted {len(dup_ids)} duplicate model rows[/yellow]")

    # 3. Create product_lines and link canonical models
    created_lines = 0
    linked_models = 0
    for line in result["product_lines_to_create"]:
        # Only create a product_line if there are multiple models in the family
        # (single-model families don't need a line)
        if len(line["members"]) < 2:
            continue

        res = supabase.table("product_lines").upsert(
            {
                "brand_id":    brand_id,
                "category_id": category_id,
                "name":        line["family"],
                "slug":        line["slug"],
            },
            on_conflict="brand_id,category_id,slug",
        ).execute()

        if res.data:
            line_id = res.data[0]["id"]
        else:
            # Already exists – fetch it
            existing = (
                supabase.table("product_lines")
                .select("id")
                .eq("brand_id", brand_id)
                .eq("category_id", category_id)
                .eq("slug", line["slug"])
                .single()
                .execute()
            )
            line_id = existing.data["id"] if existing.data else None

        if line_id:
            member_ids = [m["id"] for m in line["members"]]
            supabase.table("models").update(
                {"product_line_id": line_id}
            ).in_("id", member_ids).execute()
            created_lines += 1
            linked_models += len(member_ids)

    console.print(f"  [green]Created {created_lines} product lines, linked {linked_models} models[/green]")

    console.print("\n[bold green]Cleanup complete.[/bold green]")
    console.print("Run [bold]python -m pipeline.validate[/bold] to confirm data quality.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Clean up scraped model data")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--execute",  action="store_true",
                        help="Actually commit changes (default is dry-run report only)")
    args = parser.parse_args()

    brand    = supabase.table("brands").select("id,name").eq("slug", args.brand).single().execute()
    category = supabase.table("categories").select("id").eq("slug_en", args.category).single().execute()

    if not brand.data or not category.data:
        console.print(f"[red]Brand '{args.brand}' or category '{args.category}' not found[/red]")
        return

    result = analyse(brand.data["id"], category.data["id"])
    print_report(result, args.brand, args.category)

    if args.execute:
        execute(result, brand.data["id"], category.data["id"])
    else:
        console.print(
            "\n[dim]Dry run. Add [bold]--execute[/bold] to commit changes.[/dim]"
        )


if __name__ == "__main__":
    main()
