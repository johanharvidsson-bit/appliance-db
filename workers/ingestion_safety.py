"""Network boundary for source ingestion. No browser, cookies, or user sessions."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "RepairBaseSourceIngestion/1.0 (+https://repairbase.example/source-policy)"
ALLOWED_MIME = {"text/html", "text/plain", "application/json", "application/pdf"}


class FetchPolicyError(RuntimeError):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    mime_type: str
    body: bytes
    headers: dict[str, str]


def validate_public_url(url: str, resolver=socket.getaddrinfo) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise FetchPolicyError("blocked", "scheme_not_allowed")
    if parsed.username or parsed.password:
        raise FetchPolicyError("blocked", "url_credentials_not_allowed")
    if not parsed.hostname:
        raise FetchPolicyError("blocked", "hostname_required")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".localhost"):
        raise FetchPolicyError("blocked", "local_or_metadata_host")
    try:
        addresses = {
            item[4][0].split("%")[0]
            for item in resolver(
                host,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                0,
                socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as exc:
        raise FetchPolicyError("failed", "dns_resolution_failed") from exc
    if not addresses:
        raise FetchPolicyError("failed", "dns_resolution_empty")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise FetchPolicyError("blocked", "invalid_resolved_address") from exc
        if not ip.is_global or ip in ipaddress.ip_network("169.254.169.254/32"):
            raise FetchPolicyError("blocked", "non_public_address")


class SafeFetcher:
    def __init__(
        self,
        *,
        timeout: float,
        retries: int,
        rate_limit: float,
        max_bytes: int,
        max_redirects: int = 4,
        session: httpx.Client | None = None,
        resolver=socket.getaddrinfo,
        sleeper=time.sleep,
        check_robots: bool = True,
    ):
        self.timeout, self.retries, self.rate_limit = timeout, retries, rate_limit
        self.max_bytes, self.max_redirects = max_bytes, max_redirects
        self.session = session or httpx.Client(
            follow_redirects=False, verify=True, timeout=timeout
        )
        self.resolver, self.sleeper, self.check_robots = resolver, sleeper, check_robots
        self._last_request = 0.0

    def _robots_allowed(self, url: str) -> bool:
        if not self.check_robots:
            return True
        p = urlsplit(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        validate_public_url(robots_url, self.resolver)
        try:
            response = self.session.get(
                robots_url,
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
                follow_redirects=False,
            )
            if response.status_code >= 400:
                response.close()
                return True
            parser = RobotFileParser()
            parser.parse(response.text[:200_000].splitlines())
            allowed = parser.can_fetch(USER_AGENT, url)
            response.close()
            return allowed
        except httpx.HTTPError:
            return True

    def fetch(
        self, url: str, *, etag: str | None = None, last_modified: str | None = None
    ) -> FetchResult:
        requested, current = url, url
        if not self._robots_allowed(url):
            raise FetchPolicyError("blocked", "robots_disallowed")
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf,application/json,text/plain;q=0.8",
            "Accept-Encoding": "gzip",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        for redirect_count in range(self.max_redirects + 1):
            validate_public_url(current, self.resolver)
            delay = self.rate_limit - (time.monotonic() - self._last_request)
            if delay > 0:
                self.sleeper(delay)
            response = None
            for attempt in range(self.retries + 1):
                try:
                    request = self.session.build_request(
                        "GET", current, headers=headers
                    )
                    response = self.session.send(request, stream=True)
                    self._last_request = time.monotonic()
                    if (
                        response.status_code not in {429, 500, 502, 503, 504}
                        or attempt == self.retries
                    ):
                        break
                    response.close()
                except httpx.HTTPError as exc:
                    if attempt == self.retries:
                        raise FetchPolicyError("failed", "network_error") from exc
                self.sleeper(min(2**attempt, 4))
            assert response is not None
            if response.status_code == 304:
                result = FetchResult(
                    requested,
                    current,
                    304,
                    "",
                    b"",
                    self._safe_headers(response.headers),
                )
                response.close()
                return result
            if response.is_redirect:
                if redirect_count == self.max_redirects:
                    response.close()
                    raise FetchPolicyError("blocked", "too_many_redirects")
                location = response.headers.get("Location")
                if not location:
                    response.close()
                    raise FetchPolicyError(
                        "invalid_content", "redirect_without_location"
                    )
                current = urljoin(current, location)
                response.close()
                continue
            if response.status_code >= 400:
                response.close()
                raise FetchPolicyError("failed", f"http_{response.status_code}")
            mime = (
                response.headers.get("Content-Type", "")
                .split(";", 1)[0]
                .strip()
                .lower()
            )
            if mime not in ALLOWED_MIME:
                response.close()
                raise FetchPolicyError("unsupported", "unsupported_mime")
            length = response.headers.get("Content-Length")
            if length:
                try:
                    declared_length = int(length)
                except ValueError as exc:
                    response.close()
                    raise FetchPolicyError(
                        "invalid_content", "invalid_content_length"
                    ) from exc
                if declared_length > self.max_bytes:
                    response.close()
                    raise FetchPolicyError("too_large", "content_length_exceeds_limit")
            chunks, total = [], 0
            for chunk in response.iter_bytes(64 * 1024):
                total += len(chunk)
                if total > self.max_bytes:
                    response.close()
                    raise FetchPolicyError("too_large", "stream_exceeds_limit")
                chunks.append(chunk)
            body = b"".join(chunks)
            safe_headers = self._safe_headers(response.headers)
            response.close()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                try:
                    body = gzip.decompress(body)
                except gzip.BadGzipFile:
                    pass
                if len(body) > self.max_bytes:
                    raise FetchPolicyError(
                        "too_large", "decompressed_content_exceeds_limit"
                    )
            self._validate_signature(mime, body)
            return FetchResult(
                requested,
                current,
                response.status_code,
                mime,
                body,
                safe_headers,
            )
        raise AssertionError("redirect loop boundary")

    @staticmethod
    def _safe_headers(headers) -> dict[str, str]:
        allowed = {"content-type", "content-length", "etag", "last-modified"}
        return {k.lower(): v for k, v in headers.items() if k.lower() in allowed}

    @staticmethod
    def _validate_signature(mime: str, body: bytes) -> None:
        if mime == "application/pdf" and not body.lstrip().startswith(b"%PDF-"):
            raise FetchPolicyError("invalid_content", "pdf_signature_mismatch")
        if mime != "application/pdf" and b"\x00" in body[:4096]:
            raise FetchPolicyError("invalid_content", "binary_text_mismatch")
