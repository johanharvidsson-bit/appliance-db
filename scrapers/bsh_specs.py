"""
scrapers/bsh_specs.py

Scrapes washing machine specifications for Bosch and Siemens models.

Both brands use the identical BSH Group Next.js App Router platform.
Spec data is embedded in the page as an RSC payload (self.__next_f.push[...])
containing a "product.specifications" array with key/name/value/unit objects.

URL strategy:
  Build a model→URL cache from multiple regional sitemaps so we can construct
  the correct full path (category varies by product type).
  Fallback: try direct short URL construction.

Regional coverage per brand:
  Bosch:   UK (bosch-home.co.uk), DE (bosch-home.com/de), IN (bosch-home.in), IT
  Siemens: UK (siemens-home.bsh-group.com/uk), DE (.../de)

Usage (via scrape_specs.py):
    python -m pipeline.scrape_specs --brand bosch --category washing-machines
    python -m pipeline.scrape_specs --brand siemens --category washing-machines
"""

import json
import re
import unicodedata
from typing import Optional

import httpx
from loguru import logger

from scrapers.base_scraper import fetch_soup

# ── Regional sitemap config ────────────────────────────────────────────────────

# (sitemap_url, model_pattern, wm_path_keywords)
_BOSCH_SITEMAPS = [
    ("https://www.bosch-home.co.uk/sitemap.xml",        r"bosch-home\.co\.uk"),
    ("https://www.bosch-home.com/de/sitemap.xml",        r"bosch-home\.com/de"),
    ("https://www.bosch-home.in/sitemap.xml",            r"bosch-home\.in"),
    ("https://www.bosch-home.com/it/sitemap.xml",        r"bosch-home\.com/it"),
    ("https://www.bosch-home.com/at/sitemap.xml",        r"bosch-home\.com/at"),
]

_SIEMENS_SITEMAPS = [
    ("https://www.siemens-home.bsh-group.com/uk/sitemap.xml", r"bsh-group\.com/uk"),
    ("https://www.siemens-home.bsh-group.com/de/sitemap.xml", r"bsh-group\.com/de"),
    ("https://www.siemens-home.bsh-group.com/in/sitemap.xml", r"bsh-group\.com/in"),
    ("https://www.siemens-home.bsh-group.com/it/sitemap.xml", r"bsh-group\.com/it"),
]

# WM path keywords per brand
_WM_PATH_KW = (
    "washing-machine", "washing-machines", "waschmaschine", "waschmaschinen",
    "washer-dryer", "wasch-trockner", "frontlader", "front-load", "built-in-wash",
    "washer-dryer",
)

# Model code pattern (Bosch/Siemens WM codes)
_MODEL_RE = re.compile(
    r"/(W[A-Z]{1,2}\d[A-Z0-9]{5,}[A-Z0-9])(?:[/?]|$)",
    re.IGNORECASE,
)

# In-process cache: brand → {model_upper: product_url}
_url_cache: dict[str, dict[str, str]] = {}

# ── BSH spec key → our DB column ───────────────────────────────────────────────

_BSH_KEY_MAP: dict[str, str] = {
    "RATED_CAPACITY_ECO_2017": "capacity_kg",
    "CAPACITY":                "capacity_kg",
    "RATED_CAPACITY":          "capacity_kg",
    "SPIN_MAX":                "spin_speed_rpm",
    "MAX_SPIN_SPEED":          "spin_speed_rpm",
    "ENERGY_CLASS_2017":       "energy_class",
    "ENERGY_CLASS":            "energy_class",
    "NOISE_SPIN":              "noise_spinning_db",
    "NOISE_CENTRIFUGE":        "noise_spinning_db",
    "ENERGY_CONSUMPTION_2017": "energy_consumption_kwh",
    "ENERGY_CONSUMPTION":      "energy_consumption_kwh",
    "ANNUAL_ENERGY":           "energy_consumption_kwh",
    "WATER_CONSUMPTION_2017":  "water_consumption_l",
    "WATER_CONSUMPTION":       "water_consumption_l",
    "ANNUAL_WATER":            "water_consumption_l",
    "DIM_WASHER":              "_dimensions",  # special: "WxHxD mm" string
    "DIMENSIONS":              "_dimensions",
    "PRODUCT_DIMENSION":       "_dimensions",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_float(s: str) -> Optional[float]:
    m = re.search(r"\d+(?:[.,]\d+)?", str(s).replace(",", "."))
    return float(m.group().replace(",", ".")) if m else None


def _safe_int(v: Optional[float]) -> Optional[int]:
    return None if v is None else int(round(v))


def _parse_dimensions(text: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse 'W x H x D mm' or '845x598x588' into (width, height, depth) in mm."""
    nums = re.findall(r"\d+(?:[.,]\d+)?", text)
    if len(nums) >= 3:
        vals = [_parse_float(n) for n in nums[:3]]
        result = []
        for v in vals:
            if v is None:
                result.append(None)
            elif v < 200:           # cm → mm
                result.append(round(v * 10))
            else:
                result.append(int(round(v)))
        return tuple(result)  # type: ignore[return-value]
    return None, None, None


# ── Sitemap cache building ─────────────────────────────────────────────────────

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _fetch_sitemap_locs(sitemap_url: str) -> list[str]:
    try:
        r = httpx.get(sitemap_url, headers={"User-Agent": _UA}, timeout=20, follow_redirects=True)
        r.raise_for_status()
        return re.findall(r"<loc>(https[^<]+)</loc>", r.text)
    except Exception as e:
        logger.debug(f"BSH sitemap fetch failed ({sitemap_url}): {e}")
        return []


def _build_cache(brand: str) -> dict[str, str]:
    if brand in _url_cache:
        return _url_cache[brand]

    sitemaps = _BOSCH_SITEMAPS if brand == "bosch" else _SIEMENS_SITEMAPS
    cache: dict[str, str] = {}

    for sitemap_url, _ in sitemaps:
        locs = _fetch_sitemap_locs(sitemap_url)
        wm_locs = [u for u in locs if any(kw in u.lower() for kw in _WM_PATH_KW)]
        added = 0
        for url in wm_locs:
            m = _MODEL_RE.search(url)
            if not m:
                continue
            model_key = m.group(1).upper()
            if model_key not in cache:
                cache[model_key] = url
            # Also index shorter prefixes (without trailing region code)
            for length in range(6, min(len(model_key), 10)):
                prefix = model_key[:length]
                if prefix not in cache:
                    cache[prefix] = url
            added += 1

        logger.debug(f"BSH {brand} sitemap {sitemap_url}: {len(wm_locs)} WM URLs → +{added} new keys")

    logger.info(f"BSH {brand} URL cache: {len(cache)} lookup keys")
    _url_cache[brand] = cache
    return cache


def _get_product_url(base_model: str, brand: str) -> Optional[str]:
    cache = _build_cache(brand)
    bm = base_model.upper()

    if bm in cache:
        return cache[bm]
    for code, url in cache.items():
        if code.startswith(bm) or bm.startswith(code):
            return url

    # Fallback: direct short URL (works for some newer models)
    if brand == "bosch":
        return f"https://www.bosch-home.co.uk/en/product/{base_model}"
    else:
        return f"https://www.siemens-home.bsh-group.com/uk/en/mkt-product/{base_model}"


# ── Spec extraction from BSH RSC payload ──────────────────────────────────────

def _extract_from_rsc(html: str) -> dict:
    """
    BSH pages embed full product data in the RSC payload as escaped JSON.
    The product object has a "specifications" array with groups of spec items.
    Each item: {"key":"SPIN_MAX","name":{"text":"..."},"value":{"text":"1400"},"unit":"rpm"}
    """
    # Locate the product.specifications data in the RSC payload
    # Pattern: \"specifications\":[{\"name\":
    idx = html.find('\\"specifications\\":[{\\"name\\"')
    if idx < 0:
        idx = html.find('"specifications":[{"name"')
    if idx < 0:
        return {}

    # Find the enclosing array by scanning for the matching bracket
    bracket_start = html.find("[", idx)
    if bracket_start < 0:
        return {}

    # Extract a large slice and try to parse the array
    # The array is double-escaped so we unescape \\" → " first
    chunk = html[bracket_start:bracket_start + 200_000]
    # Unescape: the RSC payload is inside a JSON string, so \" → "
    try:
        # Try to find the end of the JSON array
        # Walk until balanced brackets (accounting for escaping)
        depth = 0
        end = 0
        for i, ch in enumerate(chunk):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        raw = chunk[:end]
        # Unescape double-escaped JSON (RSC payload)
        unescaped = raw.replace('\\"', '"').replace("\\/", "/")
        spec_groups = json.loads(unescaped)
    except Exception:
        return {}

    return _parse_spec_groups(spec_groups)


def _parse_spec_groups(spec_groups: list) -> dict:
    """Parse BSH spec groups into our DB fields."""
    specs: dict = {}

    for group in spec_groups:
        if not isinstance(group, dict):
            continue
        items = group.get("specifications", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            bsh_key = item.get("key", "").upper()
            name_obj = item.get("name", {})
            val_obj = item.get("value", {})
            unit = item.get("unit") or ""
            value_text = str(val_obj.get("text", "") if isinstance(val_obj, dict) else val_obj).strip()

            if not value_text or value_text.lower() in ("null", "n/a", "-", ""):
                continue

            db_field = _BSH_KEY_MAP.get(bsh_key)
            if not db_field:
                continue

            if db_field == "capacity_kg":
                specs["capacity_kg"] = _parse_float(value_text)
            elif db_field == "spin_speed_rpm":
                specs["spin_speed_rpm"] = _safe_int(_parse_float(value_text))
            elif db_field == "energy_class":
                clean = value_text.strip().upper()
                if clean and clean[0].isalpha():
                    specs["energy_class"] = clean[:3]
            elif db_field == "noise_spinning_db":
                specs["noise_spinning_db"] = _parse_float(value_text)
            elif db_field == "energy_consumption_kwh":
                specs["energy_consumption_kwh"] = _parse_float(value_text)
            elif db_field == "water_consumption_l":
                specs["water_consumption_l"] = _parse_float(value_text)
            elif db_field == "_dimensions":
                w, h, d = _parse_dimensions(value_text)
                if w: specs["width_mm"]  = w
                if h: specs["height_mm"] = h
                if d: specs["depth_mm"]  = d

    return {k: v for k, v in specs.items() if v is not None}


def _extract_from_technical_overview(soup) -> dict:
    """
    Fallback: parse the server-rendered Technical Overview section.
    Items: <div data-testid="technical-overview-item">LABEL VALUE</div>
    """
    specs: dict = {}
    items = soup.find_all(attrs={"data-testid": "technical-overview-item"})
    for item in items:
        text = item.get_text(separator=" ", strip=True)

        # Dimensions: "Dimensions of the product 845x598x588 mm"
        if "dimension" in text.lower() or re.search(r"\d+x\d+x\d+", text):
            m = re.search(r"(\d+)\s*[x×]\s*(\d+)\s*[x×]\s*(\d+)", text)
            if m:
                w, h, d = _parse_dimensions(m.group(0))
                if w: specs["width_mm"]  = w
                if h: specs["height_mm"] = h
                if d: specs["depth_mm"]  = d

        # Capacity: "Rated capacity ... 10.0 kg"
        if "capacity" in text.lower() and "kg" in text.lower():
            m = re.search(r"(\d+(?:\.\d+)?)\s*kg", text, re.IGNORECASE)
            if m:
                specs["capacity_kg"] = float(m.group(1))

    # Spin speed from <p> tag
    for p in soup.find_all("p"):
        txt = p.get_text(strip=True)
        if "spin speed" in txt.lower() or "spin" in txt.lower() and "rpm" in txt.lower():
            m = re.search(r"(\d{3,4})\s*rpm", txt, re.IGNORECASE)
            if m:
                specs["spin_speed_rpm"] = int(m.group(1))

    # Energy class from energyLabel in RSC payload or JSON-LD
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            name = data.get("name", "")
            m = re.search(r"(\d+(?:\.\d+)?)\s*kg", name, re.IGNORECASE)
            if m and "capacity_kg" not in specs:
                specs["capacity_kg"] = float(m.group(1))
            m = re.search(r"(\d{3,4})\s*rpm", name, re.IGNORECASE)
            if m and "spin_speed_rpm" not in specs:
                specs["spin_speed_rpm"] = int(m.group(1))

    return {k: v for k, v in specs.items() if v is not None}


def _infer_door_type(soup) -> Optional[str]:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        name = (d.get("name") or "").lower()
        if "front loader" in name or "front-loader" in name:
            return "front"
        if "top loader" in name or "top-loader" in name:
            return "top"
    return None


# ── Main scrape function ───────────────────────────────────────────────────────

def scrape_model_specs(base_model: str, brand: str = "bosch") -> dict:
    """
    Scrape specs for a BSH (Bosch/Siemens) washing machine model.
    Returns a dict of populated spec fields.
    """
    product_url = _get_product_url(base_model, brand)
    if not product_url:
        logger.debug(f"  {base_model}: no URL found")
        return {}

    logger.debug(f"  {base_model}: {product_url}")

    try:
        # Use httpx directly to fast-fail on 4xx without tenacity retries
        r = httpx.get(product_url, headers={"User-Agent": _UA}, timeout=20, follow_redirects=True)
        if r.status_code >= 400:
            logger.debug(f"  {base_model}: HTTP {r.status_code}")
            return {}
        html = r.text
    except Exception as e:
        logger.debug(f"  {base_model}: fetch failed – {e}")
        return {}

    # 1. Try RSC payload extraction (most complete)
    specs = _extract_from_rsc(html)

    # 2. Fallback: parse technical overview HTML
    if not specs:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        specs = _extract_from_technical_overview(soup)

    # 3. Add door type
    if "door_type" not in specs:
        from bs4 import BeautifulSoup
        soup_for_door = BeautifulSoup(html, "html.parser") if not specs else None
        if soup_for_door is None:
            from bs4 import BeautifulSoup
            soup_for_door = BeautifulSoup(html, "html.parser")
        door = _infer_door_type(soup_for_door)
        if door:
            specs["door_type"] = door

    if specs:
        logger.debug(f"  {base_model}: {len(specs)} fields")

    return specs


# ── Brand-specific entry points ────────────────────────────────────────────────

def scrape_bosch_specs(base_model: str) -> dict:
    return scrape_model_specs(base_model, brand="bosch")


def scrape_siemens_specs(base_model: str) -> dict:
    return scrape_model_specs(base_model, brand="siemens")
