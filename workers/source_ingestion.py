"""Deterministic parsing and candidate-fact extraction for PR 2B."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import json
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import pdfplumber

PARSER_VERSION = "1.0.0"
EXTRACTOR_VERSION = "1.0.0"
MAX_EXCERPT = 500


@dataclass
class Segment:
    text: str
    locator: str
    heading: str | None = None
    page: int | None = None
    json_path: str | None = None


@dataclass
class ParsedDocument:
    document_type: str
    language: str | None
    title: str | None
    text: str
    segments: list[Segment]
    page_count: int | None
    metadata: dict = field(default_factory=dict)


@dataclass
class Fact:
    fact_type: str
    predicate: str
    value: object
    locator: str
    excerpt: str
    subject_hint: str | None = None
    unit: str | None = None
    locale: str | None = None
    confidence: int = 70
    status: str = "candidate"
    page: int | None = None
    heading: str | None = None
    json_path: str | None = None
    conflict_key: str | None = None
    conflict_metadata: dict = field(default_factory=dict)

    @property
    def input_hash(self) -> str:
        payload = [
            self.fact_type,
            self.subject_hint,
            self.predicate,
            self.value,
            self.unit,
            self.locator,
        ]
        return sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


def classify_document(url: str, mime: str, title: str | None, text: str) -> str:
    hay = " ".join((url.lower(), (title or "").lower(), text[:1500].lower()))
    host = (urlsplit(url).hostname or "").lower()
    if "forum" in hay or any(x in host for x in ("reddit.", "ifixit.")):
        return "forum_page"
    if "service manual" in hay or "service-manual" in hay:
        return "service_manual"
    if "parts catalog" in hay or "spare parts" in hay:
        return "parts_catalog"
    if "datasheet" in hay or "data sheet" in hay:
        return "technical_datasheet"
    if mime == "application/pdf" or "user manual" in hay or "owner's manual" in hay:
        return "user_manual"
    if any(x in hay for x in ("support", "troubleshooting")):
        return "manufacturer_support_page"
    if any(x in host for x in ("parts", "spares")):
        return "parts_supplier_page"
    if any(x in hay for x in ("retailer", "buy now", "add to cart")):
        return "retailer_product_page"
    if mime == "text/html":
        return "manufacturer_product_page"
    return "unknown"


def parse_document(url: str, mime: str, body: bytes) -> ParsedDocument:
    if mime == "application/pdf":
        segments, metadata = [], {}
        with pdfplumber.open(BytesIO(body)) as pdf:
            metadata = {
                str(k): str(v) for k, v in (pdf.metadata or {}).items() if v is not None
            }
            for number, page in enumerate(pdf.pages, 1):
                text = (page.extract_text() or "").strip()
                if text:
                    segments.append(Segment(text, f"page:{number}", page=number))
            title = metadata.get("Title")
            text = "\n".join(x.text for x in segments)
            return ParsedDocument(
                classify_document(url, mime, title, text),
                metadata.get("Language"),
                title,
                text,
                segments,
                len(pdf.pages),
                metadata,
            )
    encoding = "utf-8"
    decoded = body.decode(encoding, errors="replace")
    if mime == "application/json":
        data = json.loads(decoded)
        segments = []

        def walk(value, path="$"):
            if isinstance(value, dict):
                for key, child in value.items():
                    walk(child, f"{path}.{key}")
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    walk(child, f"{path}[{i}]")
            elif value is not None:
                segments.append(Segment(str(value), path, json_path=path))

        walk(data)
        text = "\n".join(s.text for s in segments)
        return ParsedDocument(
            classify_document(url, mime, None, text),
            None,
            None,
            text,
            segments,
            None,
            {},
        )
    if mime == "text/plain":
        segments = [
            Segment(line.strip(), f"line:{i}")
            for i, line in enumerate(decoded.splitlines(), 1)
            if line.strip()
        ]
        text = "\n".join(x.text for x in segments)
        return ParsedDocument(
            classify_document(url, mime, None, text),
            None,
            None,
            text,
            segments,
            None,
            {},
        )
    soup = BeautifulSoup(decoded, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    language = soup.html.get("lang") if soup.html else None
    segments = []
    heading = None
    for row in soup.select("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.select(":scope > th,:scope > td")
        ]
        if len(cells) >= 2 and cells[0] and cells[1]:
            segments.append(
                Segment(f"{cells[0]}: {cells[1]}", _css_locator(row), heading=heading)
            )
    for element in soup.select("h1,h2,h3,h4,th,td,dt,dd,p,li"):
        text = element.get_text(" ", strip=True)
        if not text:
            continue
        if element.name in {"h1", "h2", "h3", "h4"}:
            heading = text
        locator = _css_locator(element)
        segments.append(Segment(text, locator, heading=heading))
    for index, node in enumerate(soup.select('script[type="application/ld+json"]'), 1):
        try:
            data = json.loads(node.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        flat = json.dumps(data, ensure_ascii=False)
        segments.append(
            Segment(flat, f"jsonld:{index}", json_path=f"$[jsonld:{index}]")
        )
    text = "\n".join(x.text for x in segments)
    return ParsedDocument(
        classify_document(url, mime, title, text),
        language,
        title,
        text,
        segments,
        None,
        {},
    )


def _css_locator(element) -> str:
    parts = []
    current = element
    while current and current.name not in {"html", "[document]"} and len(parts) < 5:
        part = current.name
        if current.get("id"):
            part += f"#{current['id']}"
            parts.append(part)
            break
        siblings = (
            current.parent.find_all(current.name, recursive=False)
            if current.parent
            else []
        )
        if len(siblings) > 1:
            part += f":nth-of-type({siblings.index(current) + 1})"
        parts.append(part)
        current = current.parent
    return " > ".join(reversed(parts))


FIELD_MAP = {
    "capacity": "capacity",
    "weight": "weight",
    "voltage": "voltage",
    "frequency": "frequency",
    "power": "power",
    "energy class": "energy_class",
    "water consumption": "water_consumption",
    "installation type": "installation_type",
    "model": "model_code",
    "model number": "model_code",
    "product code": "product_code",
    "document number": "document_number",
    "revision date": "revision_date",
}
VALUE_UNIT = re.compile(r"^\s*([^|:]{1,80}?)\s*[:|]\s*(.{1,180}?)\s*$")
UNIT = re.compile(r"^(.+?)\s*(kg|g|lb|mm|cm|m|v|hz|kw|w|l|litres?|kwh)\s*$", re.I)
ERROR = re.compile(
    r"\b(?:error\s*)?([A-Z]{1,3}[0-9]{1,3}(?:[-/][A-Z0-9]+)?)\s*[:\-]\s*(.{3,180})",
    re.I,
)
STEP = re.compile(r"^\s*(?:step\s*)?(\d{1,2})[.)]\s+(.{3,300})$", re.I)


def extract_facts(
    document: ParsedDocument,
    *,
    subject_hint: str | None,
    locale: str | None,
    source_trust: int,
) -> list[Fact]:
    facts = []
    for segment in document.segments:
        text = " ".join(segment.text.split())
        match = VALUE_UNIT.match(text)
        if match:
            label, value = match.groups()
            predicate = FIELD_MAP.get(label.casefold().strip())
            if predicate:
                unit = None
                unit_match = UNIT.match(value)
                if unit_match:
                    value, unit = unit_match.group(1).strip(), unit_match.group(2)
                facts.append(
                    _fact(
                        "specification"
                        if predicate
                        not in {
                            "model_code",
                            "product_code",
                            "document_number",
                            "revision_date",
                        }
                        else "identity",
                        predicate,
                        value,
                        segment,
                        subject_hint,
                        locale,
                        source_trust,
                        unit,
                        structured=True,
                    )
                )
        error = ERROR.search(text)
        if error:
            facts.append(
                _fact(
                    "error_code",
                    "meaning",
                    {"code": error.group(1).upper(), "meaning": error.group(2).strip()},
                    segment,
                    subject_hint,
                    locale,
                    source_trust,
                    structured=False,
                )
            )
        step = STEP.match(text)
        if step:
            facts.append(
                _fact(
                    "guide_step",
                    "instruction",
                    {"step_number": int(step.group(1)), "instruction": step.group(2)},
                    segment,
                    subject_hint,
                    locale,
                    source_trust,
                    structured=False,
                )
            )
    return deduplicate_and_conflict(facts)


def _fact(
    fact_type,
    predicate,
    value,
    segment,
    subject_hint,
    locale,
    source_trust,
    unit=None,
    structured=False,
):
    confidence = max(
        0, min(100, round(source_trust * 0.55 + (20 if structured else 10) + 10))
    )
    excerpt = segment.text[:MAX_EXCERPT]
    return Fact(
        fact_type,
        predicate,
        value,
        segment.locator,
        excerpt,
        subject_hint,
        unit,
        locale,
        confidence,
        "candidate",
        segment.page,
        segment.heading,
        segment.json_path,
    )


def deduplicate_and_conflict(facts: list[Fact]) -> list[Fact]:
    unique = {fact.input_hash: fact for fact in facts}
    grouped = {}
    for fact in unique.values():
        key = json.dumps(
            [fact.subject_hint, fact.fact_type, fact.predicate, fact.locale],
            sort_keys=True,
        )
        grouped.setdefault(key, []).append(fact)
    for key, group in grouped.items():
        values = {
            json.dumps(x.value, sort_keys=True, ensure_ascii=False) for x in group
        }
        if len(values) > 1:
            digest = sha256(key.encode()).hexdigest()
            for fact in group:
                fact.status = "conflicted"
                fact.conflict_key = digest
                fact.conflict_metadata = {
                    "reason": "different_values_same_subject_predicate",
                    "candidate_count": len(group),
                }
    return list(unique.values())
