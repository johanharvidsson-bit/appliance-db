"""
db/fix_slug_prefixes.py

Prefixes all article_translations slugs with the brand slug.
e.g. "error-code-ce" -> "samsung-error-code-ce" / "lg-error-code-ce"
     "wont-drain"    -> "samsung-washing-machine-wont-drain" / "lg-wont-drain"

Idempotent: skips rows already prefixed with a known brand slug.
"""

from loguru import logger
from config.settings import supabase

def run(dry_run: bool = False) -> None:
    # ── Build article_id -> brand_slug map ────────────────────────────────────
    arts = supabase.table("articles").select("id,article_type,error_code_id,fault_id").execute()

    ec_ids = [a["error_code_id"] for a in arts.data if a["error_code_id"]]
    f_ids  = [a["fault_id"]       for a in arts.data if a["fault_id"]]

    ec_rows = supabase.table("error_codes").select("id,brand_id").in_("id", ec_ids).execute()
    f_rows  = supabase.table("faults").select("id,brand_id").in_("id", f_ids).execute()

    ec_brand = {r["id"]: r["brand_id"] for r in ec_rows.data}
    f_brand  = {r["id"]: r["brand_id"] for r in f_rows.data}

    brands     = supabase.table("brands").select("id,slug").execute()
    brand_slug = {r["id"]: r["slug"] for r in brands.data}
    known_prefixes = set(brand_slug.values())

    art_brand: dict[int, str] = {}
    for a in arts.data:
        if a["error_code_id"]:
            bid = ec_brand.get(a["error_code_id"])
        else:
            bid = f_brand.get(a["fault_id"])
        art_brand[a["id"]] = brand_slug.get(bid, "unknown")

    # ── Load all translations ─────────────────────────────────────────────────
    trans = supabase.table("article_translations").select("id,article_id,locale,slug").execute()

    to_update: list[dict] = []
    already_prefixed = 0

    for t in trans.data:
        brand = art_brand.get(t["article_id"], "unknown")
        slug  = t["slug"] or ""

        # Skip if already prefixed with a brand slug
        if any(slug.startswith(p + "-") for p in known_prefixes):
            already_prefixed += 1
            continue

        new_slug = f"{brand}-{slug}"
        to_update.append({"id": t["id"], "article_id": t["article_id"],
                           "locale": t["locale"], "old": slug, "new": new_slug})

    logger.info(f"Already prefixed: {already_prefixed}")
    logger.info(f"To update:        {len(to_update)}")

    # Show sample
    for r in to_update[:6]:
        logger.info(f"  [{r['locale']}] {r['old']}  ->  {r['new']}")
    if len(to_update) > 6:
        logger.info(f"  ... and {len(to_update) - 6} more")

    if dry_run:
        logger.info("Dry run — no writes.")
        return

    updated = 0
    for r in to_update:
        supabase.table("article_translations").update({"slug": r["new"]}).eq("id", r["id"]).execute()
        updated += 1

    logger.success(f"Updated {updated} slugs.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
