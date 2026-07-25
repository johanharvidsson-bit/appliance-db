"""
pipeline/article_generator.py

Generates article_translations rows for each error_code (or fault) using the Claude API.

Flow per error code:
  1. Check if EN translation already published → skip
  2. Get affected model names from DB
  3. Call Claude Sonnet → structured JSON (all EN fields in one call)
  4. Upsert article row → status=published
  5. Upsert EN article_translation → translation_status=published
  6. For each other active locale: translate EN via Claude Haiku → translation_status=draft

Usage:
    python -m pipeline.article_generator
    python -m pipeline.article_generator --brand samsung --category washing-machines
    python -m pipeline.article_generator --brand samsung --category washing-machines --mode faults
    python -m pipeline.article_generator --limit 5   # test with first 5 items
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

console = Console()

# ── Anthropic client ───────────────────────────────────────────────────────────
_client = anthropic.Anthropic()

MODEL         = "claude-sonnet-4-6"   # all article generation and translation
MAX_TOKENS    = 4096
TRANSLATED_BY = "claude"

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
Generate a rich, detailed troubleshooting article (~800-1000 words total across all text fields).
Respond ONLY with a valid JSON object — no markdown fences, no explanation.

Rules:
- Tone: direct, calm, practical. Helpful to a non-expert homeowner. Not salesy.
- description and quick_fix are separate model-page fields — do NOT repeat them inside the article body.
- Say "service technician", never "engineer".
- Target 800-1000 words across intro_html + causes_json details + steps_json details +
  when_to_call_technician_html + prevention_html + faq_json answers combined.

Required JSON fields:

- title_tag        : SEO title 50-60 chars, include brand + appliance type + error code
- meta_description : SEO meta 140-160 chars
- h1               : conversational page heading — must differ meaningfully from title_tag.
                     Use plain descriptive language, NOT keyword stacking.
                     Example: title_tag = "Samsung Washing Machine Error Code 4C | Fix It Now"
                              h1        = "What Does Error Code 4C Mean on a Samsung Washing Machine?"
- description      : exactly one sentence — what the fault IS. No fix. Shown on model pages.
- quick_fix        : one action sentence — the fix that resolves the highest percentage of cases
                     for this specific error type. Include the expected outcome and a rough time
                     estimate in brackets, e.g. "…(takes about 5 minutes)".
                     Shown as a callout box on the article page.
                     Rule: match the first sentence to the most common root cause listed in
                     causes_json. For drain faults (e.g. 15C, 5C, OE) lead with filter cleaning,
                     not power cycle. For communication/PCB errors (e.g. 1AC) lead with power
                     cycle. Do NOT default to power cycle for mechanical faults.

- intro_html       : H2 "Fault description" body — 2-3 HTML <p> tags.
                     Explain what the error means, what system is affected, what the machine
                     does when it occurs. Do NOT repeat the description sentence verbatim.
                     ~100-150 words.

- causes_json      : H2 "Causes" body — array of {"cause": str, "detail": str}, 4-6 items.
                     No frequency labels. Each detail should be 1-2 sentences. Most likely first.

- steps_json       : H2 "Step by step guide" body — array of
                     {"step": int, "action": str, "detail": str}, 5-7 steps.
                     Ordered easy to hard. Each detail should be 2-3 sentences with specific,
                     practical guidance a homeowner can follow. ~200-250 words total.

- when_to_call_technician_html : H2 "When to call a service technician" body —
                     2 HTML <p> tags. Describe specific symptoms that indicate DIY won't work.
                     ~80-100 words.

- prevention_html  : H2 "Find spare parts" body — 1-2 HTML <p> tags.
                     Name the 2-3 parts most commonly replaced for this fault.
                     End with this exact HTML placeholder on its own line:
                     <!-- SPARE_PARTS:{code} -->
                     where {code} is the error code (e.g. 4C).

- faq_json         : H2 "FAQ" body — array of 4-5 {"question": str, "answer": str}.
                     Target real follow-up searches. Answers should be 2-4 sentences each.
                     ~150-200 words total.

- slug             : e.g. "error-code-4c" — lowercase, no substitution in the code part\
"""

SYSTEM_PROMPT_FAULT_EN = """\
You are a technical writer specialising in home appliance repair.
Generate a rich, detailed troubleshooting article (~800-1000 words total across all text fields).
Respond ONLY with a valid JSON object — no markdown fences, no explanation.

Rules:
- Tone: direct, calm, practical. Helpful to a non-expert homeowner. Not salesy.
- description and quick_fix are separate model-page fields — do NOT repeat them inside the article body.
- Say "service technician", never "engineer".
- The article is about a SYMPTOM (what the user observes), not a single error code.
  If related error codes exist, mention them naturally in the text but keep the focus on the symptom.
- Target 800-1000 words across intro_html + causes_json details + steps_json details +
  when_to_call_technician_html + prevention_html + faq_json answers combined.

Required JSON fields:

- title_tag        : SEO title 50-60 chars, include brand + appliance type + symptom
- meta_description : SEO meta 140-160 chars
- h1               : conversational page heading — must differ meaningfully from title_tag.
                     Use plain descriptive language, NOT keyword stacking.
                     Example: title_tag = "Samsung Washing Machine Won't Drain – Fixes"
                              h1        = "Why Won't My Samsung Washing Machine Drain?"
- description      : exactly one sentence — what the symptom IS. No fix. Shown on model pages.
- quick_fix        : one action sentence — the single fix that resolves the highest percentage
                     of cases for this specific symptom. Include the expected outcome and a rough
                     time estimate in brackets, e.g. "…(takes about 5 minutes)".
                     Shown as a callout box on the article page.

- intro_html       : H2 "Fault description" body — 2-3 HTML <p> tags.
                     Explain the symptom, what system is likely affected, what the machine
                     does when it occurs. Do NOT repeat the description sentence verbatim.
                     ~100-150 words.

- causes_json      : H2 "Causes" body — array of {"cause": str, "detail": str}, 4-6 items.
                     No frequency labels. Each detail should be 1-2 sentences. Most likely first.

- steps_json       : H2 "Step by step guide" body — array of
                     {"step": int, "action": str, "detail": str}, 5-7 steps.
                     Ordered easy to hard. Each detail should be 2-3 sentences with specific,
                     practical guidance a homeowner can follow. ~200-250 words total.

- when_to_call_technician_html : H2 "When to call a service technician" body —
                     2 HTML <p> tags. Describe specific symptoms that indicate DIY won't work.
                     ~80-100 words.

- prevention_html  : H2 "Find spare parts" body — 1-2 HTML <p> tags.
                     Name the 2-3 parts most commonly replaced for this fault.
                     End with this exact HTML placeholder on its own line:
                     <!-- SPARE_PARTS_FAULT:{fault_slug} -->
                     where {fault_slug} is the fault slug provided in the input.

- faq_json         : H2 "FAQ" body — array of 4-5 {"question": str, "answer": str}.
                     Target real follow-up searches. Answers should be 2-4 sentences each.
                     ~150-200 words total.

- slug             : URL slug for this fault article, e.g. "washing-machine-wont-drain"\
"""

SYSTEM_PROMPT_TRANSLATE = """\
Translate the following JSON article fields from English to {language}.
Return ONLY a valid JSON object with exactly the same structure and keys.
Keep all JSON keys in English — translate only the string values.
Keep all HTML tags intact. Keep the <!-- SPARE_PARTS:... --> comment unchanged.
Translate the slug prefix to the natural {language} equivalent \
(e.g. "error-code-4c" → "felkod-4c" in Swedish — translate the prefix, keep the code).
Maintain a professional, practical tone appropriate for a home appliance repair guide.\
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
    # EN always first so en_fields are ready before translations run
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
    # Truncate fields with known DB length limits
    if "meta_description" in fields and fields["meta_description"]:
        fields["meta_description"] = fields["meta_description"][:165]
    if "title_tag" in fields and fields["title_tag"]:
        fields["title_tag"] = fields["title_tag"][:70]

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


# ── Fault DB helpers ───────────────────────────────────────────────────────────

def _get_faults(brand_id: int, category_id: int) -> list[dict]:
    res = (
        supabase.table("faults")
        .select("id,slug,canonical_name,severity,has_error_code")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .order("id")
        .execute()
    )
    return res.data or []


def _get_fault_related_codes(fault_id: int) -> list[str]:
    """Return error code strings linked to this fault."""
    links = (
        supabase.table("fault_error_code_map")
        .select("error_code_id")
        .eq("fault_id", fault_id)
        .execute()
    )
    if not links.data:
        return []
    ec_ids = [r["error_code_id"] for r in links.data]
    codes = (
        supabase.table("error_codes")
        .select("code")
        .in_("id", ec_ids)
        .execute()
    )
    return [r["code"] for r in (codes.data or [])]


def _get_fault_article_id(fault_id: int) -> Optional[int]:
    res = (
        supabase.table("articles")
        .select("id")
        .eq("fault_id", fault_id)
        .execute()
    )
    return res.data[0]["id"] if res.data else None


def _upsert_fault_article(fault_id: int) -> Optional[int]:
    existing = _get_fault_article_id(fault_id)
    if existing:
        return existing
    res = (
        supabase.table("articles")
        .insert({"fault_id": fault_id, "article_type": "fault", "status": "pending_translation"})
        .execute()
    )
    return res.data[0]["id"] if res.data else None


def _get_brand_model_count(brand_id: int, category_id: int) -> int:
    res = (
        supabase.table("models")
        .select("id", count="exact")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    )
    return res.count or 0


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
    """Generate all EN article fields via Claude Sonnet. Returns (fields, tokens)."""
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
    """Translate EN fields to target_locale via Claude Haiku. Returns (fields, tokens)."""
    language = LOCALE_NAMES.get(target_locale, target_locale)
    # Exclude non-translatable fields
    translatable = {
        k: v for k, v in en_fields.items()
        if k != "affected_models_json"
    }
    resp = _client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0,
        system=SYSTEM_PROMPT_TRANSLATE.format(language=language),
        messages=[{"role": "user", "content": json.dumps(translatable, ensure_ascii=False)}],
    )
    tokens = resp.usage.input_tokens + resp.usage.output_tokens
    fields = _parse_json(resp.content[0].text)
    fields["affected_models_json"] = en_fields.get("affected_models_json", [])
    return fields, tokens


def generate_fault_article_en(
    fault: dict,
    brand_name: str,
    category_name: str,
    related_codes: list[str],
    model_count: int,
) -> tuple[dict, int]:
    """Generate all EN article fields for a fault via Claude Sonnet. Returns (fields, tokens)."""
    codes_str = ", ".join(related_codes) if related_codes else "none"
    user_msg = (
        f"Brand: {brand_name}\n"
        f"Appliance type: {category_name}\n"
        f"Symptom: {fault['canonical_name']}\n"
        f"Fault slug: {fault['slug']}\n"
        f"Severity: {fault.get('severity') or 'medium'}\n"
        f"Related error codes: {codes_str}\n"
        f"Number of affected models: {model_count}"
    )
    resp = _client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0,
        system=SYSTEM_PROMPT_FAULT_EN,
        messages=[{"role": "user", "content": user_msg}],
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
                res = (
                    supabase.table("article_translations")
                    .select("title_tag,meta_description,h1,description,quick_fix,"
                            "intro_html,causes_json,steps_json,"
                            "when_to_call_technician_html,prevention_html,faq_json,slug,"
                            "affected_models_json")
                    .eq("article_id", article_id)
                    .eq("locale", "en")
                    .single()
                    .execute()
                )
                en_fields = res.data or {}
                # Reconcile: EN exists but article row may still be "pending_translation"
                # if the process crashed between writing EN and updating the article status.
                supabase.table("articles").update({"status": "published"}).eq("id", article_id).execute()
            continue

        try:
            if is_en:
                affected_models = _get_affected_models(ec_id)
                fields, tokens  = generate_article_en(
                    error_code, brand_name, category_name, affected_models
                )
                fields["affected_models_json"] = [
                    {"model_id": m["id"], "name": m["name"], "slug": m["slug"]}
                    for m in affected_models
                ]
                en_fields = fields

                _upsert_translation(article_id, "en", fields, translation_status="published")

                supabase.table("articles").update({"status": "published"}).eq("id", article_id).execute()
                logger.success(f"  {ec_code} [en]: generated ({tokens} tokens)")

            else:
                if en_fields is None:
                    logger.warning(f"  {ec_code} [{locale}]: EN not ready, skipping")
                    continue

                fields, tokens = translate_article(en_fields, locale)
                _upsert_translation(
                    article_id, locale, fields,
                    translation_status="pending", source_locale="en"
                )
                logger.success(f"  {ec_code} [{locale}]: translated ({tokens} tokens)")

        except json.JSONDecodeError as e:
            logger.error(f"  {ec_code} [{locale}]: JSON parse error – {e}")
            if is_en:
                return False

        except Exception as e:
            logger.error(f"  {ec_code} [{locale}]: {type(e).__name__}: {e}")
            if is_en:
                return False

    return True


# ── Per-fault orchestration ────────────────────────────────────────────────────

def process_fault(
    fault: dict,
    brand_name: str,
    brand_id: int,
    category_id: int,
    category_name: str,
    active_locales: list[dict],
) -> bool:
    fault_id   = fault["id"]
    fault_slug = fault["slug"]

    article_id = _upsert_fault_article(fault_id)
    if not article_id:
        logger.error(f"Could not create article row for fault id={fault_id}")
        return False

    en_fields: Optional[dict] = None

    for locale_row in active_locales:
        locale = locale_row["code"]
        is_en  = locale == "en"

        if _translation_exists_published(article_id, locale):
            logger.debug(f"  {fault_slug} [{locale}]: already published, skipping")
            if is_en:
                res = (
                    supabase.table("article_translations")
                    .select("title_tag,meta_description,h1,description,quick_fix,"
                            "intro_html,causes_json,steps_json,"
                            "when_to_call_technician_html,prevention_html,faq_json,slug")
                    .eq("article_id", article_id)
                    .eq("locale", "en")
                    .single()
                    .execute()
                )
                en_fields = res.data or {}
                supabase.table("articles").update({"status": "published"}).eq("id", article_id).execute()
            continue

        try:
            if is_en:
                related_codes = _get_fault_related_codes(fault_id)
                model_count   = _get_brand_model_count(brand_id, category_id)
                fields, tokens = generate_fault_article_en(
                    fault, brand_name, category_name, related_codes, model_count
                )
                en_fields = fields

                _upsert_translation(article_id, "en", fields, translation_status="published")
                supabase.table("articles").update({"status": "published"}).eq("id", article_id).execute()
                logger.success(f"  {fault_slug} [en]: generated ({tokens} tokens)")

            else:
                if en_fields is None:
                    logger.warning(f"  {fault_slug} [{locale}]: EN not ready, skipping")
                    continue

                fields, tokens = translate_article(en_fields, locale)
                _upsert_translation(
                    article_id, locale, fields,
                    translation_status="pending", source_locale="en"
                )
                logger.success(f"  {fault_slug} [{locale}]: translated ({tokens} tokens)")

        except json.JSONDecodeError as e:
            logger.error(f"  {fault_slug} [{locale}]: JSON parse error – {e}")
            if is_en:
                return False

        except Exception as e:
            logger.error(f"  {fault_slug} [{locale}]: {type(e).__name__}: {e}")
            if is_en:
                return False

    return True


def process_all_faults(
    brand_slug: str = "samsung",
    category_slug: str = "washing-machines",
    limit: int = 0,
) -> None:
    """Generate articles for all faults in a brand × category."""
    brand, category = _get_brand_category(brand_slug, category_slug)
    if not brand or not category:
        logger.error(f"Brand '{brand_slug}' or category '{category_slug}' not found")
        return

    category_name  = _category_display_name(category["slug_en"])
    active_locales = _get_active_locales()
    faults         = _get_faults(brand["id"], category["id"])

    if limit:
        faults = faults[:limit]

    total = len(faults)
    locale_codes = [l["code"] for l in active_locales]
    logger.info(
        f"Fault article generation: {total} faults × {len(active_locales)} locales "
        f"({brand_slug}/{category_slug}) — locales: {locale_codes}"
    )

    success = failed = 0

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        task = progress.add_task(f"{brand_slug}/{category_slug} faults", total=total)

        for fault in faults:
            ok = process_fault(
                fault, brand["name"], brand["id"], category["id"],
                category_name, active_locales
            )
            if ok:
                success += 1
            else:
                failed += 1
            progress.advance(task)

    console.print(
        f"\n[bold]Done:[/bold] {success} ok, {failed} failed "
        f"out of {total} faults"
    )


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

    success = failed = 0

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
                        help="Limit to N items (0 = all, use for testing)")
    parser.add_argument("--mode",     default="error_codes",
                        choices=["error_codes", "faults"],
                        help="Generate error code articles or fault articles")
    args = parser.parse_args()
    if args.mode == "faults":
        process_all_faults(args.brand, args.category, args.limit)
    else:
        process_all(args.brand, args.category, args.limit)
