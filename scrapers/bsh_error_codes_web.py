"""
scrapers/bsh_error_codes_web.py

Scrapes Bosch/Siemens washing machine error codes from public web pages.
BSH Group uses the same error code set across both brands.

Sources (tried in order, results merged):
  1. Bosch US official error code page
  2. Domex UK comprehensive table

Returns list of {"code": ..., "display_text": ...} dicts.
"""

import re
import httpx
from bs4 import BeautifulSoup
from loguru import logger

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"}


_CODE_RE = re.compile(
    r"""^
    (
        [EFH]\d{1,3}          # E16, F17, H9E, E:30, etc.
        | [EFH]:[0-9][\d/.-]* # E:30/-10
        | CL | NO | END        # named codes
    )
    (\s*[,/]\s*[EFH]\d{1,3})* # optional alternates: E16/F16, E42,E43
    $""",
    re.VERBOSE | re.IGNORECASE,
)


def _looks_like_code(raw: str) -> bool:
    """Return True if raw text looks like a genuine error code entry."""
    clean = raw.strip().split("\n")[0].strip()  # first line only
    return bool(_CODE_RE.match(clean))


def _normalise_code(raw: str) -> str:
    """Strip whitespace, collapse multiple codes on one entry to primary."""
    # E16, E34, F16, F34 → take first token
    code = raw.strip().split(",")[0].split("/")[0].strip()
    # Remove surrounding punctuation
    code = code.strip(".:–-").strip()
    return code.upper()


def _fetch(url: str) -> BeautifulSoup | None:
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=20, follow_redirects=True)
        if r.status_code == 200:
            return BeautifulSoup(r.text, "lxml")
        logger.debug(f"  {url} → HTTP {r.status_code}")
    except Exception as e:
        logger.debug(f"  {url} → {e}")
    return None


# ── Source 1: Bosch US official ────────────────────────────────────────────────

def _scrape_bosch_official() -> list[dict]:
    """
    https://www.bosch-home.com/us/owner-support/error-codes/washers
    Accordion layout — error code headings with description text beneath.
    """
    url = "https://www.bosch-home.com/us/owner-support/error-codes/washers"
    soup = _fetch(url)
    if not soup:
        return []

    results: dict[str, str] = {}

    # Headings contain the code, next sibling/paragraph has description
    for el in soup.find_all(["h2", "h3", "h4", "strong", "b"]):
        text = el.get_text(" ", strip=True)
        # Match patterns like "E17, F17, F29" or "E:30/-10" or "H9E"
        m = re.match(r"^([A-Z][A-Z0-9:.\-/,\s]{1,30})\s*[–—-]?\s*(.+)?$", text, re.I)
        if not m:
            continue
        raw_code = m.group(1).strip()
        # Must look like an error code (letter + digits or known format)
        if not re.search(r"[A-Z][0-9]|[0-9][A-Z]|E:|F:|H[0-9]", raw_code, re.I):
            continue
        code = _normalise_code(raw_code)
        if not code or len(code) > 15:
            continue

        # Description from inline text or next sibling
        desc = (m.group(2) or "").strip()
        if not desc:
            nxt = el.find_next_sibling(["p", "li", "div"])
            if nxt:
                desc = nxt.get_text(" ", strip=True)

        if code and desc and len(desc) > 5:
            if len(desc) > len(results.get(code, "")):
                results[code] = desc[:500]

    logger.debug(f"Bosch official: {len(results)} codes")
    return [{"code": k, "display_text": v} for k, v in results.items()]


# ── Source 2: Domex UK comprehensive table ─────────────────────────────────────

def _expand_range(raw_code: str, desc: str) -> list[tuple[str, str]]:
    """
    If raw_code is a range like 'E60 – E69' or 'E90 – E92', expand to individual codes.
    Returns list of (code, desc) tuples.
    """
    m = re.match(r'^([EFH])(\d{1,3})\s*[–—-]\s*[EFH](\d{1,3})', raw_code.strip(), re.I)
    if m:
        prefix = m.group(1).upper()
        start = int(m.group(2))
        end   = int(m.group(3))
        if 1 <= (end - start) <= 20:  # sanity: only expand small ranges
            return [(f"{prefix}{n}", desc) for n in range(start, end + 1)]
    return []


def _scrape_domex_bosch() -> list[dict]:
    """
    https://www.domex-uk.co.uk/help-advice/bosch-washing-machine-error-codes-explained/
    HTML table with Code / Description / Likely Cause columns.
    Also expands range rows like 'E60 – E69' into individual codes.
    """
    url = "https://www.domex-uk.co.uk/help-advice/bosch-washing-machine-error-codes-explained/"
    soup = _fetch(url)
    if not soup:
        return []

    results: dict[str, str] = {}

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            raw_code = cells[0]
            desc_parts = [c for c in cells[1:] if c and c.lower() not in ("", "n/a", "-")]
            desc = " — ".join(desc_parts)[:500]
            if not desc or len(desc) <= 5:
                continue

            # Try to expand range entries first (e.g. "E60 – E69")
            expanded = _expand_range(raw_code, desc)
            if expanded:
                for code, d in expanded:
                    if len(d) > len(results.get(code, "")):
                        results[code] = d
                continue

            # Single code — apply normal filter + normalise
            if not _looks_like_code(raw_code):
                # Also accept "CL / CHILD" style entries: take first token
                first_token = raw_code.strip().split()[0].strip("./,")
                if not re.match(r'^([EFH]\d{1,3}|CL|NO|END)$', first_token, re.I):
                    continue
                raw_code = first_token

            code = _normalise_code(raw_code)
            if not code or len(code) > 12:
                continue
            if len(desc) > len(results.get(code, "")):
                results[code] = desc

    logger.debug(f"Domex UK: {len(results)} codes")
    return [{"code": k, "display_text": v} for k, v in results.items()]


# ── Public API ─────────────────────────────────────────────────────────────────

def scrape_bsh_error_codes() -> list[dict]:
    """
    Fetch and merge Bosch/Siemens error codes from all available sources.
    Returns deduplicated list of {"code": ..., "display_text": ...}.
    """
    merged: dict[str, str] = {}

    for fn in [_scrape_domex_bosch, _scrape_bosch_official]:
        for item in fn():
            code = item["code"]
            desc = item["display_text"]
            # Keep the longer / more descriptive entry
            if len(desc) > len(merged.get(code, "")):
                merged[code] = desc

    # Filter: codes must start with a letter and be reasonable length
    final = [
        {"code": k, "display_text": v}
        for k, v in sorted(merged.items())
        if re.match(r"^[A-Z]", k) and 2 <= len(k) <= 12 and len(v) > 5
    ]
    logger.info(f"BSH error codes scraped: {len(final)} unique codes")
    return final
