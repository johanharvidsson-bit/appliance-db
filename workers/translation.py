"""Deterministic selection + Claude-backed text translation for already-applied,
locale-scoped content (model overviews, error-code text, fault text, guide
title/steps).

This worker is deliberately not part of the evidence/candidate-fact/proposal
chain the other seven workers share. It does not extract anything from an
external source and makes no factual claim beyond "this says the same thing
as the verified source-locale row, in another language" - the same operation
pipeline/article_generator.py already performed for years for articles, via
the same model family. Selection (which rows need translating) is
deterministic; only the translation call itself is not.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

WORKER_NAME = "translation"
WORKER_VERSION = "1.0.0"

LOCALE_NAMES = {
    "en": "English", "sv": "Swedish", "de": "German", "fr": "French",
    "es": "Spanish", "pl": "Polish", "it": "Italian", "nl": "Dutch",
    "pt": "Portuguese", "fi": "Finnish",
}

SYSTEM_PROMPT = """\
Translate the following JSON object from {source_language} to {target_language}.
Return ONLY a valid JSON object with exactly the same keys and structure.
Do not add, remove, reorder, or renumber any array items or object keys.
Translate only human-readable string values. Never translate numbers, ids, \
step_number values, product/model codes, or error codes.
Maintain a professional, practical tone appropriate for a home appliance \
repair guide. Do not invent information that is not present in the input.\
"""


@dataclass(frozen=True)
class TranslationField:
    """One text field to translate. `is_list` fields hold a list of dicts
    (e.g. guide steps); `list_text_key` names the translatable string inside
    each item."""

    name: str
    is_list: bool = False
    list_text_key: str | None = None


# Per source-table shape. id_column is the FK to the owning entity; slug is
# only present (and only generated) for guides, whose translations are
# addressable pages in their own right.
TRANSLATABLE_TABLES = {
    "model": {
        "table": "model_content_translations",
        "id_column": "model_id",
        "fields": (TranslationField("overview"), TranslationField("short_summary")),
        "has_slug": False,
    },
    "error_code": {
        "table": "error_code_translations",
        "id_column": "error_code_id",
        "fields": (TranslationField("title"), TranslationField("description")),
        "has_slug": False,
    },
    "fault": {
        "table": "fault_translations",
        "id_column": "fault_id",
        "fields": (
            TranslationField("symptom_name"),
            TranslationField("meta_description"),
        ),
        "has_slug": False,
    },
    "guide": {
        "table": "guide_translations",
        "id_column": "guide_id",
        "fields": (
            TranslationField("title"),
            TranslationField("short_description"),
            TranslationField("summary"),
            TranslationField("steps_json", is_list=True, list_text_key="instruction"),
        ),
        "has_slug": True,
    },
}


def source_content_hash(row: dict, fields: tuple[TranslationField, ...]) -> str:
    """Hash of exactly the content a translation would need to stay in sync
    with. Stored on the target-locale row as source_hash; a target row whose
    source_hash no longer matches this is stale (source changed) or was never
    a real translation (e.g. a duplicate of the source row, source_hash NULL)."""
    payload = {f.name: row.get(f.name) for f in fields}
    return sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def needs_translation(source_row: dict, target_row: dict | None, fields) -> bool:
    if target_row is None:
        return True
    return target_row.get("source_hash") != source_content_hash(source_row, fields)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text.rstrip())
    return json.loads(text)


class TranslationEngine:
    def __init__(self, client, *, model: str = "claude-haiku-4-5-20251001"):
        self.client = client
        self.model = model

    def translate(
        self, row: dict, fields: tuple[TranslationField, ...], *, source_locale: str, target_locale: str
    ) -> dict:
        """Return {field_name: translated_value} for every non-empty field."""
        payload = {}
        source_items = {}
        for f in fields:
            value = row.get(f.name)
            if value in (None, "", [], {}):
                continue
            if f.is_list:
                # Only the translatable text travels to Claude - step_number
                # and any other non-text keys are always overwritten from the
                # source on the way back, so sending/expecting them is pure
                # token overhead.
                source_items[f.name] = value
                payload[f.name] = [
                    {f.list_text_key: item.get(f.list_text_key, "")} for item in value
                ]
            else:
                payload[f.name] = value
        if not payload:
            return {}
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,
            system=SYSTEM_PROMPT.format(
                source_language=LOCALE_NAMES.get(source_locale, source_locale),
                target_language=LOCALE_NAMES.get(target_locale, target_locale),
            ),
            messages=[
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
            ],
        )
        translated = _parse_json(response.content[0].text)
        result = {}
        for f in fields:
            if f.name not in translated:
                continue
            if f.is_list:
                original = source_items.get(f.name, [])
                out = translated[f.name]
                if not isinstance(out, list) or len(out) != len(original):
                    # Claude changed the item count - reject rather than risk
                    # silently dropping or duplicating a step.
                    continue
                for item, source_item in zip(out, original):
                    for key in source_item:
                        if key != f.list_text_key:
                            item[key] = source_item[key]
                result[f.name] = out
            else:
                result[f.name] = translated[f.name]
        return result


def build_slug(entity_type: str, entity_id, locale: str) -> str:
    return f"{entity_type}-{entity_id}-{locale}"
