"""
scrapers/electrolux_specs.py

Scrapes washing machine specifications for Electrolux models.

URL strategy:
  Build a model_slug → URL cache from category listing pages on multiple
  regional Electrolux Next.js sites (UK, FR, SE). The listing pages embed
  all product URLs in __NEXT_DATA__, giving us the full path including the
  description slug required by the router.

  Listing pages crawled:
    https://www.electrolux.co.uk/laundry/laundry/washing-machines/
    https://www.electrolux.co.uk/laundry/laundry/washer-dryers/
    https://www.electrolux.fr/laundry/laundry/washing-machines/
    https://www.electrolux.fr/laundry/laundry/washer-dryers/
    https://www.electrolux.se/laundry/laundry/washing-machines/

  Product pages embed spec data in __NEXT_DATA__ as {label, infoText} pairs.

Usage (via scrape_specs.py):
    python -m pipeline.scrape_specs --brand electrolux --category washing-machines
"""

import json
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

# ── Regional listing page config ───────────────────────────────────────────────

_LISTING_PAGES = [
    ("https://www.electrolux.co.uk", "/laundry/laundry/washing-machines/"),
    ("https://www.electrolux.co.uk", "/laundry/laundry/washer-dryers/"),
    ("https://www.electrolux.fr",    "/laundry/laundry/washing-machines/"),
    ("https://www.electrolux.fr",    "/laundry/laundry/washer-dryers/"),
    ("https://www.electrolux.se",    "/laundry/laundry/washing-machines/"),
]

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# In-process cache: model_code_upper → product_url
_url_cache: Optional[dict[str, str]] = None

# ── Label → DB column mapping ──────────────────────────────────────────────────

_LABEL_MAP: dict[str, str] = {}

_CAPACITY_LABELS = {
    # English
    "full load capacity (kg)", "washing capacity (kg)", "capacity (kg)",
    "load capacity", "drum capacity", "rated capacity",
    # French
    "capacité maximum du tambour (kg)", "capacité maxi du tambour (kg)",
    "capacit\u00e9 maximum du tambour (kg)", "capacit\u00e9 maxi du tambour (kg)",
    # Swedish
    "kapacitet (kg)", "kapacitet kg, full maskin eco 40-60",
}
_SPIN_LABELS = {
    # English
    "max spin speed (rpm)", "max spin speed", "maximum spin speed",
    "max. spin speed", "spin speed",
    # French
    "vitesse d'essorage (tr/min)", "vitesse d'essorage maxi (tr/mn)",
    "vitesse d\u2019essorage (tr/min)", "vitesse d\u2019essorage maxi (tr/mn)",
    # Swedish
    "centrifugeringhastighet", "max centrifugering, v/m",
}
_ENERGY_CLASS_LABELS = {
    # English
    "energy class", "energy rating", "energy efficiency class",
    "eu energy class", "energy label", "energy efficiency rating",
    # Swedish
    "energiklass",
}
_NOISE_SPIN_LABELS = {
    # English
    "noise level, db(a)  (eu 2017/1369)", "noise level (spinning)",
    "noise (spinning)", "spin noise", "noise during spinning",
    "noise level spin", "noise level (db(a)) re 1 pw (spinning)",
    "noise level (db)",
    # French
    "niveau sonore (db)",
    # Swedish
    "ljudniv\u00e5 (db)", "ljudniva (db)",
}
_ENERGY_KWH_LABELS = {
    # English
    "energy consumption per 100 wash cycles (kwh)",
    "energy consumption", "annual energy consumption",
    "rated annual energy consumption", "energy per cycle",
    # French
    "consommation en \u00e9lectricit\u00e9 en kwh/100 cycles",
    "consommation en electricite en kwh/100 cycles",
    # Swedish
    "energif\u00f6rbrukning kwh/100 cykler", "energiforbrukning kwh/100 cykler",
}
_WATER_LABELS = {
    # English
    "water consumption", "annual water consumption",
    "rated annual water consumption",
    "water consumption per 100 full load cycles (litres)",
    # French
    "consommation en eau en litres/cycle",
    # Swedish
    "vattenf\u00f6rbrukning per tv\u00e4ttkol, l",
    "vattenforbrukning per tvattkol, l",
    "vattenf\u00f6rbrukning per tv\u00e4ttcykel, l",
}
_WIDTH_LABELS  = {"width (mm)", "width", "net width", "product width"}
_HEIGHT_LABELS = {"height (mm)", "height", "net height", "product height"}
_DEPTH_LABELS  = {
    "depth (mm)", "depth max (mm)", "depth", "net depth", "product depth",
    # Swedish
    "djup (mm)", "max djup, mm",
}
_DIM_LABELS    = {
    # English
    "dimensions (mm) (hxwxd)", "dimensions (mm) (wxhxd)",
    "dimensions", "net dimensions", "product dimensions",
    # French — HxLxP = Height×Width(Largeur)×Depth(Profondeur)
    "dimensions hxlxp (mm)",
    # Swedish — H x B x D = Height×Width(Bredd)×Depth(Djup)
    "produktm\u00e5tt h x b x d, mm", "produktmatt h x b x d, mm",
}


def _parse_float(s: str) -> Optional[float]:
    m = re.search(r"\d+(?:[.,]\d+)?", str(s).replace(",", "."))
    return float(m.group().replace(",", ".")) if m else None


def _parse_dimensions_hxwxd(text: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse 'HxWxD' or 'WxHxD' string into (width, height, depth) mm."""
    nums = re.findall(r"\d+(?:[.,]\d+)?", text)
    if len(nums) >= 3:
        vals = [_parse_float(n) for n in nums[:3]]
        h, w, d = vals[0], vals[1], vals[2]
        # Convert cm → mm if suspiciously small
        result = []
        for v in (w, h, d):
            if v is None:
                result.append(None)
            elif v < 200:
                result.append(round(v * 10))
            else:
                result.append(int(round(v)))
        return tuple(result)  # type: ignore[return-value]
    return None, None, None


# ── Listing-page URL cache ─────────────────────────────────────────────────────

def _extract_product_paths(base: str, html: str) -> dict[str, str]:
    """
    Extract model_slug → full_url from a Next.js listing page __NEXT_DATA__.
    URL pattern: /laundry/.../washing-machines/{desc-slug}/{model-slug}/
    """
    soup = BeautifulSoup(html, "html.parser")
    nd = soup.find("script", {"id": "__NEXT_DATA__"})
    if not nd:
        return {}
    try:
        text = json.dumps(json.loads(nd.string or ""))
    except (json.JSONDecodeError, TypeError):
        return {}

    # Match paths that end with a model-like slug (alphanumeric, 4+ chars)
    paths = re.findall(r'(/(?:laundry|lave-linge|tvatt)[^"\']{4,}/([a-z0-9]{4,})/)(?:[,"])', text)
    result: dict[str, str] = {}
    for path, slug in paths:
        model_key = slug.upper()
        if model_key not in result:
            result[model_key] = base + path
    return result


def _build_url_cache() -> dict[str, str]:
    global _url_cache
    if _url_cache is not None:
        return _url_cache

    cache: dict[str, str] = {}

    for base, path in _LISTING_PAGES:
        url = base + path
        try:
            r = httpx.get(url, headers={"User-Agent": _UA}, timeout=15, follow_redirects=True)
            if r.status_code != 200:
                logger.debug(f"Electrolux listing {url}: HTTP {r.status_code}")
                continue
            extracted = _extract_product_paths(base, r.text)
            new_keys = {k: v for k, v in extracted.items() if k not in cache}
            cache.update(new_keys)
            logger.debug(f"Electrolux listing {url}: {len(extracted)} products → +{len(new_keys)} new keys")
        except Exception as e:
            logger.debug(f"Electrolux listing fetch failed ({url}): {e}")

    logger.info(f"Electrolux URL cache: {len(cache)} lookup keys")
    _url_cache = cache
    return cache


def _get_product_url(base_model: str) -> Optional[str]:
    cache = _build_url_cache()
    bm = base_model.upper()

    if bm in cache:
        return cache[bm]
    # Prefix match (handles minor suffix variants)
    for code, url in cache.items():
        if code.startswith(bm) or bm.startswith(code):
            return url

    return None


# ── Spec extraction ────────────────────────────────────────────────────────────

def _extract_specs(soup) -> dict:
    """
    Extract specs from Electrolux UK/EU Next.js product page.
    Spec data is in __NEXT_DATA__ as {label, infoText} pairs.
    """
    nd = soup.find("script", {"id": "__NEXT_DATA__"})
    if not nd:
        return {}
    try:
        text = nd.string or ""
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}

    # Find all {label, infoText} pairs anywhere in the data
    raw_json = json.dumps(data)
    pairs = re.findall(
        r'\{"label"\s*:\s*"([^"]+)"\s*,\s*"infoText"\s*:\s*"([^"]+)"\}',
        raw_json,
    )
    # Also handle reversed key order
    pairs += re.findall(
        r'\{"infoText"\s*:\s*"([^"]+)"\s*,\s*"label"\s*:\s*"([^"]+)"\}',
        raw_json,
    )

    raw: dict[str, str] = {}
    for label, val in pairs:
        key = label.lower().strip()
        if key and val and val.lower() not in ("-", "n/a", "na", "tbc", ""):
            raw[key] = val

    # Reversed-order pairs have (infoText, label) swapped — fix them
    pairs_rev = re.findall(
        r'\{"infoText"\s*:\s*"([^"]+)"\s*,\s*"label"\s*:\s*"([^"]+)"\}',
        raw_json,
    )
    for val, label in pairs_rev:
        key = label.lower().strip()
        if key and val and val.lower() not in ("-", "n/a", "na", "tbc", ""):
            raw[key] = val

    specs: dict = {}
    for k, v in raw.items():
        if k in _CAPACITY_LABELS:
            specs["capacity_kg"] = _parse_float(v)
        elif k in _SPIN_LABELS:
            specs["spin_speed_rpm"] = _parse_float(v)
        elif k in _ENERGY_CLASS_LABELS:
            clean = v.strip().upper()
            if clean and clean[0].isalpha():
                specs["energy_class"] = clean[:3]
        elif k in _NOISE_SPIN_LABELS:
            specs["noise_spinning_db"] = _parse_float(v)
        elif k in _ENERGY_KWH_LABELS:
            specs["energy_consumption_kwh"] = _parse_float(v)
        elif k in _WATER_LABELS:
            specs["water_consumption_l"] = _parse_float(v)
        elif k in _WIDTH_LABELS:
            val_f = _parse_float(v)
            if val_f:
                specs["width_mm"] = round(val_f * 10) if val_f < 200 else int(round(val_f))
        elif k in _HEIGHT_LABELS:
            val_f = _parse_float(v)
            if val_f:
                specs["height_mm"] = round(val_f * 10) if val_f < 200 else int(round(val_f))
        elif k in _DEPTH_LABELS:
            val_f = _parse_float(v)
            if val_f:
                specs["depth_mm"] = round(val_f * 10) if val_f < 200 else int(round(val_f))
        elif k in _DIM_LABELS:
            # HxWxD or WxHxD — parse as H, W, D
            nums = re.findall(r"\d+", v)
            if len(nums) >= 3:
                h, w, d = int(nums[0]), int(nums[1]), int(nums[2])
                # Dimensions (mm) (HxWxD): first=H, second=W, third=D
                specs["height_mm"] = h
                specs["width_mm"]  = w
                specs["depth_mm"]  = d

    # Infer door type
    door = _infer_door_type(soup)
    if door:
        specs["door_type"] = door

    return {k: v for k, v in specs.items() if v is not None}


def _infer_door_type(soup) -> Optional[str]:
    text = soup.get_text(" ", strip=True).lower()
    if "top loader" in text or "top-loader" in text:
        return "top"
    if "front loader" in text or "front-loader" in text:
        return "front"
    return None


# ── Main scrape function ───────────────────────────────────────────────────────

def scrape_model_specs(base_model: str) -> dict:
    """
    Attempt to scrape specs for an Electrolux washing machine model.
    Returns a dict of populated spec fields.
    """
    # Skip obviously non-Electrolux model names
    if " " in base_model and not base_model[:4].isalpha():
        logger.debug(f"  {base_model}: skipping (not an Electrolux model code)")
        return {}

    product_url = _get_product_url(base_model)
    if not product_url:
        logger.debug(f"  {base_model}: no URL found in cache")
        return {}

    logger.debug(f"  {base_model}: {product_url}")

    try:
        r = httpx.get(product_url, headers={"User-Agent": _UA}, timeout=15, follow_redirects=True)
        if r.status_code >= 400:
            logger.debug(f"  {base_model}: HTTP {r.status_code}")
            return {}
        html = r.text
    except Exception as e:
        logger.debug(f"  {base_model}: fetch failed – {e}")
        return {}

    soup = BeautifulSoup(html, "html.parser")

    # Check for 404 page
    title = soup.find("title")
    if title and ("404" in title.get_text() or "not found" in title.get_text().lower()):
        logger.debug(f"  {base_model}: 404 page at {product_url}")
        return {}

    specs = _extract_specs(soup)
    if specs:
        logger.debug(f"  {base_model}: {len(specs)} fields")
    return specs
