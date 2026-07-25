"""
pipeline/enrich_error_codes.py

Enriches error code records via Google Search (Serper API) + Claude Haiku synthesis.

For each error_code row in the DB:
  1. Search Google: "{code} error {brand} {category_name}"
  2. Fetch top 5-10 results (title + snippet)
  3. Synthesise via Claude Haiku:
       - short_description: one-line headline (e.g. "Water supply problem")
       - description: full 2-3 sentence explanation with cause and DIY tip
       - severity: 'easy' | 'medium' | 'advanced'
  4. Update all three columns + source URL in DB
  5. Flag codes that return no relevant results as likely invalid

Severity badges:
  easy     -> user can fix without tools (e.g. unbalanced load, reversed hoses)
  medium   -> requires basic tools / some disassembly (e.g. pump filter, door seal)
  advanced -> likely needs a technician (e.g. PCB failure, motor fault)

Usage:
    python -m pipeline.enrich_error_codes
    python -m pipeline.enrich_error_codes --brand samsung --category washing-machines
    python -m pipeline.enrich_error_codes --dry-run           # print report only
    python -m pipeline.enrich_error_codes --delete-invalid    # also remove flagged codes
"""

import argparse
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
import anthropic
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase

console = Console()

# ── Config ─────────────────────────────────────────────────────────────────────

SERPER_URL    = "https://google.serper.dev/search"
# Accept both the old mixed-case key and the new standardised name
SERPER_KEY    = os.getenv("SERPER_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HAIKU_MODEL   = "claude-haiku-4-5-20251001"

_SEVERITY_BADGE = {
    "easy":     "Easy (user fix)",
    "medium":   "Medium (moderate repair)",
    "advanced": "Advanced (technician)",
}

# Friendly category names for search queries
_CATEGORY_NAMES = {
    "washing-machines": "washing machine",
    "dryers":           "dryer",
    "dishwashers":      "dishwasher",
    "refrigerators":    "refrigerator",
    "freezers":         "freezer",
    "ovens":            "oven",
    "microwaves":       "microwave",
}

# ── Search helpers ─────────────────────────────────────────────────────────────

def _serper_search(query: str) -> list[dict]:
    """Return top organic results [{title, snippet, link}] from Serper."""
    try:
        r = httpx.post(
            SERPER_URL,
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": 10},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("organic", [])[:10]
    except Exception as exc:
        logger.warning(f"Serper search failed for {query!r}: {exc}")
        return []


# ── LLM synthesis ──────────────────────────────────────────────────────────────

_llm: Optional[anthropic.Anthropic] = None

def _get_llm() -> anthropic.Anthropic:
    global _llm
    if _llm is None:
        _llm = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    return _llm


def _synthesise(
    code: str,
    brand: str,
    category_name: str,
    results: list[dict],
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], bool]:
    """
    Use Claude Haiku to write all three fields from search snippets.
    Returns (short_description, description, severity, best_source_url, is_valid).
    """
    if not results:
        return None, None, None, None, False

    snippets = "\n".join(
        f"- [{r.get('title','')}]: {r.get('snippet','')}"
        for r in results[:8]
    )
    best_url = results[0].get("link")

    prompt = f"""You are a home appliance repair expert. Given these Google search results for error code "{code}" on a {brand} {category_name}:

{snippets}

Respond with a JSON object containing exactly these four fields:
  "short_description": one-line headline (max 80 chars) naming the fault — e.g. "Water supply problem" or "Door not closing properly". No error code number, no brand name.
  "description": 2-3 sentence plain-prose description: what the fault is, the most common cause(s), and a brief DIY fix tip if applicable.
  "severity": one of "easy" | "medium" | "advanced"
    easy     = user can fix with no tools (e.g. reversed hoses, unbalanced load, settings)
    medium   = requires basic tools or minor disassembly (e.g. drain filter, door seal)
    advanced = likely needs a service technician (e.g. PCB, motor, control board failure)
  "valid": true if the results actually describe this error code on {brand} {category_name}; false if results are unrelated or about a different product.

Reply ONLY with the JSON object — no markdown fences, no explanation."""

    try:
        msg = _get_llm().messages.create(
            model=HAIKU_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        import json as _json
        text = msg.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = _json.loads(text)
        if not data.get("valid", True):
            return None, None, None, None, False
        severity = data.get("severity", "medium")
        if severity not in ("easy", "medium", "advanced"):
            severity = "medium"
        return (
            (data.get("short_description") or "")[:200] or None,
            (data.get("description") or "") or None,
            severity,
            best_url,
            True,
        )
    except Exception as exc:
        logger.warning(f"Haiku synthesis failed for {code!r}: {exc}")
        return None, None, "medium", best_url, True  # keep valid if LLM fails


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_brand(brand_slug: str) -> tuple[Optional[int], Optional[str]]:
    res = supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    return (res.data["id"], res.data["name"]) if res.data else (None, None)


def _get_category_id(category_slug: str) -> Optional[int]:
    res = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()
    return res.data["id"] if res.data else None


# ── Main enrichment ────────────────────────────────────────────────────────────

def enrich(
    brand_slug: str = "samsung",
    category_slug: str = "washing-machines",
    dry_run: bool = False,
    delete_invalid: bool = False,
) -> None:
    brand_id, brand_name = _get_brand(brand_slug)
    category_id = _get_category_id(category_slug)
    category_name = _CATEGORY_NAMES.get(category_slug, category_slug.replace("-", " "))

    if not brand_id or not category_id:
        console.print(f"[red]Brand '{brand_slug}' or category '{category_slug}' not found in DB[/red]")
        return

    rows = (
        supabase.table("error_codes")
        .select("id,code,display_text,source")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    ).data or []

    console.print(f"\n[bold]Error code enrichment — {brand_slug} / {category_slug}[/bold]")
    console.print(f"Found {len(rows)} error codes. {'[dim]DRY RUN — no DB writes[/dim]' if dry_run else ''}\n")

    updated: list[dict] = []
    invalid: list[dict] = []
    failed:  list[dict] = []

    for i, row in enumerate(rows, 1):
        code = row["code"]
        query = f"{code} error {brand_name} {category_name}"
        console.print(f"  [{i}/{len(rows)}] {code:12} -> searching...", end="")

        results = _serper_search(query)
        short_desc, description, severity, source_url, is_valid = _synthesise(
            code, brand_name, category_name, results
        )

        if not is_valid:
            console.print(f" [red]INVALID[/red]")
            invalid.append(row)
        elif description:
            badge = {"easy": "green", "medium": "yellow", "advanced": "red"}.get(severity or "medium", "yellow")
            console.print(f" [{badge}]{severity}[/{badge}]")
            updated.append({
                **row,
                "_short_description": short_desc,
                "_description":       description,
                "_severity":          severity,
                "_source":            source_url,
            })
        else:
            console.print(f" [yellow]no description[/yellow]")
            failed.append(row)

        time.sleep(0.5)

    # ── Report ──────────────────────────────────────────────────────────────────
    console.print(f"\n[bold]Results:[/bold] {len(updated)} updated, {len(invalid)} invalid, {len(failed)} failed\n")

    if invalid:
        console.print(f"[bold red]Codes flagged as INVALID ({len(invalid)}):[/bold red]")
        for r in invalid:
            console.print(f"  {r['code']:12} (was: {(r.get('display_text') or '')[:60]!r})")

    if not dry_run:
        now_iso = datetime.now(timezone.utc).isoformat()
        for r in updated:
            supabase.table("error_codes").update({
                "short_description": r["_short_description"],
                "description":       r["_description"],
                "severity":          r["_severity"],
                "source":            r["_source"],
                "scrape_status":     "done",
                "last_verified_at":  now_iso,
            }).eq("id", r["id"]).execute()

        console.print(f"\n[green]Updated {len(updated)} error codes in DB[/green]")

        if delete_invalid and invalid:
            ids = [r["id"] for r in invalid]
            supabase.table("error_codes").delete().in_("id", ids).execute()
            console.print(f"[red]Deleted {len(ids)} invalid error codes[/red]")
        elif invalid:
            console.print(f"[dim]Invalid codes kept (run with --delete-invalid to remove)[/dim]")

    # ── Preview table ────────────────────────────────────────────────────────────
    if updated:
        t = Table(title="Enriched Error Codes", box=box.SIMPLE, show_header=True)
        t.add_column("Code",             style="bold", width=10)
        t.add_column("Severity",         width=10)
        t.add_column("Short description",width=30)
        t.add_column("Description (truncated)", width=55)
        for r in updated:
            sev = r["_severity"] or "medium"
            sev_color = {"easy": "green", "medium": "yellow", "advanced": "red"}.get(sev, "white")
            t.add_row(
                r["code"],
                f"[{sev_color}]{sev}[/{sev_color}]",
                (r["_short_description"] or "")[:30],
                (r["_description"] or "")[:55],
            )
        console.print(t)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich error codes via Google + Claude Haiku")
    parser.add_argument("--brand",          default="samsung")
    parser.add_argument("--category",       default="washing-machines")
    parser.add_argument("--dry-run",        action="store_true",
                        help="Print report only; do not write to DB")
    parser.add_argument("--delete-invalid", action="store_true",
                        help="Delete codes flagged as invalid")
    args = parser.parse_args()

    if not SERPER_KEY:
        console.print("[red]SERPER_API_KEY not set in .env[/red]")
        return
    if not ANTHROPIC_KEY:
        console.print("[red]ANTHROPIC_API_KEY not set in .env[/red]")
        return

    enrich(
        brand_slug=args.brand,
        category_slug=args.category,
        dry_run=args.dry_run,
        delete_invalid=args.delete_invalid,
    )


if __name__ == "__main__":
    main()
