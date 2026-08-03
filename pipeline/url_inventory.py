"""Bounded URL-baseline inventory with no redirect or publishing behavior."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Callable, Iterable, Protocol
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from bs4 import BeautifulSoup

from config.environment import load_settings
from config.target_safety import assert_safe_target


SITE_ID = "appliance-repair-base"
USER_AGENT = "ApplianceRepairBase-URLBaseline/1.0 (+read-only inventory)"
ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}
ALLOWED_ENTITY_TYPES = {"brand", "category", "model", "product_code", "error_code", "fault", "article"}


def normalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"URL must be absolute HTTP(S): {value!r}")
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    port = parsed.port
    netloc = host if port is None or (scheme, port) in {("http", 80), ("https", 443)} else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if "." not in path.rsplit("/", 1)[-1] and not path.endswith("/"):
        path += "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


@dataclass(frozen=True)
class URLCandidate:
    url: str
    page_type: str
    entity_type: str | None = None
    entity_id: int | None = None
    sitemap_present: bool | None = None
    internal_incoming_links: int | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "URLCandidate":
        candidate = cls(**value)
        if candidate.entity_type is None and candidate.entity_id is not None:
            raise ValueError("entity_id requires entity_type")
        if candidate.entity_type is not None and candidate.entity_type not in ALLOWED_ENTITY_TYPES:
            raise ValueError(f"unsupported entity_type: {candidate.entity_type}")
        if candidate.entity_type is not None and candidate.entity_id is None:
            raise ValueError("entity_type requires entity_id")
        if candidate.internal_incoming_links is not None and candidate.internal_incoming_links < 0:
            raise ValueError("internal_incoming_links cannot be negative")
        return candidate


@dataclass(frozen=True)
class FetchResult:
    status: int
    final_url: str
    body: bytes
    content_type: str


@dataclass(frozen=True)
class URLObservation:
    site_id: str
    environment: str
    url: str
    normalized_url: str
    path: str
    page_type: str
    http_status: int | None
    canonical_url: str | None
    sitemap_present: bool | None
    internal_incoming_links: int | None
    classification: str
    classification_reason: str | None
    first_observed_at: str
    last_observed_at: str
    entity_type: str | None
    entity_id: int | None


class ObservationSink(Protocol):
    def write(self, observations: list[URLObservation]) -> None: ...


class JsonLinesSink:
    def __init__(self, path: Path):
        self.path = path

    def write(self, observations: list[URLObservation]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8", newline="\n") as handle:
            for observation in observations:
                handle.write(json.dumps(asdict(observation), ensure_ascii=False, sort_keys=True) + "\n")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def fetch_http(url: str, *, timeout: float) -> FetchResult:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    opener = build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return FetchResult(response.status, response.geturl(), response.read(2_000_000), response.headers.get_content_type())
    except HTTPError as error:
        return FetchResult(error.code, error.geturl(), error.read(2_000_000), error.headers.get_content_type())


def extract_canonical(result: FetchResult) -> str | None:
    if result.status != 200 or result.content_type not in {"text/html", "application/xhtml+xml"}:
        return None
    soup = BeautifulSoup(result.body, "html.parser")
    link = soup.find("link", rel=lambda value: value and "canonical" in value)
    href = link.get("href") if link else None
    return normalize_url(urljoin(result.final_url, href)) if isinstance(href, str) and href.strip() else None


def inventory(
    candidates: Iterable[URLCandidate],
    *,
    environment: str,
    check_http: bool = False,
    timeout: float = 10.0,
    max_urls: int = 500,
    now: datetime | None = None,
    fetcher: Callable[..., FetchResult] = fetch_http,
) -> list[URLObservation]:
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError(f"unsupported environment: {environment}")
    if not 1 <= max_urls <= 5_000:
        raise ValueError("max_urls must be between 1 and 5000")
    if not 0 < timeout <= 30:
        raise ValueError("timeout must be greater than 0 and at most 30 seconds")

    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    seen: set[str] = set()
    observations: list[URLObservation] = []
    for candidate in candidates:
        normalized = normalize_url(candidate.url)
        if normalized in seen:
            continue
        if len(observations) >= max_urls:
            break
        seen.add(normalized)
        status = None
        canonical = None
        if check_http:
            result = fetcher(normalized, timeout=timeout)
            status = result.status
            canonical = extract_canonical(result)
        observations.append(
            URLObservation(
                site_id=SITE_ID,
                environment=environment,
                url=candidate.url,
                normalized_url=normalized,
                path=urlsplit(normalized).path,
                page_type=candidate.page_type,
                http_status=status,
                canonical_url=canonical,
                sitemap_present=candidate.sitemap_present,
                internal_incoming_links=candidate.internal_incoming_links,
                classification="unclassified",
                classification_reason=None,
                first_observed_at=timestamp,
                last_observed_at=timestamp,
                entity_type=candidate.entity_type,
                entity_id=candidate.entity_id,
            )
        )
    return observations


def read_candidates(path: Path) -> list[URLCandidate]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("input must be a JSON array")
    return [URLCandidate.from_dict(row) for row in rows]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a bounded, read-only URL baseline artifact")
    parser.add_argument("--input", type=Path, required=True, help="JSON array of URL candidates")
    parser.add_argument("--output", type=Path, required=True, help="JSONL observation artifact")
    parser.add_argument("--environment", choices=sorted(ALLOWED_ENVIRONMENTS), default="development")
    parser.add_argument("--check-http", action="store_true", help="perform bounded HTTP GET checks")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-urls", type=int, default=500)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check_http:
        settings = load_settings()
        first = read_candidates(args.input)
        for candidate in first[: args.max_urls]:
            assert_safe_target(candidate.url, app_env=settings.app_env, operation="read")
        candidates = first
    else:
        candidates = read_candidates(args.input)
    observations = inventory(
        candidates,
        environment=args.environment,
        check_http=args.check_http,
        timeout=args.timeout,
        max_urls=args.max_urls,
    )
    JsonLinesSink(args.output).write(observations)
    print(json.dumps({"observed": len(observations), "http_checks": args.check_http, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
