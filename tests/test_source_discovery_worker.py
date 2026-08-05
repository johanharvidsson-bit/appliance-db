import json
from pathlib import Path

import pytest

from workers.__main__ import main
from workers.source_discovery import DiscoveryEngine, RateLimitedRetryProvider, SearchResult, build_query, classify

FIXTURE=Path("tests/fixtures/source_discovery.json")


def test_tier_confidence_is_deterministic():
    context={"official_domains":["samsung.com"]}
    assert classify(SearchResult("https://samsung.com/support/x/manual","x"),context)==("manufacturer",95)
    assert classify(SearchResult("https://manualslib.com/a.pdf","x"),context)==("service_manual",70)
    assert classify(SearchResult("https://reddit.com/r/a","x"),context)==("forum",25)


def test_candidates_are_normalized_ranked_and_deduplicated():
    data=json.loads(FIXTURE.read_text(encoding="utf-8")); item=data["backlog"][0]
    values=DiscoveryEngine().discover(item,[SearchResult(**x) for x in data["results"]["1"]],method="fixture")
    assert len(values)==3
    assert values[0].source_type=="manufacturer" and values[0].confidence==95
    assert values[-1].source_type=="forum" and values[-1].confidence==25


def test_query_uses_existing_entity_context_only():
    item=json.loads(FIXTURE.read_text(encoding="utf-8"))["backlog"][0]
    query=build_query(item)
    assert "Samsung" in query and "WF45" in query and "official specifications" in query


def test_retry_is_bounded_and_rate_limited():
    class Fake:
        name="fake"
        def __init__(self): self.calls=0
        def search(self,query,*,timeout):
            self.calls+=1
            if self.calls<3: raise TimeoutError()
            return [SearchResult("https://example.com/","ok")]
    fake=Fake(); sleeps=[]
    wrapped=RateLimitedRetryProvider(fake,delay_seconds=0,retries=2,sleep=sleeps.append)
    assert len(wrapped.search("x",timeout=1))==1 and fake.calls==3
    assert sleeps==[1,2]


def test_offline_cli_reports_candidates_and_not_found(tmp_path,capsys):
    assert main(["source-discovery","--site","appliance-repair-base","--fixture",str(FIXTURE),"--output-dir",str(tmp_path)])==0
    result=json.loads(capsys.readouterr().out)
    assert result["dry_run"] is True and result["backlog_scanned"]==2
    assert result["source_candidates"]==3 and result["not_found"]==1
    assert len(list(tmp_path.glob("*.json")))==1 and len(list(tmp_path.glob("*.md")))==1


def test_fixture_mode_ignores_environment():
    # Fixture mode never touches a database or network regardless of
    # --environment, so it is not blanket-rejected for production - only a
    # real, unapproved production *write* is (see config/target_safety.py).
    main(["source-discovery","--site","x","--environment","production","--fixture",str(FIXTURE)])


def test_no_extraction_llm_or_content_writes():
    source="".join(Path(x).read_text(encoding="utf-8") for x in ("workers/source_discovery.py","workers/source_repository.py","workers/source_cli.py"))
    for forbidden in ("BeautifulSoup","pdfplumber","anthropic","openai"):
        assert forbidden not in source
    for table in ("brands","categories","models","model_variants","product_codes","error_codes","faults","guides","articles","url_registry"):
        assert f"INSERT INTO {table}" not in source and f"UPDATE {table}" not in source


def test_migration_is_internal_idempotent_and_history_preserving():
    sql=Path("db/migrations/021_source_discovery_worker.sql").read_text(encoding="utf-8").lower()
    assert "create table public.source_candidates" in sql
    assert "unique(site_id,environment,backlog_id,candidate_key)" in sql
    assert "on delete cascade" not in sql
    assert "revoke all on public.%i from public,anon,authenticated" in sql
