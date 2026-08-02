"""Apply an approved, file-backed article review through PostgREST.

The command is dry-run by default. Pass ``--apply`` to write. It refuses to
touch anything except the article/locales declared in the proposal, creates a
JSON backup immediately before writing, and verifies every saved value.

Usage:
    python -m pipeline.apply_article_review \
        data/article_reviews/article-52-ue-proposal.json
    python -m pipeline.apply_article_review \
        data/article_reviews/article-52-ue-proposal.json --apply
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import BASE_DIR, SUPABASE_URL, supabase


EXPECTED_ARTICLE_ID = 52
EXPECTED_LOCALES = {"en", "sv"}
BLOCKED_HOST = "jqepafrexisjmzoefvpr.supabase.co"

EDITABLE_FIELDS = (
    "title_tag",
    "meta_description",
    "h1",
    "description",
    "quick_fix",
    "intro_html",
    "causes_json",
    "steps_json",
    "when_to_call_technician_html",
    "prevention_html",
    "faq_json",
    "parts_json",
)

READ_FIELDS = (
    "article_id",
    "locale",
    "slug",
    *EDITABLE_FIELDS,
    "symptoms_json",
    "affected_models_json",
    "translation_status",
    "source_locale",
    "last_updated",
)


def _load_proposal(path: Path) -> dict[str, Any]:
    proposal = json.loads(path.read_text(encoding="utf-8"))
    if proposal.get("article_id") != EXPECTED_ARTICLE_ID:
        raise RuntimeError("Proposal is not for the approved article ID 52")
    translations = proposal.get("translations")
    if not isinstance(translations, dict) or set(translations) != EXPECTED_LOCALES:
        raise RuntimeError("Proposal must contain exactly the en and sv locales")
    return proposal


def _validate_translation(locale: str, fields: dict[str, Any]) -> None:
    missing = set(EDITABLE_FIELDS) - set(fields)
    extra = set(fields) - set(EDITABLE_FIELDS)
    if missing or extra:
        raise RuntimeError(
            f"{locale}: field mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )

    for name, keys, minimum, maximum in (
        ("causes_json", {"cause", "detail"}, 4, 6),
        ("steps_json", {"step", "action", "detail"}, 5, 7),
        ("faq_json", {"question", "answer"}, 4, 5),
    ):
        value = fields[name]
        if not isinstance(value, list) or not minimum <= len(value) <= maximum:
            raise RuntimeError(f"{locale}: {name} must contain {minimum}-{maximum} items")
        if any(not isinstance(item, dict) or set(item) != keys for item in value):
            raise RuntimeError(f"{locale}: {name} contains invalid item keys")

    if not isinstance(fields["parts_json"], list) or fields["parts_json"]:
        raise RuntimeError(f"{locale}: UE parts_json must be an empty array")
    if locale == "sv" and not 140 <= len(fields["meta_description"]) <= 160:
        raise RuntimeError("sv: meta_description must be 140-160 characters")
    if locale == "en" and not 140 <= len(fields["meta_description"]) <= 160:
        raise RuntimeError("en: meta_description must be 140-160 characters")


def _read_rows() -> list[dict[str, Any]]:
    response = (
        supabase.table("article_translations")
        .select(",".join(READ_FIELDS))
        .eq("article_id", EXPECTED_ARTICLE_ID)
        .in_("locale", sorted(EXPECTED_LOCALES))
        .order("locale")
        .execute()
    )
    rows = response.data or []
    if len(rows) != 2 or {row["locale"] for row in rows} != EXPECTED_LOCALES:
        raise RuntimeError("Expected exactly two rows for article 52: en and sv")
    if any(row["article_id"] != EXPECTED_ARTICLE_ID for row in rows):
        raise RuntimeError("Read-back contained an unexpected article ID")
    return rows


def _write_backup(rows: list[dict[str, Any]]) -> Path:
    backup_dir = BASE_DIR / "data" / "backups" / "article_reviews"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_dir / f"article-52-ue-before-{stamp}.json"
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": "production-vps",
        "table": "article_translations",
        "article_id": EXPECTED_ARTICLE_ID,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _changed_fields(current: dict[str, Any], proposed: dict[str, Any]) -> list[str]:
    return [field for field in EDITABLE_FIELDS if current.get(field) != proposed[field]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if BLOCKED_HOST in SUPABASE_URL:
        raise RuntimeError("Refusing to use the retired Supabase Cloud project")

    proposal = _load_proposal(args.proposal)
    translations = proposal["translations"]
    for locale, fields in translations.items():
        _validate_translation(locale, fields)

    before = _read_rows()
    before_by_locale = {row["locale"]: row for row in before}
    if before_by_locale["en"]["slug"] != "samsung-error-code-ue":
        raise RuntimeError("Unexpected English slug")
    if before_by_locale["sv"]["slug"] != "samsung-felkod-ue":
        raise RuntimeError("Unexpected Swedish slug")
    if before_by_locale["sv"]["translation_status"] != "pending":
        raise RuntimeError("Swedish translation must remain pending")

    changes = {
        locale: _changed_fields(before_by_locale[locale], translations[locale])
        for locale in sorted(EXPECTED_LOCALES)
    }
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", "changes": changes}))
    if not args.apply:
        return

    backup_path = _write_backup(before)
    print(f"backup={backup_path}")

    updated_at = datetime.now(timezone.utc).isoformat()
    for locale in sorted(EXPECTED_LOCALES):
        payload = {field: translations[locale][field] for field in EDITABLE_FIELDS}
        payload["last_updated"] = updated_at
        response = (
            supabase.table("article_translations")
            .update(payload)
            .eq("article_id", EXPECTED_ARTICLE_ID)
            .eq("locale", locale)
            .execute()
        )
        if len(response.data or []) != 1:
            raise RuntimeError(f"Expected one updated {locale} row, got {len(response.data or [])}")

    after = _read_rows()
    after_by_locale = {row["locale"]: row for row in after}
    for locale in sorted(EXPECTED_LOCALES):
        row = after_by_locale[locale]
        mismatches = [field for field in EDITABLE_FIELDS if row.get(field) != translations[locale][field]]
        if mismatches:
            raise RuntimeError(f"{locale}: read-back mismatch in {mismatches}")
        if row["last_updated"] != updated_at:
            raise RuntimeError(f"{locale}: last_updated read-back mismatch")

    if after_by_locale["en"]["translation_status"] != before_by_locale["en"]["translation_status"]:
        raise RuntimeError("English translation status changed unexpectedly")
    if after_by_locale["sv"]["translation_status"] != "pending":
        raise RuntimeError("Swedish translation status changed unexpectedly")
    if after_by_locale["en"]["affected_models_json"] != before_by_locale["en"]["affected_models_json"]:
        raise RuntimeError("English affected_models_json changed unexpectedly")
    if after_by_locale["sv"]["affected_models_json"] != before_by_locale["sv"]["affected_models_json"]:
        raise RuntimeError("Swedish affected_models_json changed unexpectedly")

    print(json.dumps({"status": "verified", "rows": 2, "last_updated": updated_at}))


if __name__ == "__main__":
    main()
