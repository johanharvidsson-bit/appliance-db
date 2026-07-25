"""
pipeline/cleanup_models.py

Cleans up the raw ManualsLib model data before error code extraction.

Four operations (dry-run by default, use --execute to commit):

  0. NORMALISE    – strips "Series" suffix, strips leading product-designation
                    words (e.g. "VRT STEAM"), and expands slash-variant notation
                    (e.g. "Q1657(T/S/V)" → model renamed to "Q1657",
                     Q1657T/Q1657S/Q1657V added as product_codes).

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


# ── Name normalisation ─────────────────────────────────────────────────────────

# Marketing/designation words that appear before the real model code
_DESIGNATION_WORDS = re.compile(
    r'^(VRT(\s+STEAM)?|SILVER(\s*CARE)?|SLIM\s*FIT|AEGIS|SILVER\s*NANO(\s+HEALTH(\s+SYSTEM)?)?'
    r'|ECOBUBBLE|ADDWASH|QUICKDRIVE|BESPOKE|CRYSTAL\s*BLUE|AI\s*CONTROL'
    r'|FRONT\s*LOAD(ER)?|TOP\s*LOAD(ER)?)\s+',
    re.I,
)

def normalize_model_name(name: str) -> str:
    """
    Clean a raw ManualsLib model name:
      1. Strip trailing " Series" (case-insensitive)
      2. Strip firmware/revision suffixes e.g. "/A5-00", "/A5-01"
      3. Strip leading product-designation words (e.g. "VRT STEAM ", "SilverCare ")
      4. Normalise known product-line prefix casing (e.g. "FLEXWASH" → "FlexWash")
    """
    n = name.strip()
    # Strip " Series" suffix with optional leading digit e.g. "5 Series", "SERIES" (any casing)
    n = re.sub(r'\s+\d*\s*series$', '', n, flags=re.I).strip()
    # Strip firmware revision suffixes like /A5-00, /A5-01, /A5-0
    n = re.sub(r'\s*/[A-Z]\d+-\d+$', '', n).strip()
    # Strip leading designation words
    n = _DESIGNATION_WORDS.sub('', n).strip()
    # Normalise known product-line prefix casing
    n = re.sub(r'^flexwash\b', 'FlexWash', n, flags=re.I)
    return n


def expand_slash_variants(name: str) -> list[str]:
    """
    Expand slash-variant notation into individual model codes.
    Returns an empty list if no expansion is needed.

    Examples:
      Q1657(T/S/V)    → ['Q1657T', 'Q1657S', 'Q1657V']
      B1045(V/S/C)    → ['B1045V', 'B1045S', 'B1045C']
      Q1657A(V/T/S)   → ['Q1657AV', 'Q1657AT', 'Q1657AS']
      WF419AAW        → []   (no expansion)
    """
    m = re.match(r'^(.*?)\(([^)]+/[^)]+)\)(.*)$', name.strip())
    if not m:
        return []
    prefix, variants_str, suffix = m.group(1).strip(), m.group(2), m.group(3).strip()
    variants = [v.strip() for v in variants_str.split('/')]
    return [f"{prefix}{v}{suffix}".strip() for v in variants if v]


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

    # Strip firmware revision suffixes: /A5-00, /A5-01, /A5-0
    n = re.sub(r"\s*/[A-Z]\d+-\d+$", "", n)
    # Strip trailing market suffixes: /AA, /XAC, /US, etc.
    n = re.sub(r"\s*/[A-Z0-9]{2,4}$", "", n)
    # Strip "(V/S/C)" style variant specs
    n = re.sub(r"\s*\([^)]*[/][^)]*\)", "", n)
    # Strip "Series" suffix
    n = re.sub(r"\s+[Ss]eries$", "", n)
    n = n.strip()

    # Old Samsung 7-char with base letter: B1445AS → B1445A  (strip trailing colour letter)
    m = re.match(r"^([A-Z]\d{4}[A-Z])[A-Z]{1,2}$", n)
    if m:
        return m.group(1)

    # Old Samsung 6-char colour variant: B1075C → B1075  (C/S/V/W/X are colour codes)
    # B1445A is NOT matched here (A is a base/generation suffix, not a colour code)
    m = re.match(r"^([A-Z]\d{4})([CSWVX])$", n)
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

    # --- Step 0: normalise names + expand slash variants ---
    names_to_normalize: dict[int, str] = {}   # model_id → cleaned name
    slash_expansions: list[dict] = []         # models to rename + expand

    for row in models:
        # Expand slash variants first (before normalization)
        variants = expand_slash_variants(row["name"])
        if variants:
            base = re.sub(r'\s*\([^)]*[/][^)]*\)', '', row["name"]).strip()
            base = normalize_model_name(base)
            slash_expansions.append({
                "model_id":      row["id"],
                "original_name": row["name"],
                "base_name":     base,
                "variants":      [normalize_model_name(v) for v in variants],
            })
            # Update the row's name in memory for subsequent steps
            row = {**row, "name": base}
        else:
            cleaned = normalize_model_name(row["name"])
            if cleaned != row["name"]:
                names_to_normalize[row["id"]] = cleaned
                row = {**row, "name": cleaned}

    # Rebuild models list with normalized names applied in memory
    slash_ids = {e["model_id"] for e in slash_expansions}
    models_normalized = []
    for row in models:
        if row["id"] in slash_ids:
            exp = next(e for e in slash_expansions if e["model_id"] == row["id"])
            models_normalized.append({**row, "name": exp["base_name"]})
        elif row["id"] in names_to_normalize:
            models_normalized.append({**row, "name": names_to_normalize[row["id"]]})
        else:
            models_normalized.append(row)
    models = models_normalized

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
        "names_to_normalize":      names_to_normalize,
        "slash_expansions":        slash_expansions,
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
    t.add_row("Names to normalise",                      f"[cyan]{len(result['names_to_normalize'])}[/cyan]")
    t.add_row("Slash variants to expand",                f"[cyan]{len(result['slash_expansions'])}[/cyan]")
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

    # 0a. Normalise model names
    normalised = 0
    for model_id, new_name in result["names_to_normalize"].items():
        new_slug = re.sub(r"[^a-z0-9]+", "-", new_name.lower()).strip("-")
        # Skip if the target slug already belongs to a different model
        conflict = (
            supabase.table("models")
            .select("id")
            .eq("brand_id", brand_id)
            .eq("category_id", category_id)
            .eq("slug", new_slug)
            .execute()
        ).data
        if conflict and conflict[0]["id"] != model_id:
            logger.debug(f"Skipping normalise for id={model_id}: slug '{new_slug}' already taken")
            continue
        supabase.table("models").update(
            {"name": new_name, "slug": new_slug}
        ).eq("id", model_id).execute()
        normalised += 1
    if normalised:
        console.print(f"  [cyan]Normalised {normalised} model names[/cyan]")

    # 0b. Expand slash variants
    deleted_in_step0: set[int] = set()  # model IDs deleted here — skip in later steps
    expanded_count = 0
    merged_count = 0
    for exp in result["slash_expansions"]:
        base = exp["base_name"]
        new_slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")

        # Check if a model with this base slug already exists
        existing = (
            supabase.table("models")
            .select("id")
            .eq("brand_id", brand_id)
            .eq("category_id", category_id)
            .eq("slug", new_slug)
            .execute()
        ).data
        existing_id = existing[0]["id"] if existing else None

        if existing_id and existing_id != exp["model_id"]:
            # Base already exists as a separate row — delete the slash-variant row,
            # add product_codes to the existing base model
            target_id = existing_id
            supabase.table("models").delete().eq("id", exp["model_id"]).execute()
            deleted_in_step0.add(exp["model_id"])
            merged_count += 1
        else:
            # Safe to rename
            target_id = exp["model_id"]
            supabase.table("models").update(
                {"name": base, "slug": new_slug}
            ).eq("id", exp["model_id"]).execute()
            expanded_count += 1

        for variant in exp["variants"]:
            supabase.table("product_codes").upsert(
                {"model_id": target_id, "code": variant[:100], "scrape_status": "done"},
                on_conflict="code",
                ignore_duplicates=True,
            ).execute()

    if expanded_count or merged_count:
        console.print(
            f"  [cyan]Slash variants: {expanded_count} renamed, "
            f"{merged_count} merged into existing base models[/cyan]"
        )

    # 1. Delete junk
    junk_ids = [r["id"] for r in result["junk"]]
    if junk_ids:
        supabase.table("models").delete().in_("id", junk_ids).execute()
        console.print(f"  [red]Deleted {len(junk_ids)} junk rows[/red]")

    # 2. Delete duplicate models (variants), but first collect product_code inserts
    #    Skip any entries whose canonical or variant IDs were deleted in step 0b
    pc_rows = [
        {
            "model_id":     pc["canonical_id"],
            "code":         pc["variant_name"][:100],
            "scrape_status": "done",
        }
        for pc in result["product_codes_to_add"]
        if pc["canonical_id"] not in deleted_in_step0
    ]
    if pc_rows:
        # Check which canonical model IDs already have product_codes (re-run guard)
        canonical_ids = list({r["model_id"] for r in pc_rows})
        existing = (
            supabase.table("product_codes")
            .select("model_id,code")
            .in_("model_id", canonical_ids[:500])
            .execute()
        ).data or []
        existing_keys = {(r["model_id"], r["code"]) for r in existing}
        new_rows = [r for r in pc_rows if (r["model_id"], r["code"]) not in existing_keys]

        if new_rows:
            for i in range(0, len(new_rows), 200):
                supabase.table("product_codes").upsert(
                    new_rows[i:i+200],
                    on_conflict="code",
                    ignore_duplicates=True,
                ).execute()
            console.print(f"  [cyan]Inserted {len(new_rows)} product_codes[/cyan]")
        else:
            console.print(f"  [dim]product_codes already exist, skipping[/dim]")

    dup_ids = [r["id"] for r in result["to_delete"] if r["id"] not in deleted_in_step0]
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


# ── Error code garbage cleanup ─────────────────────────────────────────────────

def _is_garbage_display_text(text: str) -> bool:
    """Return True if display_text looks like OCR noise rather than a real description."""
    if not text or not text.strip():
        return True
    t = text.strip()
    # Repeated short tokens: "ee ee ee", "1 1 1 1"
    tokens = t.split()
    if len(tokens) >= 3 and len(set(tokens)) == 1:
        return True
    # Mostly non-alphanumeric / looks like garbled OCR
    alnum = sum(c.isalnum() for c in t)
    if len(t) > 3 and alnum / len(t) < 0.4:
        return True
    # Purely numeric or single char
    if re.match(r'^[\d\W]+$', t):
        return True
    return False


def clean_garbage_error_codes(brand_id: int, category_id: int, dry_run: bool = True) -> int:
    """
    Delete error_code rows whose display_text is OCR garbage.
    Returns count of rows deleted (or would delete in dry_run).
    """
    codes = (
        supabase.table("error_codes")
        .select("id,code,display_text")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    ).data or []

    garbage_ids = [
        r["id"] for r in codes
        if _is_garbage_display_text(r.get("display_text", ""))
    ]

    if dry_run:
        garbage = [r for r in codes if r["id"] in set(garbage_ids)]
        console.print(f"\n[bold]Garbage error codes ({len(garbage_ids)}):[/bold]")
        for r in sorted(garbage, key=lambda x: x["code"]):
            console.print(f"  [red]{r['code']}[/red]: {r.get('display_text', '')[:60]}")
    else:
        if garbage_ids:
            supabase.table("error_codes").delete().in_("id", garbage_ids).execute()
            console.print(f"  [red]Deleted {len(garbage_ids)} garbage error codes[/red]")

    return len(garbage_ids)


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

    bid, cid = brand.data["id"], category.data["id"]

    result = analyse(bid, cid)
    print_report(result, args.brand, args.category)
    clean_garbage_error_codes(bid, cid, dry_run=not args.execute)

    if args.execute:
        execute(result, bid, cid)
    else:
        console.print(
            "\n[dim]Dry run. Add [bold]--execute[/bold] to commit changes.[/dim]"
        )


if __name__ == "__main__":
    main()
