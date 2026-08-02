"""Read-only Priority 0 audit of all repair articles.

Produces one JSON and one CSV row per article. This script never updates the
database; it only identifies articles that need source and safety review.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import SUPABASE_URL, supabase


BLOCKED_HOST = "jqepafrexisjmzoefvpr.supabase.co"

SELECT_TRANSLATIONS = (
    "article_id,locale,slug,title_tag,meta_description,h1,description,quick_fix,"
    "intro_html,causes_json,steps_json,when_to_call_technician_html,"
    "prevention_html,faq_json,parts_json,translation_status,last_updated"
)

DISMANTLING_PATTERNS = {
    "remove_panel": r"\b(remove|take off|open)\b.{0,45}\b(panel|cover|cabinet)\b|"
    r"\bta (bort|av|loss)\b.{0,45}\b(panel|kåpa|hölje)\b|\böppna\b.{0,30}\b(panel|hölje)\b",
    "internal_inspection": r"\binspect\b.{0,60}\b(spring|damper|shock absorber|bearing|control board|pcb|wiring)\b|"
    r"\b(inspektera|kontrollera)\b.{0,60}\b(fjäder|stötdämpare|lager|styrkort|kretskort|kablage)\b",
    "electrical_testing": r"\b(multimeter|continuity test|voltage test|test resistance|live voltage)\b|"
    r"\b(multimeter|kontinuitetsmätning|spänningsmätning|mät resistans)\b",
    "gas_or_refrigerant": r"\b(gas line|gas valve|refrigerant|compressor|sealed system)\b|"
    r"\b(gasledning|gasventil|köldmedium|kompressor|slutet kylsystem)\b",
}

OVERCLAIM_PATTERN = re.compile(
    r"resolves? (the )?(majority|most)|will (fix|resolve)|all that is needed|"
    r"löser (de flesta|problemet)|kommer att (lösa|åtgärda)|allt som behövs",
    re.IGNORECASE,
)
UNPLUG_PATTERN = re.compile(
    r"\b(unplug|disconnect (the )?(power|washer|appliance)|switch off at the mains)\b|"
    r"\b(dra ur|koppla ur|frånkoppla|bryt strömmen|stäng av.*ström)\b",
    re.IGNORECASE,
)
GENERIC_CALIBRATION_PATTERN = re.compile(
    r"hold (down )?.{0,35}(buttons?|temp|delay end).{0,25}(seconds?|CB)|"
    r"håll (in|ned).{0,35}(knapp|temp|fördröj).{0,25}(sekund|CB)",
    re.IGNORECASE,
)


def _all_text(row: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "title_tag",
        "meta_description",
        "h1",
        "description",
        "quick_fix",
        "intro_html",
        "when_to_call_technician_html",
        "prevention_html",
    ):
        values.append(str(row.get(key) or ""))
    for key in ("causes_json", "steps_json", "faq_json", "parts_json"):
        values.append(json.dumps(row.get(key), ensure_ascii=False))
    return "\n".join(values)


def _instruction_sentences(row: dict[str, Any]) -> list[str]:
    """Return homeowner-facing instructions, excluding explicit warnings/service work."""
    text_parts = [str(row.get("quick_fix") or "")]
    for item in row.get("steps_json") or []:
        if isinstance(item, dict):
            text_parts.extend((str(item.get("action") or ""), str(item.get("detail") or "")))
    sentences = re.split(r"(?<=[.!?])\s+|\n+", "\n".join(text_parts))
    safe: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if re.search(r"\b(do not|don't|never|should not|must not|inte|aldrig)\b", lowered):
            continue
        if re.search(r"\b(service technician|technician|professional|servicetekniker|fackman)\b", lowered):
            continue
        safe.append(sentence)
    return safe


def _shape_flags(row: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    specs = (
        ("causes_json", {"cause", "detail"}, 4, 6),
        ("steps_json", {"step", "action", "detail"}, 5, 7),
        ("faq_json", {"question", "answer"}, 4, 5),
    )
    for field, keys, minimum, maximum in specs:
        value = row.get(field)
        if not isinstance(value, list) or not minimum <= len(value) <= maximum:
            flags.append(f"invalid_{field}_count")
        elif any(not isinstance(item, dict) or set(item) != keys for item in value):
            flags.append(f"invalid_{field}_keys")
    return flags


def _translation_flags(row: dict[str, Any]) -> list[str]:
    text = _all_text(row)
    instruction_text = "\n".join(_instruction_sentences(row))
    flags = _shape_flags(row)
    for name, pattern in DISMANTLING_PATTERNS.items():
        if re.search(pattern, instruction_text, re.IGNORECASE):
            flags.append(name)
    if OVERCLAIM_PATTERN.search(text):
        flags.append("unqualified_fix_claim")
    if GENERIC_CALIBRATION_PATTERN.search(instruction_text):
        flags.append("generic_calibration_sequence")
    if "SPARE_PARTS" in str(row.get("prevention_html") or ""):
        flags.append("spare_parts_marker_in_prevention")
    prevention = str(row.get("prevention_html") or "")
    if re.search(r"\b(parts?|replace|replaced|replacement|reservdel|byts? ut|ersätt)\b", prevention, re.IGNORECASE):
        flags.append("parts_content_in_prevention")
    if row.get("parts_json") is None:
        flags.append("parts_json_null")
    meta = row.get("meta_description") or ""
    if len(meta) >= 165:
        flags.append("meta_at_column_limit")
    if meta and (meta[-1].isalnum() and len(meta) >= 160):
        flags.append("possibly_truncated_meta")
    hazardous = any(
        flag in flags
        for flag in ("remove_panel", "internal_inspection", "electrical_testing", "gas_or_refrigerant")
    )
    if hazardous and not UNPLUG_PATTERN.search(instruction_text):
        flags.append("hazardous_instruction_without_unplug")
    return sorted(set(flags))


def _subject_maps() -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    error_codes = supabase.table("error_codes").select("id,code,brand_id,category_id,severity").execute().data or []
    faults = supabase.table("faults").select("id,slug,canonical_name,brand_id,category_id,severity").execute().data or []
    return ({row["id"]: row for row in error_codes}, {row["id"]: row for row in faults})


def _priority(record: dict[str, Any]) -> tuple[str, int]:
    flags = set(record["flags"])
    safety = {
        "remove_panel",
        "internal_inspection",
        "electrical_testing",
        "gas_or_refrigerant",
        "hazardous_instruction_without_unplug",
    }
    if flags & safety:
        return "P0-SAFETY", 1
    if record["brand_slug"] == "samsung" and record["category_slug"] == "washing-machines":
        return "P0-SAMSUNG-WM", 2
    if record["brand_slug"] in {"bosch", "lg", "electrolux", "siemens"} and record["category_slug"] == "washing-machines":
        return "P0-CORE-WM", 3
    if record["article_type"] != "error_code":
        return "P0-SYMPTOM", 4
    return "P0-REMAINING", 5


def audit() -> dict[str, Any]:
    if BLOCKED_HOST in SUPABASE_URL:
        raise RuntimeError("Refusing to audit the retired Supabase Cloud project")

    translations = supabase.table("article_translations").select(SELECT_TRANSLATIONS).order("article_id").execute().data or []
    articles = supabase.table("articles").select("id,error_code_id,fault_id,status,article_type,review_flag").order("id").execute().data or []
    brands = {row["id"]: row for row in (supabase.table("brands").select("id,name,slug").execute().data or [])}
    categories = {row["id"]: row for row in (supabase.table("categories").select("id,slug_en").execute().data or [])}
    error_codes, faults = _subject_maps()
    translations_by_article: dict[int, dict[str, dict[str, Any]]] = {}
    for row in translations:
        translations_by_article.setdefault(row["article_id"], {})[row["locale"]] = row

    records: list[dict[str, Any]] = []
    for article in articles:
        subject = error_codes.get(article["error_code_id"]) if article.get("error_code_id") else faults.get(article["fault_id"])
        if not subject:
            raise RuntimeError(f"Article {article['id']} has no resolvable subject")
        brand = brands[subject["brand_id"]]
        category = categories[subject["category_id"]]
        locale_rows = translations_by_article.get(article["id"], {})
        locale_flags = {locale: _translation_flags(row) for locale, row in locale_rows.items()}
        flags = sorted({flag for values in locale_flags.values() for flag in values})
        record = {
            "article_id": article["id"],
            "article_type": article["article_type"],
            "status": article["status"],
            "brand": brand["name"],
            "brand_slug": brand["slug"],
            "category_slug": category["slug_en"],
            "subject": subject.get("code") or subject.get("canonical_name") or subject.get("slug"),
            "en_slug": locale_rows.get("en", {}).get("slug"),
            "sv_slug": locale_rows.get("sv", {}).get("slug"),
            "flags": flags,
            "en_flags": locale_flags.get("en", []),
            "sv_flags": locale_flags.get("sv", []),
            "requires_p0_review": bool(flags),
        }
        label, rank = _priority(record)
        record["priority"] = label
        record["priority_rank"] = rank
        records.append(record)

    records.sort(key=lambda row: (row["priority_rank"], row["brand_slug"], row["category_slug"], row["article_id"]))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "production-vps-read-only",
        "article_count": len(articles),
        "translation_count": len(translations),
        "requires_p0_review": sum(row["requires_p0_review"] for row in records),
        "priority_counts": dict(
            Counter(row["priority"] for row in records if row["requires_p0_review"])
        ),
        "flag_counts": dict(Counter(flag for row in records for flag in row["flags"])),
        "articles": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    columns = (
        "priority",
        "article_id",
        "article_type",
        "brand",
        "category_slug",
        "subject",
        "en_slug",
        "sv_slug",
        "flags",
    )
    with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in report["articles"]:
            if not row["requires_p0_review"]:
                continue
            writer.writerow({**{key: row[key] for key in columns if key != "flags"}, "flags": ";".join(row["flags"])})
    print(json.dumps({key: report[key] for key in ("article_count", "translation_count", "requires_p0_review", "priority_counts", "flag_counts")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
