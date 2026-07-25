"""
scrapers/samsung_specs.py

Scrapes washing machine specifications for Samsung models from Samsung.com.

Source strategy:
  Samsung.com product pages are Next.js server-side rendered and embed spec
  data in <script id="__NEXT_DATA__"> JSON. We resolve product page URLs via
  Samsung's product sitemaps (XML, publicly accessible), which list all product
  URLs with the model code embedded in the slug.

  Regional coverage:
    - WW / WD prefix → Samsung UK  (samsung.com/uk)
    - WF / WA / WC  prefix → Samsung US  (samsung.com/us)

  Sitemap is fetched once per scraper run and cached in memory.

Rate limiting: base_scraper.fetch() adds 2 s + jitter between requests.
"""

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Optional

import httpx
from loguru import logger

from scrapers.base_scraper import fetch, fetch_soup

# ── Sitemap URLs ───────────────────────────────────────────────────────────────

# US: Next.js SSR, product sitemap lists all product URLs with -sku-{MODEL} pattern
SITEMAP_US = "https://www.samsung.com/us/us-pd-b2c-sitemap.xml"

# AEM regions: all use b2c-sitemap.xml → da-sitemap.xml with {model}-{region}/ pattern
SITEMAP_AEM = {
    "uk": "https://www.samsung.com/uk/b2c-sitemap.xml",
    "de": "https://www.samsung.com/de/b2c-sitemap.xml",
    "au": "https://www.samsung.com/au/b2c-sitemap.xml",
    "in": "https://www.samsung.com/in/b2c-sitemap.xml",
}

# Model prefix → regions to try, in priority order
_PREFIX_REGIONS: dict[str, list[str]] = {
    "WW": ["uk", "de", "au", "in"],   # Front-load EU/global
    "WD": ["uk", "de", "au"],         # Washer-dryer combos
    "WF": ["us", "au", "in"],         # Front-load US
    "WA": ["us", "au", "in"],         # Top-load US/Asia
    "WC": ["us"],                     # Compact US
}

# ── Samsung spec field name → our DB column ────────────────────────────────────

CAPACITY_KEYS = {
    # English
    "capacity", "drum capacity", "load capacity",
    "washer capacity", "tub capacity", "total capacity",
    "wash capacity", "washing capacity", "washing capacity (kg)",
    # German
    "kapazität", "nennkapazität", "füllmenge", "maximale beladungsmenge",
    "maximale beladungsmenge*",
}
SPIN_KEYS = {
    # English
    "spin speed", "max spin speed", "maximum spin speed",
    "centrifuge speed", "spin (rpm)", "max. spin speed",
    "max spin speed (rpm)",
    # German
    "max. schleuderdrehzahl (u/min.)", "schleuderdrehzahl",
    "maximale schleuderdrehzahl",
}
ENERGY_CLASS_KEYS = {
    # English
    "energy class", "energy rating", "eu energy class",
    "energy efficiency class", "energy efficiency rating",
    "energy efficiency",
    # German (the superscript chars get normalised away)
    "energieeffizienzklasse", "energieklasse", "energieeffizienz",
}
WIDTH_KEYS  = {"width", "net width", "product width", "net dimension w"}
HEIGHT_KEYS = {"height", "net height", "product height", "net dimension h"}
DEPTH_KEYS  = {"depth", "net depth", "product depth", "net dimension d"}
NOISE_SPIN_KEYS = {
    # English
    "noise level (spinning)", "spin noise", "noise while spinning",
    "noise level spin", "noise (spinning)", "noise level during spinning",
    "noise (centrifuge)", "spinning noise level", "noise level",
    # German
    "luftschallemissionen während des schleuderzyklus",
    "geräuschemission schleudern", "geräuschpegel schleudern",
    "schalldruckpegel schleudern",
}
ENERGY_KWH_KEYS = {
    # English
    "energy consumption", "annual energy consumption",
    "annual power consumption", "energy per year",
    "rated annual energy consumption",
    "energy consumption (100 cycles)",
    # German
    'gewichteter energieverbrauch „eco 40-60" **',
    "jahresenergieverbrauch", "jährlicher energieverbrauch",
}
WATER_KEYS = {
    # English
    "water consumption", "annual water consumption",
    "water usage", "water per year",
    "rated annual water consumption",
    "water consumption (cycle)",
    # German
    'gewichteter wasserverbrauch „eco 40-60" **',
    "jährlicher wasserverbrauch",
}
# Combined dimension fields (WxHxD) — both mm and cm values handled by sanity check
NET_DIM_KEYS = {
    # English
    "net dimension (wxhxd)", "net dimensions (wxhxd)", "dimensions (wxhxd)",
    "physical specification",
    # German — Samsung DE writes "B x H xT" without a space before T
    "abmessungen (b x h xt)", "abmessungen (b x h x t)",
    "nettogröße (b x h x t)", "nettogröße (b x h xt)",
}


def _normalise_key(s: str) -> str:
    # Strip Unicode superscripts/subscripts (category No) and combining marks
    # so "Energieeffizienzklasse ²" → "energieeffizienzklasse"
    cleaned = "".join(
        " " if unicodedata.category(c) in ("No", "Mn") else c
        for c in s
    )
    return re.sub(r"\s+", " ", cleaned.lower().strip())


def _parse_float(s: str) -> Optional[float]:
    m = re.search(r"[\d]+(?:[.,]\d+)?", str(s).replace(",", "."))
    return float(m.group().replace(",", ".")) if m else None


def _infer_door_type(model_code: str) -> Optional[str]:
    prefix = model_code[:2].upper()
    if prefix in {"WW", "WF", "WD"}:
        return "front"
    if prefix in {"WA", "WC"}:
        return "top"
    return None


# ── Spec extraction ────────────────────────────────────────────────────────────

def _extract_from_props(spec_list: list[dict]) -> dict:
    raw: dict[str, str] = {}
    for item in spec_list:
        if not isinstance(item, dict):
            continue
        key = _normalise_key(str(item.get("name") or item.get("title") or item.get("key") or ""))
        val = str(item.get("value") or item.get("spec") or item.get("val") or "").strip()
        if key and val and val.lower() not in ("-", "n/a", "na", "tbc", ""):
            raw[key] = val

    specs: dict = {}
    for k, v in raw.items():
        if k in CAPACITY_KEYS:
            specs["capacity_kg"] = _parse_float(v)
        elif k in SPIN_KEYS:
            specs["spin_speed_rpm"] = _parse_float(v)
        elif k in ENERGY_CLASS_KEYS:
            specs["energy_class"] = v.strip().upper()[:3]
        elif k in WIDTH_KEYS:
            specs["width_mm"] = _parse_float(v)
        elif k in HEIGHT_KEYS:
            specs["height_mm"] = _parse_float(v)
        elif k in DEPTH_KEYS:
            specs["depth_mm"] = _parse_float(v)
        elif k in NOISE_SPIN_KEYS:
            specs["noise_spinning_db"] = _parse_float(v)
        elif k in ENERGY_KWH_KEYS:
            specs["energy_consumption_kwh"] = _parse_float(v)
        elif k in WATER_KEYS:
            specs["water_consumption_l"] = _parse_float(v)
        elif k in NET_DIM_KEYS:
            # "600 x 850 x 600 mm" → width, height, depth
            nums = re.findall(r"\d+(?:[.,]\d+)?", v)
            if len(nums) >= 3:
                specs["width_mm"]  = _parse_float(nums[0])
                specs["height_mm"] = _parse_float(nums[1])
                specs["depth_mm"]  = _parse_float(nums[2])

    # Dimension sanity: Samsung sometimes gives cm; convert anything < 200 → mm
    # Cast all dimensions to int (DB columns are INTEGER)
    for dim in ("width_mm", "height_mm", "depth_mm"):
        v = specs.get(dim)
        if v is not None:
            specs[dim] = round(v * 10) if v < 200 else int(round(v))

    return {k: v for k, v in specs.items() if v is not None}


def _extract_from_next_data(soup) -> dict:
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not tag:
        return {}
    try:
        data = json.loads(tag.string or "")
    except (json.JSONDecodeError, TypeError):
        return {}

    candidates: list[list] = []

    def _dig(obj, depth=0):
        if depth > 14 or not isinstance(obj, (dict, list)):
            return
        if isinstance(obj, list) and len(obj) >= 3 and isinstance(obj[0], dict):
            if any(k in obj[0] for k in ("name", "title", "spec", "value", "key", "val")):
                candidates.append(obj)
        if isinstance(obj, dict):
            for v in obj.values():
                _dig(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _dig(item, depth + 1)

    _dig(data)

    best: dict = {}
    for candidate in candidates:
        extracted = _extract_from_props(candidate)
        if len(extracted) > len(best):
            best = extracted

    return best


def _extract_from_aem_html(soup) -> dict:
    """
    Extract specs from Samsung UK (AEM CMS) product pages.
    Spec labels/values are rendered in paired <p> tags with specific CSS classes.
    """
    titles = soup.find_all("p", class_="pdd32-product-spec__content-item-title")
    descs  = soup.find_all("p", class_="pdd32-product-spec__content-item-desc")
    if not titles or not descs:
        return {}
    spec_list = [
        {"name": t.get_text(strip=True), "value": d.get_text(strip=True)}
        for t, d in zip(titles, descs)
    ]
    return _extract_from_props(spec_list)


def _extract_from_jsonld(soup) -> dict:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue
        props = data.get("additionalProperty", [])
        extracted = _extract_from_props(props)
        if extracted:
            return extracted
    return {}


# ── Sitemap-based URL resolution ───────────────────────────────────────────────

def _fetch_sitemap_urls(sitemap_url: str, depth: int = 0) -> list[str]:
    """
    Fetch a sitemap (urlset or sitemapindex) and return all leaf URLs.
    Follows up to 2 levels of nesting.
    """
    if depth > 2:
        return []
    try:
        resp = fetch(sitemap_url)
        root = ET.fromstring(resp.text)
    except Exception as e:
        logger.debug(f"Sitemap fetch failed ({sitemap_url}): {e}")
        return []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    tag_name = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if tag_name == "sitemapindex":
        urls: list[str] = []
        for loc in root.findall(".//sm:loc", ns):
            sub = loc.text or ""
            if any(kw in sub for kw in ("da-", "ha-", "product", "pd-", "b2c", "laundry", "washing")):
                urls.extend(_fetch_sitemap_urls(sub, depth + 1))
        return urls
    else:
        return [loc.text for loc in root.findall(".//sm:loc", ns) if loc.text]


# Paths that identify washing machine product pages (not dishwashers or category pages)
_WM_PATHS = (
    "/washers-and-dryers/washing-machines/",
    "/washers-and-dryers/washer-dryer-combo/",
    "/washers-and-dryers/washer-dryers/",
    "/home-appliances/washers/",          # US path
    "/laundry/washers/",                  # US alternate path
    "/home-appliances/all-in-one-washer", # US combo
)

def _is_washer_url(url: str) -> bool:
    lo = url.lower()
    return any(p in lo for p in _WM_PATHS)


# In-process cache: {region: {model_key_upper: product_url}}
_url_cache: dict[str, dict[str, str]] = {}

# Samsung URL patterns for model code extraction:
#   US:  .../slug-sku-WA47CG3500AWA4/      → group 1 = full model+region code
#   AEM old: .../slug-ww10t684dln-s1/      → group 1 = model code, dash before region
#   AEM new: .../slug-wd90dg5b15bbeg/      → model+region concatenated, no dash
_SKU_RE  = re.compile(r"-sku-([a-z0-9]+)/?$", re.IGNORECASE)
_AEM_RE  = re.compile(
    r"[/-]((?:ww|wd|wf|wa|wc)[a-z0-9]{6,}?)(?:-[a-z0-9]{1,4})?/?$",
    re.IGNORECASE,
)


def _extract_model_key(url: str) -> Optional[str]:
    """
    Extract a Samsung model key from a product page URL.
    Returns the raw matched string (may include a regional suffix for new AEM URLs).
    We store multiple prefix lengths in the cache so lookup works regardless.
    """
    m = _SKU_RE.search(url)
    if m:
        return m.group(1).upper()
    m = _AEM_RE.search(url)
    if m:
        # Return full match including any trailing region chars;
        # prefix indexing in _build_url_cache handles the suffix.
        full = m.group(0).lstrip("/-").rstrip("/").upper()
        return full
    return None


def _build_url_cache(region: str) -> dict[str, str]:
    """
    Build model_key → URL mapping from Samsung's product sitemap for a given region.
    We store the URL keyed by the full extracted key AND all prefixes of length 8–14,
    so DB model codes (which may lack the regional suffix) still match.
    """
    if region in _url_cache:
        return _url_cache[region]

    sitemap = SITEMAP_US if region == "us" else SITEMAP_AEM[region]
    logger.info(f"Building Samsung {region.upper()} URL cache from sitemap …")

    all_urls = _fetch_sitemap_urls(sitemap)
    washer_urls = [u for u in all_urls if _is_washer_url(u)]

    cache: dict[str, str] = {}
    for url in washer_urls:
        key = _extract_model_key(url)
        if not key:
            continue
        cache[key] = url
        for length in range(8, min(len(key), 15)):
            prefix = key[:length]
            if prefix not in cache:
                cache[prefix] = url

    logger.info(f"Samsung {region.upper()} cache: {len(washer_urls)} washer pages → {len(cache)} lookup keys")
    _url_cache[region] = cache
    return cache


def _lookup_in_cache(bm: str, cache: dict[str, str]) -> Optional[str]:
    """Exact match, then prefix match in either direction."""
    url = cache.get(bm)
    if url:
        return url
    for code, u in cache.items():
        if code.startswith(bm) or bm.startswith(code):
            return u
    return None


def _get_product_url(base_model: str) -> Optional[str]:
    """
    Return the best Samsung.com product page URL for base_model.
    Tries region caches in priority order based on model prefix.
    """
    prefix = base_model[:2].upper()
    regions = _PREFIX_REGIONS.get(prefix, ["us"])
    bm = base_model.upper()
    for region in regions:
        cache = _build_url_cache(region)
        url = _lookup_in_cache(bm, cache)
        if url:
            return url
    return None


# ── Main scrape function ───────────────────────────────────────────────────────

def scrape_model_specs(base_model: str) -> dict:
    """
    Attempt to scrape specs for a Samsung washing machine model.
    Returns a dict of populated spec fields (only non-None values).
    """
    specs: dict = {}

    # 1. Door type from model code (instant, no network)
    door_type = _infer_door_type(base_model)
    if door_type:
        specs["door_type"] = door_type

    # 2. Resolve product page URL from sitemap cache
    product_url = _get_product_url(base_model)
    if not product_url:
        logger.debug(f"  {base_model}: not in sitemap cache")
        return specs

    logger.debug(f"  {base_model}: {product_url}")

    # 3. Fetch product page
    try:
        soup = fetch_soup(product_url)
    except Exception as e:
        logger.debug(f"  {base_model}: page fetch failed – {e}")
        return specs

    # 4. Extract specs: __NEXT_DATA__ (US/Next.js), AEM HTML (UK), then JSON-LD fallback
    extracted = _extract_from_next_data(soup)
    if not extracted:
        extracted = _extract_from_aem_html(soup)
    if not extracted:
        extracted = _extract_from_jsonld(soup)

    specs.update(extracted)
    return specs
