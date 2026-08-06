from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.target_safety import TargetSafetyError
from workers.__main__ import main
from workers.translation import (
    TRANSLATABLE_TABLES,
    TranslationEngine,
    build_slug,
    needs_translation,
    source_content_hash,
)

FIXTURE = Path("tests/fixtures/translation.json")


class FakeMessage:
    def __init__(self, text):
        self.content = [type("Block", (), {"text": text})()]


class FakeMessages:
    def __init__(self, response_json):
        self.response_json = response_json
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeMessage(json.dumps(self.response_json))


class FakeClient:
    def __init__(self, response_json):
        self.messages = FakeMessages(response_json)


def test_needs_translation_detects_missing_and_stale_and_skips_matching():
    fields = TRANSLATABLE_TABLES["error_code"]["fields"]
    source = {"title": "5E", "description": "Drain error"}
    assert needs_translation(source, None, fields) is True
    stale = {"source_hash": "not-the-real-hash"}
    assert needs_translation(source, stale, fields) is True
    current = {"source_hash": source_content_hash(source, fields)}
    assert needs_translation(source, current, fields) is False


def test_translate_preserves_step_count_order_and_non_text_keys():
    guide_fields = TRANSLATABLE_TABLES["guide"]["fields"]
    row = {
        "title": "Error Code 294 repair guide",
        "steps_json": [
            {"step_number": 1, "instruction": "Unplug the appliance."},
            {"step_number": 2, "instruction": "Clean the drain filter."},
        ],
    }
    client = FakeClient(
        {
            "title": "Felkod 294 reparationsguide",
            "steps_json": [
                {"step_number": 1, "instruction": "Dra ur kontakten."},
                {"step_number": 2, "instruction": "Rengor avloppsfiltret."},
            ],
        }
    )
    engine = TranslationEngine(client)
    result = engine.translate(row, guide_fields, source_locale="en", target_locale="sv")
    assert result["title"] == "Felkod 294 reparationsguide"
    assert [s["step_number"] for s in result["steps_json"]] == [1, 2]
    assert result["steps_json"][0]["instruction"] == "Dra ur kontakten."
    # temperature=0, structured JSON in/out - not a free-text generation call.
    assert client.messages.calls[0]["temperature"] == 0


def test_translate_rejects_mismatched_step_count_rather_than_guess():
    guide_fields = TRANSLATABLE_TABLES["guide"]["fields"]
    row = {
        "steps_json": [
            {"step_number": 1, "instruction": "Unplug the appliance."},
            {"step_number": 2, "instruction": "Clean the drain filter."},
        ]
    }
    client = FakeClient({"steps_json": [{"step_number": 1, "instruction": "Dra ur kontakten."}]})
    engine = TranslationEngine(client)
    result = engine.translate(row, guide_fields, source_locale="en", target_locale="sv")
    assert "steps_json" not in result


def test_translate_skips_empty_source_without_calling_the_model():
    client = FakeClient({})
    engine = TranslationEngine(client)
    result = engine.translate({}, TRANSLATABLE_TABLES["fault"]["fields"], source_locale="en", target_locale="sv")
    assert result == {}
    assert client.messages.calls == []


def test_build_slug_is_stable_and_locale_scoped():
    assert build_slug("guide", 1, "sv") == "guide-1-sv"
    assert build_slug("guide", 1, "en") != build_slug("guide", 1, "sv")


def test_fixture_run_reports_would_translate_candidates(tmp_path, capsys):
    assert (
        main(
            [
                "translation",
                "--site",
                "appliance-repair-base",
                "--fixture",
                str(FIXTURE),
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True and output["scanned"] == 1
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert report["items"][0]["entity_type"] == "guide"
    assert report["items"][0]["would_translate"] is True


def test_fixture_rejects_mismatched_site():
    with pytest.raises(SystemExit, match="fixture site does not match"):
        main(
            [
                "translation",
                "--site",
                "wrong-site",
                "--fixture",
                str(FIXTURE),
            ]
        )


def test_real_run_requires_dsn(monkeypatch):
    monkeypatch.delenv("REPAIRBASE_SECURITY_TEST_DB_URL", raising=False)
    with pytest.raises(SystemExit, match="REPAIRBASE_SECURITY_TEST_DB_URL is required"):
        main(["translation", "--site", "appliance-repair-base", "--dry-run"])


def test_production_write_without_approval_token_is_fail_closed(monkeypatch):
    # TEST-NET-3 (RFC 5737): non-routable, so this can never reach a real
    # host; the "appliancedb" database name alone is enough for
    # classify_target to mark this PRODUCTION_DATABASE regardless of host.
    monkeypatch.setenv(
        "REPAIRBASE_SECURITY_TEST_DB_URL",
        "postgresql://u:p@203.0.113.1:5432/appliancedb",
    )
    monkeypatch.delenv("ALLOW_PRODUCTION_WRITE", raising=False)
    monkeypatch.delenv("PRODUCTION_WRITE_CONFIRMATION", raising=False)
    with pytest.raises(TargetSafetyError):
        main(
            [
                "translation",
                "--site",
                "appliance-repair-base",
                "--environment",
                "production",
            ]
        )
