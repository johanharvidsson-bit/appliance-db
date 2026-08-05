from __future__ import annotations

import json
from pathlib import Path
import socket

import httpx
import pytest

from workers.__main__ import main
from workers.ingestion_repository import IngestionRepository
from workers.ingestion_safety import FetchPolicyError, SafeFetcher, validate_public_url
from workers.source_ingestion import extract_facts, parse_document

FIXTURE = Path(__file__).parent / "fixtures" / "source_ingestion.json"


def public_resolver(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def private_resolver(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]


@pytest.mark.parametrize("url", ["https://example.com/a", "http://example.com/a"])
def test_public_http_urls_allowed(url):
    validate_public_url(url, public_resolver)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/a",
        "http://u:p@example.com/a",
        "http://localhost/a",
        "http://[::1]/a",
    ],
)
def test_unsafe_urls_are_blocked(url):
    with pytest.raises(FetchPolicyError):
        validate_public_url(url, private_resolver)


def test_redirect_destination_is_revalidated_and_private_target_blocked():
    def resolver(host, *_args, **_kwargs):
        address = "127.0.0.1" if host == "internal.example" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={"location": "http://internal.example/private"},
            request=request,
        )
    )
    fetcher = SafeFetcher(
        timeout=1,
        retries=0,
        rate_limit=0,
        max_bytes=1000,
        session=httpx.Client(transport=transport),
        resolver=resolver,
        check_robots=False,
    )
    with pytest.raises(FetchPolicyError, match="non_public_address"):
        fetcher.fetch("https://example.com/start")


@pytest.mark.parametrize(
    ("mime", "body", "expected"),
    [
        ("video/mp4", b"video", "unsupported_mime"),
        ("application/pdf", b"not-pdf", "pdf_signature_mismatch"),
        ("text/plain", b"a" * 20, "content_length_exceeds_limit"),
    ],
)
def test_fetch_rejects_unsupported_invalid_and_too_large(mime, body, expected):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": mime, "content-length": str(len(body))},
            content=body,
            request=request,
        )
    )
    fetcher = SafeFetcher(
        timeout=1,
        retries=0,
        rate_limit=0,
        max_bytes=10,
        session=httpx.Client(transport=transport),
        resolver=public_resolver,
        check_robots=False,
    )
    with pytest.raises(FetchPolicyError, match=expected):
        fetcher.fetch("https://example.com/source")


def test_conditional_fetch_preserves_304_without_body():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(304, request=request)

    fetcher = SafeFetcher(
        timeout=1,
        retries=0,
        rate_limit=0,
        max_bytes=100,
        session=httpx.Client(transport=httpx.MockTransport(handler)),
        resolver=public_resolver,
        check_robots=False,
    )
    result = fetcher.fetch("https://example.com/source", etag='"abc"')
    assert result.status_code == 304 and result.body == b""
    assert seen["if-none-match"] == '"abc"'


def test_html_extraction_has_exact_locators_and_conflicts():
    body = b"<h1>Specifications</h1><table><tr><th>Voltage</th><td>230 V</td></tr><tr><th>Voltage</th><td>120 V</td></tr><tr><th>Capacity</th><td>9 kg</td></tr></table>"
    doc = parse_document("https://example.com/support", "text/html", body)
    facts = extract_facts(doc, subject_hint="model:1", locale="en", source_trust=95)
    voltages = [f for f in facts if f.predicate == "voltage"]
    assert len(voltages) == 2 and all(f.status == "conflicted" for f in voltages)
    assert all(f.locator and len(f.excerpt) <= 500 for f in facts)


def test_support_page_extracts_exact_error_description_not_heading_steps():
    body = b"""
    <html lang="en-GB"><head><title>Resolve a 5E or 5C error</title></head><body>
      <h1>How to resolve a 5E or 5C error code</h1>
      <p>A 5E or 5C error code indicates that the washing machine has detected a drainage issue.</p>
      <h2>1. Check the drain filter</h2>
      <ul><li>Clean the filter and check the drain hose for blockages.</li></ul>
    </body></html>
    """
    doc = parse_document("https://www.samsung.com/support/5c", "text/html", body)
    facts = extract_facts(
        doc,
        subject_hint="error_code:20",
        subject_identifier="5C",
        locale="en",
        source_trust=95,
    )
    meanings = [fact for fact in facts if fact.fact_type == "error_code"]
    assert len(meanings) == 1
    assert meanings[0].value == {
        "code": "5C",
        "meaning": "A 5E or 5C error code indicates that the washing machine has detected a drainage issue.",
    }
    assert meanings[0].status == "candidate"
    assert not [fact for fact in facts if fact.fact_type == "guide_step"]


def test_numbered_steps_have_independent_conflict_identity():
    body = b"<p>1. Unplug the appliance.</p><p>2. Check the drain hose.</p>"
    doc = parse_document("https://example.com/support", "text/html", body)
    facts = extract_facts(doc, subject_hint="error_code:1", locale="en", source_trust=95)
    steps = [fact for fact in facts if fact.fact_type == "guide_step"]
    assert len(steps) == 2
    assert all(fact.status == "candidate" for fact in steps)


def test_json_extraction_retains_json_path():
    doc = parse_document(
        "https://example.com/a.json",
        "application/json",
        b'{"capacity":"Capacity: 9 kg"}',
    )
    fact = extract_facts(doc, subject_hint="model:1", locale="en", source_trust=90)[0]
    assert fact.json_path == "$.capacity"


def test_fixture_dry_run_covers_html_pdf_conflict_and_failures(tmp_path, capsys):
    assert (
        main(
            [
                "source-ingestion",
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
    assert output["fetched"] == 2 and output["documents"] == 2
    assert output["accepted_scanned"] == 4
    assert output["candidate_facts"] >= 3 and output["conflicted"] == 2
    assert output["blocked"] == 1 and output["unsupported"] == 1
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert {x.get("document_type") for x in report["items"]} >= {
        "manufacturer_support_page",
        "user_manual",
    }


def test_fixture_mode_ignores_environment():
    # Fixture mode never touches a database or network regardless of
    # --environment, so it is not blanket-rejected for production - only a
    # real, unapproved production *write* is (see config/target_safety.py).
    main(
        [
            "source-ingestion",
            "--site",
            "x",
            "--environment",
            "production",
            "--fixture",
            str(FIXTURE),
        ]
    )


def test_write_allowlist_excludes_canonical_content_tables():
    assert IngestionRepository.WRITABLE_TABLES.isdisjoint(
        {
            "models",
            "error_codes",
            "faults",
            "guides",
            "articles",
            "model_specs",
            "url_registry",
            "url_redirects",
        }
    )


def test_migration_has_historical_and_security_guards():
    sql = (
        Path(__file__).parents[1]
        / "db/migrations/022_source_ingestion_enrichment_worker.sql"
    ).read_text(encoding="utf-8")
    assert "ON DELETE CASCADE" not in sql
    assert sql.count("FORCE ROW LEVEL SECURITY") == 1
    assert "REVOKE ALL" in sql and "REVOKE DELETE" in sql
    assert "'verified'" not in sql
    assert "source_fetches_version_uidx" in sql
    assert (
        "UNIQUE(source_document_id,extractor_name,extractor_version,input_hash)" in sql
    )


def test_candidate_selection_is_accepted_active_cube_only():
    source = (Path(__file__).parents[1] / "workers/ingestion_repository.py").read_text(
        encoding="utf-8"
    )
    assert "sc.status='accepted'" in source
    assert "css.status='active'" in source
    assert "b.status IN('queued','in_progress','deferred')" in source
