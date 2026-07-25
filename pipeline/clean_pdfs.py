"""
pipeline/clean_pdfs.py

Manages disk usage of downloaded PDF manuals in data/manuals/.

Deletion policy (applied in order until under the size limit):
  1. PDFs whose model row has scrape_status='done' and are older than --max-age-days
  2. PDFs with no corresponding model row in the DB (orphaned files)

Safety:
  - Never deletes PDFs for models with scrape_status='pending'
  - Always shows a dry-run report first unless --execute is passed
  - Clears manual_pdf_path on the model row after deleting the file

Usage:
    python -m pipeline.clean_pdfs                    # dry-run report
    python -m pipeline.clean_pdfs --execute          # actually delete
    python -m pipeline.clean_pdfs --max-age-days 30  # only files older than 30 days
    python -m pipeline.clean_pdfs --max-size-gb 5    # delete until under 5 GB
"""

import argparse
import os
import time
from pathlib import Path
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase, MANUAL_DIR

console = Console()

DEFAULT_MAX_AGE_DAYS = 60
DEFAULT_MAX_SIZE_GB  = 10.0


def _format_mb(n_bytes: int) -> str:
    mb = n_bytes / (1024 * 1024)
    return f"{mb:.1f} MB" if mb < 1024 else f"{mb/1024:.2f} GB"


def _get_pdf_model_map() -> dict[str, dict]:
    """Return {absolute_pdf_path: model_row} for all models with a pdf path in DB."""
    res = supabase.table("models").select("id,name,manual_pdf_path,scrape_status").execute()
    result = {}
    for row in (res.data or []):
        p = row.get("manual_pdf_path")
        if p:
            result[str(Path(p).resolve())] = row
    return result


def run(
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    max_size_gb: float = DEFAULT_MAX_SIZE_GB,
    execute: bool = False,
) -> None:
    pdfs = sorted(MANUAL_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
    if not pdfs:
        console.print("[dim]No PDFs in data/manuals/[/dim]")
        return

    total_size = sum(p.stat().st_size for p in pdfs)
    max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)
    cutoff_mtime = time.time() - max_age_days * 86400

    console.print(f"\n[bold]PDF disk management[/bold]"
                  + (" [dim](DRY RUN)[/dim]" if not execute else ""))
    console.print(f"  Directory:  {MANUAL_DIR}")
    console.print(f"  Total PDFs: {len(pdfs)} ({_format_mb(total_size)})")
    console.print(f"  Policy:     older than {max_age_days} days and scrape done, "
                  f"or orphaned; max {max_size_gb:.0f} GB\n")

    pdf_map = _get_pdf_model_map()

    to_delete: list[tuple[Path, str]] = []  # (path, reason)

    for pdf in pdfs:
        abs_path = str(pdf.resolve())
        model = pdf_map.get(abs_path)
        age_days = (time.time() - pdf.stat().st_mtime) / 86400

        if model is None:
            to_delete.append((pdf, "orphaned (no model row)"))
        elif model["scrape_status"] == "done" and pdf.stat().st_mtime < cutoff_mtime:
            to_delete.append((pdf, f"done + {age_days:.0f}d old"))
        # pending models: never delete

    # Also enforce size limit: add oldest "done" PDFs until under budget
    if total_size > max_size_bytes:
        already_queued = {p for p, _ in to_delete}
        for pdf in pdfs:
            if total_size <= max_size_bytes:
                break
            if pdf in already_queued:
                continue
            abs_path = str(pdf.resolve())
            model = pdf_map.get(abs_path)
            if model and model["scrape_status"] == "done":
                to_delete.append((pdf, "size limit"))
                total_size -= pdf.stat().st_size

    if not to_delete:
        console.print("[green]Nothing to delete — disk usage is within limits.[/green]")
        return

    delete_size = sum(p.stat().st_size for p, _ in to_delete)
    t = Table(box=box.SIMPLE, show_header=True)
    t.add_column("File", width=50)
    t.add_column("Size", justify="right", width=10)
    t.add_column("Reason", width=30)
    for pdf, reason in to_delete:
        t.add_row(pdf.name[:50], _format_mb(pdf.stat().st_size), reason)
    console.print(t)
    console.print(f"Total to delete: {len(to_delete)} files, {_format_mb(delete_size)}\n")

    if not execute:
        console.print("[dim]Dry run — add --execute to delete.[/dim]")
        return

    deleted = 0
    for pdf, reason in to_delete:
        try:
            abs_path = str(pdf.resolve())
            pdf.unlink()
            deleted += 1
            # Clear the DB path reference
            model = pdf_map.get(abs_path)
            if model:
                supabase.table("models").update(
                    {"manual_pdf_path": None}
                ).eq("id", model["id"]).execute()
        except Exception as e:
            logger.warning(f"Could not delete {pdf.name}: {e}")

    console.print(f"[green]Deleted {deleted}/{len(to_delete)} files, "
                  f"freed {_format_mb(delete_size)}[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up old PDF manuals from disk")
    parser.add_argument("--max-age-days", type=int,   default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--max-size-gb",  type=float, default=DEFAULT_MAX_SIZE_GB)
    parser.add_argument("--execute",      action="store_true",
                        help="Actually delete (default is dry-run)")
    args = parser.parse_args()
    run(max_age_days=args.max_age_days, max_size_gb=args.max_size_gb, execute=args.execute)


if __name__ == "__main__":
    main()
