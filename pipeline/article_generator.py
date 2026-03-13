"""
pipeline/article_generator.py

Generates article_translations rows for each error_code using the Claude API.

Flow per error code:
  1. Check if EN translation already published → skip
  2. Get affected model names from DB
  3. Call Claude API → structured JSON (all EN fields in one call)
  4. Upsert article row → status=published
  5. Upsert EN article_translation → translation_status=published
  6. For each other active locale: translate EN via Claude → translation_status=draft

Usage:
    python -m pipeline.article_generator
    python -m pipeline.article_generator --brand samsung --category washing-machines
    python -m pipeline.article_generator --limit 5   # test with first 5 error codes
"""

import argparse
import json
import re
from typing import Optional

import anthropic
from loguru import logger
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn

from config.settings import supabase
from scrapers.base_scraper import (
    create_scrape_job,
    start_scrape_job,
    complete_scrape_job,
    fail_scrape_job,
)

console = Console()

# ── Anthropic client ───────────────────────────────────────────────────────────
# Reads ANTHROPIC_API_KEY from environment automatically
_client = anthropic.Anthropic()
MODEL        = "claude-sonnet-4-6"
MAX_TOKENS   = 2048
TRANSLATED_BY = "claude-sonnet-4-6"

# Locale display names used in translation prompts
LOCALE_NAMES = {
    "en": "English", "sv": "Swedish",  "de": "German",
    "fr": "French",  "es": "Spanish",  "pl": "Polish",
    "it": "Italian", "nl": "Dutch",    "pt": "Portuguese",
    "fi": "Finnish",
}

# ── Prompts ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_EN = """\
You are a technical writer specialising in home appliance repair.
Generate a structured troubleshooting article for the appliance error code below.
Respond ONLY with a valid JSON object — no markdown fences, no explanation.

Required fields:
- title_tag        : SEO page title, 50-60 chars, include brand + appliance type + error code
- meta_description : SEO meta description, 140-160 chars, summarise the fix
- h1               : Page heading, natural language, slightly longer than title_tag
- quick_fix        : 2-4 plain sentences, standalone fix summary, no HTML
- intro_html       : 1-2 short paragraphs in HTML <p> tags introducing the error
- causes_json      : array of {"cause": str, "frequency": "common"|"occasional"|"rare", "detail": str}, 3-5 items
- steps_json       : array of {"step": int, "action": str, "detail": str}, 5-8 steps
- when_to_call_technician_html : 1 short HTML <p> describing when professional help is needed
- prevention_html  : 1 short HTML <p> with maintenance tips to prevent this error
- faq_json         : array of exactly 5 {"question": str, "answer": str} pairs
- slug             : URL-friendly slug for this article, lowercase hyphenated, e.g. "error-code-e2"\
"""

SYSTEM_PROMPT_TRANSLATE = """\
Translate the following JSON article fields from English to {language}.
Return ONLY a valid JSON object with exactly the same structure and keys.
Keep all JSON keys unchanged (they stay in English).
Translate only the string values. Keep HTML tags intact.
Also translate the slug to a natural {language} equivalent \
(e.g. "error-code-e2" → "felkod-e2" in Swedish).
Maintain a professional, technical tone.\
"""


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_brand_category(
    brand_slug: str, category_slug: str
) -> tuple[Optional[dict], Optional[dict]]:
    brand = (
        supabase.table("brands").select("id,name")
        .eq("slug", brand_slug).single().execute()
    )
    category = (
        supabase.table("categories").select("id,slug_en")
        .eq("slug_en", category_slug).single().execute()
    )
    return brand.data, category.data


def _category_display_name(slug_en: str) -> str:
    """Convert slug_en to a human-readable name, e.g. 'washing-machines' → 'Washing Machine'."""
    singular = slug_en.rstrip("s").replace("-", " ")
    return singular.title()


def _get_error_codes(brand_id: int, category_id: int) -> list[dict]:
    res = (
        supabase.table("error_codes")
        .select("id,code,display_text")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .order("code")
        .execute()
    )
    return res.data or []


def _get_affected_models(error_code_id: int) -> list[dict]:
    """Return model id/name/slug linked to this error code via product_codes."""
    links = (
        supabase.table("error_code_product_codes")
        .select("product_code_id")
        .eq("error_code_id", error_code_id)
        .execute()
    )
    if not links.data:
        return []

    pc_ids = [l["product_code_id"] for l in links.data]
    pcs = (
        supabase.table("product_codes")
        .select("model_id")
        .in_("id", pc_ids[:100])
        .execute()
    )
    if not pcs.data:
        return []

    model_ids = list({pc["model_id"] for pc in pcs.data})
    models = (
        supabase.table("models")
        .select("id,name,slug")
        .in_("id", model_ids[:50])
        .execute()
    )
    return models.data or []


def _get_active_locales() -> list[dict]:
    res = (
        supabase.table("locales")
        .select("code,name")
        .eq("is_active", True)
        .execute()
    )
    locales = res.data or []
    # EN always first so translations can reference en_fields within same run
    locales.sort(key=lambda l: (0 if l["code"] == "en" else 1, l["code"]))
    return locales


def _translation_exists_published(article_id: int, locale: str) -> bool:
    res = (
        supabase.table("article_translations")
        .select("translation_status")
        .eq("article_id", article_id)
        .eq("locale", locale)
        .execute()
    )
    if not res.data:
        return False
    return res.data[0].get("translation_status") == "published"


def _get_article_id(error_code_id: int) -> Optional[int]:
    res = (
        supabase.table("articles")
        .select("id")
        .eq("error_code_id", error_code_id)
        .execute()
    )
    return res.data[0]["id"] if res.data else None


def _upsert_article(error_code_id: int) -> Optional[int]:
    """Create article row if it doesn't exist. Returns article id."""
    res = (
        supabase.table("articles")
        .upsert(
            {"error_code_id": error_code_id, "status": "pending_translation"},
            on_conflict="error_code_id",
            ignore_duplicates=True,
        )
        .execute()
    )
    if res.data:
        return res.data[0]["id"]
    return _get_article_id(error_code_id)


def _upsert_translation(
    article_id: int,
    locale: str,
    fields: dict,
    translation_status: str,
    source_locale: Optional[str] = None,
) -> None:
    row = {
        "article_id":         article_id,
        "locale":             locale,
        "translation_status": translation_status,
        "translated_by":      TRANSLATED_BY,
        **fields,
    }
    if source_locale:
        row["source_locale"] = source_locale
    supabase.table("article_translations").upsert(
        row, on_conflict="article_id,locale"
    ).execute()


# ── Claude API calls ───────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    """Parse JSON from Claude response, stripping any markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.rstrip())
    return json.loads(text)


def generate_article_en(
    error_code: dict,
    brand_name: str,
    category_name: str,
    affected_models: list[dict],
) -> tuple[dict, int]:
    """Generate all EN article fields in one Claude call. Returns (fields, token_count)."""
    model_names = ", ".join(m["name"] for m in affected_models[:20]) or "various models"
    user_msg = (
        f"Brand: {brand_name}\n"
        f"Appliance type: {category_name}\n"
        f"Error code: {error_code['code']}\n"
        f"Description from manual: {error_code.get('display_text') or 'Not available'}\n"
        f"Affected models include: {model_names}"
    )
    resp = _client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0,
        system=SYSTEM_PROMPT_EN,
        messages=[{"role": "user", "content": user_msg}],
    )
    tokens = resp.usage.input_tokens + resp.usage.output_tokens
    return _parse_json(resp.content[0].text), tokens


def translate_article(en_fields: dict, target_locale: str) -> tuple[dict, int]:
    """Translate EN article fields to target_locale. Returns (fields, token_count)."""
    language = LOCALE_NAMES.get(target_locale, target_locale)
    resp = _client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0,
        system=SYSTEM_PROMPT_TRANSLATE.format(language=language),
        messages=[{"role": "user", "content": json.dumps(en_fields, ensure_ascii=False)}],
    )
    tokens = resp.usage.input_tokens + resp.usage.output_tokens
    return _parse_json(resp.content[0].text), tokens


# ── Per-error-code orchestration ───────────────────────────────────────────────

def process_error_code(
    error_code: dict,
    brand_name: str,
    category_name: str,
    active_locales: list[dict],
) -> bool:
    """
    Generate + translate article for one error code.
    Returns True if EN was successfully generated (or already existed).
    """
    ec_id   = error_code["id"]
    ec_code = error_code["code"]

    article_id = _upsert_article(ec_id)
    if not article_id:
        logger.error(f"Could not create article row for error_code id={ec_id}")
        return False

    en_fields: Optional[dict] = None

    for locale_row in active_locales:
        locale = locale_row["code"]
        is_en  = locale == "en"

        if _translation_exists_published(article_id, locale):
            logger.debug(f"  {ec_code} [{locale}]: already published, skipping")
            if is_en:
                # Still need en_fields for translations — fetch them
                res = (
                    supabase.table("article_translations")
                    .select("title_tag,meta_description,h1,quick_fix,intro_html,"
                            "causes_json,steps_json,when_to_call_technician_html,"
                            "prevention_html,faq_json,slug")
                    .eq("article_id", article_id)
                    .eq("locale", "en")
                    .single()
                    .execute()
                )
                en_fields = res.data or {}
            continue

        job_id = create_scrape_job("article", f"{ec_code}:{locale}", ec_id)
        start_scrape_job(job_id)

        try:
            if is_en:
                affected_models = _get_affected_models(ec_id)
                fields, tokens  = generate_article_en(
                    error_code, brand_name, category_name, affected_models
                )
                # Add affected_models_json from DB (not generated by Claude)
                fields["affected_models_json"] = [
                    {"model_id": m["id"], "name": m["name"], "slug": m["slug"]}
                    for m in affected_models
                ]
                en_fields = fields

                _upsert_translation(article_id, "en", fields, translation_status="published")
                supabase.table("articles").update({"status": "published"}).eq("id", article_id).execute()

                complete_scrape_job(job_id, parsed_json={"locale": "en", "tokens": tokens})
                logger.success(f"  {ec_code} [en]: generated ({tokens} tokens)")

            else:
                if en_fields is None:
                    # EN not generated in this run (and not published) — skip
                    logger.warning(f"  {ec_code} [{locale}]: EN not ready, skipping translation")
                    complete_scrape_job(job_id, parsed_json={"skipped": "en_not_ready"})
                    continue

                # Translate EN fields (exclude affected_models_json — same across locales)
                translatable = {
                    k: v for k, v in en_fields.items()
                    if k != "affected_models_json"
                }
                fields, tokens = translate_article(translatable, locale)
                fields["affected_models_json"] = en_fields.get("affected_models_json", [])

                _upsert_translation(
                    article_id, locale, fields,
                    translation_status="draft", source_locale="en"
                )
                complete_scrape_job(job_id, parsed_json={"locale": locale, "tokens": tokens})
                logger.success(f"  {ec_code} [{locale}]: translated ({tokens} tokens)")

        except json.JSONDecodeError as e:
            fail_scrape_job(job_id, f"JSON parse error: {e}")
            logger.error(f"  {ec_code} [{locale}]: JSON parse failed – {e}")
            if is_en:
                return False  # Can't translate without EN

        except Exception as e:
            fail_scrape_job(job_id, str(e))
            logger.error(f"  {ec_code} [{locale}]: {type(e).__name__}: {e}")
            if is_en:
                return False

    return True


# ── Main entry point ───────────────────────────────────────────────────────────

def process_all(
    brand_slug: str = "samsung",
    category_slug: str = "washing-machines",
    limit: int = 0,
) -> None:
    """Generate articles for all error codes in a brand × category."""
    brand, category = _get_brand_category(brand_slug, category_slug)
    if not brand or not category:
        logger.error(f"Brand '{brand_slug}' or category '{category_slug}' not found")
        return

    category_name  = _category_display_name(category["slug_en"])
    active_locales = _get_active_locales()
    error_codes    = _get_error_codes(brand["id"], category["id"])

    if limit:
        error_codes = error_codes[:limit]

    total = len(error_codes)
    locale_codes = [l["code"] for l in active_locales]
    logger.info(
        f"Article generation: {total} error codes × {len(active_locales)} locales "
        f"({brand_slug}/{category_slug}) — locales: {locale_codes}"
    )

    success = failed = skipped = 0

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        task = progress.add_task(f"{brand_slug}/{category_slug}", total=total)

        for ec in error_codes:
            ok = process_error_code(ec, brand["name"], category_name, active_locales)
            if ok:
                success += 1
            else:
                failed += 1
            progress.advance(task)

    console.print(
        f"\n[bold]Done:[/bold] {success} ok, {failed} failed "
        f"out of {total} error codes"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Article generator pipeline")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--limit",    type=int, default=0,
                        help="Limit to N error codes (0 = all, use for testing)")
    args = parser.parse_args()
    process_all(args.brand, args.category, args.limit)
