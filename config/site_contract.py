"""Validation for the repository's frontend-neutral site starter contract."""

from __future__ import annotations

import re


SITE_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
DOMAIN_RE = re.compile(r"^[a-z0-9.-]+$")
LOCALE_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")


def validate_site_contract(contract: dict) -> dict:
    required = {"site_id", "name", "domain", "vertical_key", "default_locale", "locales", "routes", "design_tokens"}
    missing = sorted(required - contract.keys())
    if missing:
        raise ValueError(f"missing site contract fields: {', '.join(missing)}")
    if not SITE_ID_RE.fullmatch(contract["site_id"]):
        raise ValueError("invalid site_id")
    if not DOMAIN_RE.fullmatch(contract["domain"]):
        raise ValueError("invalid domain")
    locales = contract["locales"]
    if not isinstance(locales, list) or not locales or len(locales) != len(set(locales)):
        raise ValueError("locales must be a non-empty unique list")
    if any(not LOCALE_RE.fullmatch(locale) for locale in locales):
        raise ValueError("invalid locale")
    if contract["default_locale"] not in locales:
        raise ValueError("default_locale must be enabled")
    routes = contract["routes"]
    if set(routes) != {"model", "guide"}:
        raise ValueError("routes must define exactly model and guide")
    for route in routes.values():
        if not route.startswith("/") or not route.endswith("/") or "{" not in route:
            raise ValueError("route templates must be absolute, parameterized and trailing-slash")
    tokens = contract["design_tokens"]
    if not isinstance(tokens, dict) or not {"brand_name", "primary_color"} <= tokens.keys():
        raise ValueError("design_tokens require brand_name and primary_color")
    return contract

