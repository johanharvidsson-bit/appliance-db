from datetime import datetime, timezone
import json

import pytest

from pipeline.url_inventory import FetchResult, URLCandidate, extract_canonical, inventory, main, normalize_url


NOW = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


def test_normalize_url_is_deterministic_and_removes_fragment():
    assert normalize_url("HTTPS://Example.COM:443/a//b#section") == "https://example.com/a/b/"


def test_inventory_is_offline_by_default_and_preserves_unknowns():
    def forbidden_fetch(*_args, **_kwargs):
        raise AssertionError("network must not be used")

    rows = inventory(
        [URLCandidate("https://example.com/model", "model", "model", 7)],
        environment="development",
        now=NOW,
        fetcher=forbidden_fetch,
    )
    assert len(rows) == 1
    assert rows[0].http_status is None
    assert rows[0].canonical_url is None
    assert rows[0].classification == "unclassified"
    assert rows[0].entity_id == 7


def test_inventory_extracts_self_canonical_from_html():
    result = FetchResult(
        200,
        "https://example.com/model/",
        b'<html><head><link rel="canonical" href="/model/"></head></html>',
        "text/html",
    )
    rows = inventory(
        [URLCandidate("https://example.com/model", "model")],
        environment="staging",
        check_http=True,
        now=NOW,
        fetcher=lambda *_args, **_kwargs: result,
    )
    assert rows[0].http_status == 200
    assert rows[0].canonical_url == "https://example.com/model/"


def test_non_200_is_recorded_without_canonical():
    result = FetchResult(404, "https://example.com/missing/", b"not found", "text/html")
    rows = inventory(
        [URLCandidate("https://example.com/missing", "model")],
        environment="staging",
        check_http=True,
        now=NOW,
        fetcher=lambda *_args, **_kwargs: result,
    )
    assert rows[0].http_status == 404
    assert rows[0].canonical_url is None
    assert extract_canonical(result) is None


def test_duplicate_normalized_urls_are_deduplicated_first_wins():
    rows = inventory(
        [
            URLCandidate("https://example.com/model", "model", "model", 1),
            URLCandidate("https://EXAMPLE.com/model/", "model", "model", 2),
        ],
        environment="development",
        now=NOW,
    )
    assert len(rows) == 1
    assert rows[0].entity_id == 1


def test_bounds_and_candidate_validation():
    with pytest.raises(ValueError):
        inventory([], environment="invalid")
    with pytest.raises(ValueError):
        inventory([], environment="development", max_urls=0)
    with pytest.raises(ValueError):
        URLCandidate.from_dict({"url": "https://example.com/", "page_type": "model", "entity_type": "model"})


def test_cli_writes_artifact_without_http(tmp_path):
    source = tmp_path / "input.json"
    output = tmp_path / "output.jsonl"
    source.write_text(
        json.dumps([{"url": "https://example.com/model", "page_type": "model", "entity_type": "model", "entity_id": 9}]),
        encoding="utf-8",
    )
    assert main(["--input", str(source), "--output", str(output), "--max-urls", "10"]) == 0
    row = json.loads(output.read_text(encoding="utf-8"))
    assert row["entity_id"] == 9
    assert row["http_status"] is None
    assert row["classification"] == "unclassified"
