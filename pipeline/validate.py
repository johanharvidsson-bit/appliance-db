"""
pipeline/validate.py

Data quality checks after scraping.
Run this after each pipeline step to catch issues early.

Usage:
    python -m pipeline.validate
    python -m pipeline.validate --brand samsung --category washing-machines
"""

import argparse
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase

console = Console()


def validate(brand_slug: str = "samsung", category_slug: str = "washing-machines") -> bool:
    """
    Run all checks. Returns True if all pass, False if any fail.
    """
    brand    = supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    category = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()

    if not brand.data or not category.data:
        console.print("[red]Brand or category not found in DB[/red]")
        return False

    brand_id    = brand.data["id"]
    category_id = category.data["id"]

    checks = []

    # 1. Models exist
    models = supabase.table("models").select("id,name,manual_pdf_url,scrape_status,base_model,series").eq("brand_id", brand_id).eq("category_id", category_id).execute()
    model_count = len(models.data or [])
    checks.append(("Models in DB", model_count > 0, f"{model_count} rows"))

    # 2. Models with PDF URL
    with_pdf = sum(1 for m in (models.data or []) if m.get("manual_pdf_url"))
    checks.append(("Models with PDF URL", with_pdf > 0, f"{with_pdf}/{model_count}"))

    # 3. Product codes exist
    model_ids = [m["id"] for m in (models.data or [])]
    if model_ids:
        pcs = supabase.table("product_codes").select("id,model_id").in_("model_id", model_ids[:200]).execute()
        pc_count = len(pcs.data or [])
        models_with_pc = len({pc["model_id"] for pc in (pcs.data or [])})
        checks.append(("Product codes in DB", pc_count > 0, f"{pc_count} codes across {models_with_pc} models"))
    else:
        checks.append(("Product codes in DB", False, "no models found"))

    # 4. Error codes exist
    ecs = supabase.table("error_codes").select("id,code").eq("brand_id", brand_id).eq("category_id", category_id).execute()
    ec_count = len(ecs.data or [])
    checks.append(("Error codes in DB", ec_count > 0, f"{ec_count} unique codes"))

    # 5. Error codes are linked to product codes
    if ecs.data:
        ec_ids = [e["id"] for e in ecs.data[:200]]
        links  = supabase.table("error_code_product_codes").select("error_code_id").in_("error_code_id", ec_ids).execute()
        linked = len({l["error_code_id"] for l in (links.data or [])})
        checks.append(("Error codes linked to product codes", linked > 0, f"{linked}/{ec_count} codes linked"))
    else:
        checks.append(("Error codes linked to product codes", False, "no error codes yet"))

    # 6. No duplicate error codes
    codes = [e["code"] for e in (ecs.data or [])]
    duplicates = len(codes) - len(set(codes))
    checks.append(("No duplicate error codes", duplicates == 0, f"{duplicates} duplicates found"))

    # 6b. Error codes have descriptions (enrichment done)
    if ecs.data:
        ec_ids_all = [e["id"] for e in ecs.data]
        ec_detail = supabase.table("error_codes").select("id,description,short_description,severity").in_("id", ec_ids_all[:200]).execute().data or []
        missing_desc  = sum(1 for e in ec_detail if not e.get("description"))
        missing_short = sum(1 for e in ec_detail if not e.get("short_description"))
        checks.append(("Error codes enriched (description)", missing_desc == 0,
                        f"{ec_count - missing_desc}/{ec_count} have description"))
        checks.append(("Error codes enriched (short_description)", missing_short == 0,
                        f"{ec_count - missing_short}/{ec_count} have short_description"))

    # 6c. No models stuck in scrape_status=pending
    stuck = sum(1 for m in (models.data or []) if m.get("scrape_status") == "pending")
    checks.append(("No stuck pending models", stuck == 0, f"{stuck} models still pending"))

    # 6d. base_model and series populated
    null_base   = sum(1 for m in (models.data or []) if not m.get("base_model"))
    checks.append(("base_model populated", null_base == 0, f"{null_base} models missing base_model"))

    # 7. Affiliate site coverage by market
    if model_ids:
        all_pcs = supabase.table("product_codes").select("market").in_("model_id", model_ids[:500]).execute().data or []
        markets = {pc.get("market") for pc in all_pcs}
        gb_count = sum(1 for pc in all_pcs if pc.get("market") == "GB")
        eu_count = sum(1 for pc in all_pcs if pc.get("market") == "EU")
        us_count = sum(1 for pc in all_pcs if pc.get("market") == "US")
        checks.append(("eSpares models scraped (GB)",            gb_count > 0, f"{gb_count} product_codes with market=GB"))
        checks.append(("FixPart models scraped (EU)",            eu_count > 0, f"{eu_count} product_codes with market=EU"))
        checks.append(("AppliancePartsPros models scraped (US)", us_count > 0, f"{us_count} product_codes with market=US"))
    else:
        checks.append(("eSpares models scraped (GB)",            False, "no models found"))
        checks.append(("FixPart models scraped (EU)",            False, "no models found"))
        checks.append(("AppliancePartsPros models scraped (US)", False, "no models found"))

    # 8. Articles not stuck in partial state
    if ecs.data:
        articles = supabase.table("articles").select("id,status,error_code_id").in_("error_code_id", ec_ids_all[:200]).execute().data or []
        orphaned_articles = [
            a for a in articles
            if a["status"] == "pending_translation"
        ]
        # Check if they actually have EN translations
        truly_stuck = 0
        if orphaned_articles:
            art_ids = [a["id"] for a in orphaned_articles]
            en_translations = supabase.table("article_translations").select("article_id").in_("article_id", art_ids).eq("locale", "en").execute().data or []
            has_en = {t["article_id"] for t in en_translations}
            truly_stuck = sum(1 for a in orphaned_articles if a["id"] not in has_en)
        checks.append(("No stuck articles (pending with no EN)", truly_stuck == 0,
                        f"{truly_stuck} articles stuck without EN translation"))

    # 9. Scrape jobs – check failure rate
    recent_jobs = supabase.table("scrape_jobs").select("job_status").order("created_at", desc=True).limit(100).execute()
    if recent_jobs.data:
        failed = sum(1 for j in recent_jobs.data if j["job_status"] == "failed")
        total  = len(recent_jobs.data)
        failure_rate = failed / total
        checks.append(("Scrape job failure rate < 20%", failure_rate < 0.20, f"{failed}/{total} failed ({failure_rate:.0%})"))

    # ── Render results ─────────────────────────────────────────────────────────
    table = Table(
        title=f"Validation – {brand.data['name']} / {category_slug}",
        box=box.ROUNDED,
    )
    table.add_column("Check",   style="bold", min_width=38)
    table.add_column("Result",  justify="center")
    table.add_column("Details", style="dim")

    all_pass = True
    for check_name, passed, detail in checks:
        result_str = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        table.add_row(check_name, result_str, detail)
        if not passed:
            all_pass = False

    console.print(table)

    if all_pass:
        console.print("\n[bold green]All checks passed. Ready for article generation.[/bold green]")
    else:
        console.print("\n[bold red]Some checks failed. Review before proceeding.[/bold red]")

    return all_pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    args = parser.parse_args()
    validate(args.brand, args.category)
