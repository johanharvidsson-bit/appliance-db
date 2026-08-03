"""PR 2A Source Discovery: URL candidates only, never extraction or facts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import time
from typing import Callable, Protocol
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pipeline.url_inventory import normalize_url

WORKER_NAME = "source-discovery"
WORKER_VERSION = "1.0.0"


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    publisher: str | None = None


@dataclass(frozen=True)
class SourceCandidate:
    backlog_id: int
    entity_type: str
    entity_id: str
    locale: str | None
    source_type: str
    candidate_url: str
    normalized_url: str
    publisher: str
    title: str
    confidence: int
    discovery_method: str
    details: dict


class SearchProvider(Protocol):
    name: str
    def search(self, query: str, *, timeout: float) -> list[SearchResult]: ...


class SerperSearchProvider:
    """JSON search API only. It does not fetch or parse result pages."""
    name = "serper"

    def __init__(self, api_key: str):
        if not api_key.strip():
            raise ValueError("SERPER_API_KEY is required")
        self.api_key = api_key

    def search(self, query: str, *, timeout: float) -> list[SearchResult]:
        request = Request("https://google.serper.dev/search", data=json.dumps({"q": query, "num": 10}).encode(),
                          headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        return [SearchResult(x["link"], x.get("title", ""), x.get("source")) for x in payload.get("organic", []) if x.get("link")]


class RateLimitedRetryProvider:
    def __init__(self, provider: SearchProvider, *, delay_seconds: float = 1.0, retries: int = 2,
                 sleep: Callable[[float], None] = time.sleep):
        self.provider, self.delay_seconds, self.retries, self.sleep = provider, delay_seconds, retries, sleep
        self.name = provider.name
        self._last_call = 0.0

    def search(self, query: str, *, timeout: float) -> list[SearchResult]:
        wait = self.delay_seconds - (time.monotonic() - self._last_call)
        if wait > 0:
            self.sleep(wait)
        for attempt in range(self.retries + 1):
            try:
                result = self.provider.search(query, timeout=timeout)
                self._last_call = time.monotonic()
                return result
            except Exception:
                self._last_call = time.monotonic()
                if attempt == self.retries:
                    raise
                self.sleep(min(2 ** attempt, 4))
        return []


def classify(result: SearchResult, context: dict) -> tuple[str, int]:
    host = (urlsplit(result.url).hostname or "").lower().removeprefix("www.")
    path = urlsplit(result.url).path.lower()
    official = {x.lower().removeprefix("www.") for x in context.get("official_domains", [])}
    publisher = (result.publisher or "").lower()
    if any(host == domain or host.endswith("." + domain) for domain in official):
        return ("manufacturer", 95 if "support" in path or "manual" in path else 90)
    if "parts" in host or "spare" in host:
        return "official_parts", 80
    if path.endswith(".pdf") or "service-manual" in path or "servicemanual" in host:
        return "service_manual", 70
    if any(x in host for x in ("manualslib", "manualsonline")):
        return "service_manual", 60
    if any(x in host for x in ("amazon.", "ebay.", "walmart.", "bestbuy.")):
        return "retailer", 45
    if any(x in host for x in ("reddit.", "forum", "stackexchange")):
        return "forum", 25
    return "other", 35


def build_query(item: dict) -> str:
    terms = [item.get("brand_name"), item.get("entity_name"), item.get("action_type"), item.get("locale")]
    suffix = {
        "enrich_model_specs": "official specifications manual",
        "create_model_overview": "official support manual",
        "describe_error_code": "official error code support",
        "translate_error_code": "official error code",
        "translate_fault": "official troubleshooting",
        "create_or_enrich_guide": "official troubleshooting manual",
        "add_source_evidence": "official manual source",
    }.get(item.get("action_type"), "official support manual")
    return " ".join(str(x).strip() for x in [*terms, suffix] if x).strip()


class DiscoveryEngine:
    def discover(self, item: dict, results: list[SearchResult], *, method: str) -> list[SourceCandidate]:
        candidates: dict[str, SourceCandidate] = {}
        for result in results:
            try:
                normalized = normalize_url(result.url)
            except (ValueError, UnicodeError):
                continue
            source_type, confidence = classify(result, item)
            candidate = SourceCandidate(item["backlog_id"], item["entity_type"], str(item["entity_id"]), item.get("locale"),
                                        source_type, result.url, normalized, result.publisher or (urlsplit(result.url).hostname or "unknown"),
                                        result.title, confidence, method, {"tier": {"manufacturer":1,"official_parts":2,"service_manual":3,"retailer":4,"forum":5}.get(source_type,5)})
            previous = candidates.get(normalized)
            if previous is None or candidate.confidence > previous.confidence:
                candidates[normalized] = candidate
        return sorted(candidates.values(), key=lambda x: (-x.confidence, x.normalized_url))


def candidate_dicts(values: list[SourceCandidate]) -> list[dict]:
    return [asdict(x) for x in values]
