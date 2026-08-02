"""Generate the approved Bosch batch 001 proposal without touching the DB."""

from __future__ import annotations

import json
import re
from pathlib import Path

import anthropic

from config.settings import BASE_DIR


IDS = {164: "E16", 167: "E19", 168: "E20", 169: "E21", 170: "E22"}
FACTS = {
    "E16": "Bosch identifies E16/F16 as door not closed or not locked properly. User may remove trapped laundry and close the door until it clicks. If it persists, contact Bosch service.",
    "E19": "Bosch identifies E19/F19 as heating time exceeded and explicitly says it cannot be rectified by the user; arrange service.",
    "E20": "Bosch US identifies E20/F20 as unexpected heating. Treat as a service fault; user must not test heater, wiring, sensors or control electronics.",
    "E21": "Meaning varies by Bosch model family: an official recent manual uses E:21 for detergent solution not pumped out and allows manual-specific drain-pump maintenance; another official manual uses F:21 for a motor fault and says call service. Do not state a universal meaning. User should record exact code and E-Nr, consult exact manual, and only perform explicitly documented external/pump maintenance after unplugging and cooling/draining safely.",
    "E22": "No universal Bosch washing-machine meaning is established in the official general error-code list. Do not borrow the Bosch dishwasher E22 meaning. User should record exact code and E-Nr, consult the exact washer manual, try only a documented reset, and arrange service if it returns.",
}
SOURCES = [
    {"title": "Bosch washer error codes", "url": "https://www.bosch-home.com/us/experience-bosch/heart-of-the-home/tips-and-tricks/washer-error-codes"},
    {"title": "Bosch E16/F16 support", "url": "https://www.bosch-home.com/us/owner-support/get-support/support-selfhelp-washing-error-e16-or-f16-washing-machine"},
    {"title": "Bosch E19/F19 support", "url": "https://www.bosch-home.com/us/owner-support/get-support/support-selfhelp-washing-error-e19-or-f19-washing-machine"},
    {"title": "Bosch washer manual 9001994523", "url": "https://media3.bosch-home.com/Documents/9001994523_B.pdf"},
    {"title": "Bosch washer manual 9001026001", "url": "https://media3.bosch-home.com/Documents/9001026001_A.pdf"},
]

FIELDS = {
    "title_tag", "meta_description", "h1", "description", "quick_fix",
    "intro_html", "causes_json", "steps_json", "when_to_call_technician_html",
    "prevention_html", "faq_json", "parts_json",
}

SYSTEM = """You are a cautious technical editor for appliance repair content.
Use ONLY the supplied verified facts. Model/market differences must be explicit.
Write calm, direct English for a homeowner. Never tell the user to remove a panel,
open the cabinet, use a multimeter, test voltage/resistance/continuity, inspect
internal components, bypass a lock, or order/replace a part. Do not promise a fix.
For service-only faults, say so early. Before any permitted physical check, say
switch off and unplug. Do not invent a code meaning.

Return only JSON with exactly these keys:
title_tag, meta_description, h1, description, quick_fix, intro_html,
causes_json, steps_json, when_to_call_technician_html, prevention_html,
faq_json, parts_json.
title_tag 45-65 chars; meta_description 140-160 chars; description one sentence.
intro_html: 2 <p> elements. causes_json: 4-6 {cause,detail} objects; distinguish
confirmed meaning from contextual possibilities. steps_json: 5-7
{step,action,detail} objects, safest/easiest first and service last. FAQ: 4-5
{question,answer}. prevention_html contains prevention only. parts_json must be [].
Do not include markdown or source URLs in the article fields."""

TRANSLATE = """Translate this appliance repair JSON from English into natural,
professional Swedish. Keep exactly the same keys, arrays, numbers and HTML tags.
Do not add technical claims. Use 'servicetekniker', 'tvättmaskin', 'dra ur
kontakten', and natural Swedish terminology. Return JSON only."""


def parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def call(client: anthropic.Anthropic, system: str, payload: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=5000, temperature=0,
        system=system, messages=[{"role": "user", "content": payload}],
    )
    return parse(response.content[0].text)


def validate(locale: str, value: dict) -> None:
    if set(value) != FIELDS:
        raise RuntimeError(f"{locale}: unexpected fields {set(value) ^ FIELDS}")
    if not 140 <= len(value["meta_description"]) <= 160:
        raise RuntimeError(f"{locale}: meta length {len(value['meta_description'])}")
    for key, expected_keys, low, high in (
        ("causes_json", {"cause", "detail"}, 4, 6),
        ("steps_json", {"step", "action", "detail"}, 5, 7),
        ("faq_json", {"question", "answer"}, 4, 5),
    ):
        items = value[key]
        if not isinstance(items, list) or not low <= len(items) <= high:
            raise RuntimeError(f"{locale}: invalid {key} count")
        if any(set(item) != expected_keys for item in items):
            raise RuntimeError(f"{locale}: invalid {key} keys")
    if value["parts_json"] != []:
        raise RuntimeError(f"{locale}: parts_json not empty")
    instruction_text = json.dumps(value["steps_json"], ensure_ascii=False).lower()
    forbidden = (
        "remove the panel", "remove the rear", "remove the front", "open the cabinet",
        "multimeter", "continuity", "test voltage", "test resistance",
        "ta bort panel", "ta av panel", "öppna höljet", "mät spänning", "mät resistans",
    )
    hit = [term for term in forbidden if term in instruction_text]
    if hit:
        raise RuntimeError(f"{locale}: unsafe instruction terms {hit}")


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-001-bosch-e16-e22-before.json").read_text(encoding="utf-8"))
    existing = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    client = anthropic.Anthropic()
    translations = {}
    for article_id, code in IDS.items():
        en = call(client, SYSTEM, f"Brand: Bosch\nAppliance: washing machine\nCode: {code}\nVerified facts: {FACTS[code]}")
        validate("en", en)
        sv = call(client, TRANSLATE, json.dumps(en, ensure_ascii=False))
        validate("sv", sv)
        translations[str(article_id)] = {
            "code": code,
            "preserve": {
                "en_slug": existing[(article_id, "en")]["slug"],
                "sv_slug": existing[(article_id, "sv")]["slug"],
            },
            "en": en,
            "sv": sv,
        }
        print(f"generated {article_id} {code}")
    proposal = {
        "batch": "001-bosch-e16-e22", "status": "proposal_only_not_applied",
        "article_ids": list(IDS), "sources": SOURCES, "translations": translations,
    }
    out = BASE_DIR / "data/article_reviews/batch-001-bosch-e16-e22-proposal.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
