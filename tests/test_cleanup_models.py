"""
tests/test_cleanup_models.py

Unit tests for the pure functions in pipeline/cleanup_models.py.
No DB connection required — these test only the data-transformation logic.
"""

import pytest
from pipeline.cleanup_models import (
    normalize_model_name,
    expand_slash_variants,
    junk_reason,
    model_family,
    pick_canonical,
)


# ── normalize_model_name ──────────────────────────────────────────────────────

class TestNormalizeModelName:
    def test_strips_series_suffix(self):
        assert normalize_model_name("WF45T6000A Series") == "WF45T6000A"
        assert normalize_model_name("WF45T6000A series") == "WF45T6000A"

    def test_strips_number_series_suffix(self):
        assert normalize_model_name("WW80T Series") == "WW80T"
        assert normalize_model_name("5 Series") == "5"  # no real prefix → stripped; caught by junk_reason

    def test_strips_designation_words(self):
        assert normalize_model_name("VRT STEAM WF419AAW") == "WF419AAW"
        assert normalize_model_name("ECOBUBBLE WW90T986DSH") == "WW90T986DSH"
        assert normalize_model_name("AddWash WF45T6000AW") == "WF45T6000AW"
        assert normalize_model_name("BESPOKE WF45DB8900HA") == "WF45DB8900HA"

    def test_preserves_normal_names(self):
        assert normalize_model_name("WF45T6000AW") == "WF45T6000AW"
        assert normalize_model_name("WW90T986DSH/EN") == "WW90T986DSH/EN"

    def test_strips_firmware_revision(self):
        assert normalize_model_name("WF45T6000AW/A5-00") == "WF45T6000AW"
        assert normalize_model_name("WF45T6000AW/A5-01") == "WF45T6000AW"

    def test_normalises_flexwash_casing(self):
        assert normalize_model_name("FLEXWASH WV55M9600AW") == "FlexWash WV55M9600AW"
        assert normalize_model_name("flexwash WV55M9600AW") == "FlexWash WV55M9600AW"

    def test_strips_whitespace(self):
        assert normalize_model_name("  WF45T6000AW  ") == "WF45T6000AW"


# ── expand_slash_variants ─────────────────────────────────────────────────────

class TestExpandSlashVariants:
    def test_expands_variants(self):
        assert expand_slash_variants("Q1657(T/S/V)") == ["Q1657T", "Q1657S", "Q1657V"]
        assert expand_slash_variants("B1045(V/S/C)") == ["B1045V", "B1045S", "B1045C"]

    def test_expands_with_letter_before_parens(self):
        assert expand_slash_variants("Q1657A(V/T/S)") == ["Q1657AV", "Q1657AT", "Q1657AS"]

    def test_no_expansion_for_plain_name(self):
        assert expand_slash_variants("WF419AAW") == []
        assert expand_slash_variants("WW90T986DSH/EN") == []

    def test_no_expansion_for_empty(self):
        assert expand_slash_variants("") == []

    def test_three_variants(self):
        result = expand_slash_variants("B1075(V/S/C)")
        assert set(result) == {"B1075V", "B1075S", "B1075C"}


# ── junk_reason ───────────────────────────────────────────────────────────────

class TestJunkReason:
    def test_starts_with_paren(self):
        assert junk_reason(")WF45T") is not None

    def test_bare_number_code(self):
        assert junk_reason("12345") is not None
        assert junk_reason("123A") is not None

    def test_number_series(self):
        assert junk_reason("5 Series") is not None
        assert junk_reason("7 series") is not None

    def test_part_number_pattern(self):
        assert junk_reason("592-12345") is not None

    def test_wrong_product(self):
        assert junk_reason("SyncMaster 940BW") is not None

    def test_too_short(self):
        assert junk_reason("A1") is not None
        assert junk_reason("B2") is not None

    def test_three_digit_fragment(self):
        assert junk_reason("W123") is not None
        assert junk_reason("P456") is not None

    def test_valid_models_are_not_junk(self):
        assert junk_reason("WF45T6000AW") is None
        assert junk_reason("WW90T986DSH/EN") is None
        assert junk_reason("B1075C") is None
        assert junk_reason("Q1044") is None


# ── model_family ──────────────────────────────────────────────────────────────

class TestModelFamily:
    def test_strips_market_suffix(self):
        assert model_family("WW90T986DSH/EN") == "WW90T986DSH"
        assert model_family("WF45T6000AW/A4") == "WF45T6000A"

    def test_old_samsung_letter_4digit(self):
        assert model_family("B1075C") == "B1075"
        assert model_family("B1075S") == "B1075"
        assert model_family("B1075V") == "B1075"

    def test_old_samsung_with_base_letter(self):
        assert model_family("B1445AS") == "B1445A"
        assert model_family("B1445AV") == "B1445A"
        assert model_family("B1445A") == "B1445A"

    def test_new_samsung_lg_style(self):
        # WF45T6000AW → strip 1-char colour suffix W → WF45T6000A
        assert model_family("WF45T6000AW") == "WF45T6000A"
        assert model_family("WF45T6000AV") == "WF45T6000A"

    def test_qfj_series(self):
        assert model_family("Q1044C") == "Q1044"
        assert model_family("Q1044S") == "Q1044"
        assert model_family("F1044") == "F1044"

    def test_strips_series_word(self):
        assert model_family("WF45T6000A Series") == "WF45T6000A"

    def test_strips_variant_spec(self):
        assert model_family("Q1657(T/S/V)") == "Q1657"


# ── pick_canonical ────────────────────────────────────────────────────────────

class TestPickCanonical:
    def _row(self, name):
        return {"id": hash(name), "name": name, "slug": name.lower(), "manual_pdf_url": None}

    def test_prefers_series_name(self):
        models = [
            self._row("WF45T6000AW"),
            self._row("WF45T6000A Series"),
            self._row("WF45T6000AV"),
        ]
        canonical = pick_canonical(models, "Samsung-WF45T6000A.html")
        assert canonical["name"] == "WF45T6000A Series"

    def test_prefers_shortest_when_no_series(self):
        models = [
            self._row("WF45T6000AW"),
            self._row("WF45T6000AWRG"),
            self._row("WF45T6000AV"),
        ]
        canonical = pick_canonical(models, "Samsung-WF45T6000A.html")
        # No "Series" → pick by PDF stem match + shortest; WF45T6000AW is shortest
        assert canonical["name"] in ("WF45T6000AW", "WF45T6000AV")

    def test_single_member(self):
        models = [self._row("WF45T6000AW")]
        assert pick_canonical(models, "")["name"] == "WF45T6000AW"
