from datetime import date

from pipeline.applicability_resolver import (
    ApplicabilityRule,
    EngineContext,
    resolve_applicability,
)


CONTEXT = EngineContext(
    category_id=1,
    brand_id=10,
    product_line_id=20,
    engine_model_id=30,
    engine_generation_id=40,
    model_variant_id=50,
    model_year=2024,
    production_date=date(2023, 9, 1),
    market_code="EU",
)


def test_more_specific_inclusion_wins():
    result = resolve_applicability(
        [
            ApplicabilityRule(1, "brand", 10),
            ApplicabilityRule(2, "engine_generation", 40),
            ApplicabilityRule(3, "engine_model", 30),
        ],
        CONTEXT,
    )
    assert result.applies is True
    assert result.winning_rule_id == 2
    assert result.specificity == 5
    assert result.reason == "matched_most_specific_inclusion"


def test_matching_exclusion_is_subtracted_after_inclusions():
    result = resolve_applicability(
        [
            ApplicabilityRule(1, "engine_generation", 40),
            ApplicabilityRule(
                2,
                "model_variant",
                50,
                is_exclusion=True,
                model_year_start=2024,
                model_year_end=2024,
            ),
        ],
        CONTEXT,
    )
    assert result.applies is False
    assert result.exclusion_rule_id == 2
    assert result.reason == "excluded_by_matching_rule"


def test_rule_refinements_are_anded():
    wrong_market = ApplicabilityRule(
        1, "engine_generation", 40, model_year_start=2020, model_year_end=2025, market_code="US"
    )
    assert resolve_applicability([wrong_market], CONTEXT).applies is False


def test_missing_market_does_not_match_market_specific_rule():
    context = EngineContext(category_id=1, brand_id=10, engine_model_id=30)
    rule = ApplicabilityRule(1, "engine_model", 30, market_code="EU")
    assert resolve_applicability([rule], context).applies is False


def test_open_year_range_matches():
    rule = ApplicabilityRule(1, "engine_model", 30, model_year_start=2020)
    assert resolve_applicability([rule], CONTEXT).applies is True


def test_serial_boundaries_respect_inclusivity():
    context = EngineContext(
        category_id=1,
        brand_id=10,
        engine_model_id=30,
        serial_scheme_id=7,
        serial_normalized="00100",
    )
    exclusive = ApplicabilityRule(
        1,
        "engine_model",
        30,
        serial_scheme_id=7,
        serial_start_normalized="00100",
        serial_end_normalized="00200",
        range_start_inclusive=False,
    )
    inclusive = ApplicabilityRule(
        2,
        "engine_model",
        30,
        serial_scheme_id=7,
        serial_start_normalized="00100",
        serial_end_normalized="00200",
    )
    assert resolve_applicability([exclusive], context).applies is False
    assert resolve_applicability([inclusive], context).applies is True


def test_every_catalog_specificity_level_matches():
    targets = {
        "global": None,
        "category": 1,
        "brand": 10,
        "product_line": 20,
        "engine_model": 30,
        "engine_generation": 40,
        "model_variant": 50,
    }
    for target_type, target_id in targets.items():
        result = resolve_applicability(
            [ApplicabilityRule(1, target_type, target_id)], CONTEXT
        )
        assert result.applies is True, target_type


def test_disjoint_ranges_are_a_union():
    rules = [
        ApplicabilityRule(1, "engine_model", 30, model_year_start=2010, model_year_end=2015),
        ApplicabilityRule(2, "engine_model", 30, model_year_start=2020, model_year_end=2025),
    ]
    # Only one disjoint range matches, so the result is unambiguous.
    assert resolve_applicability(rules, CONTEXT).winning_rule_id == 2


def test_model_year_and_production_date_boundaries_are_inclusive():
    rule = ApplicabilityRule(
        1,
        "engine_generation",
        40,
        model_year_start=2024,
        model_year_end=2024,
        production_date_start=date(2023, 9, 1),
        production_date_end=date(2023, 9, 1),
    )
    assert resolve_applicability([rule], CONTEXT).applies is True


def test_open_production_date_range_matches():
    rule = ApplicabilityRule(
        1, "engine_generation", 40, production_date_start=date(2020, 1, 1)
    )
    assert resolve_applicability([rule], CONTEXT).applies is True


def test_same_specificity_overlap_fails_safely():
    result = resolve_applicability(
        [
            ApplicabilityRule(8, "engine_model", 30, model_year_start=2020),
            ApplicabilityRule(3, "engine_model", 30, model_year_end=2025),
        ],
        CONTEXT,
    )
    assert result.applies is False
    assert result.reason == "ambiguous_same_specificity"
    assert result.ambiguous_rule_ids == (3, 8)


def test_serial_prefix_and_scheme_must_match():
    context = EngineContext(
        category_id=1,
        brand_id=10,
        engine_model_id=30,
        serial_scheme_id=7,
        serial_prefix="EU",
        serial_normalized="00100",
    )
    rule = ApplicabilityRule(
        1,
        "engine_model",
        30,
        serial_scheme_id=7,
        serial_prefix="US",
        serial_start_normalized="00001",
        serial_end_normalized="99999",
    )
    assert resolve_applicability([rule], context).applies is False


def test_incompatible_serial_scheme_is_rejected():
    context = EngineContext(
        category_id=1,
        brand_id=10,
        engine_model_id=30,
        serial_scheme_id=8,
        serial_normalized="00100",
    )
    rule = ApplicabilityRule(
        1, "engine_model", 30, serial_scheme_id=7, serial_start_normalized="00001"
    )
    assert resolve_applicability([rule], context).applies is False


def test_unparseable_serial_fails_safely():
    context = EngineContext(
        category_id=1,
        brand_id=10,
        engine_model_id=30,
        serial_scheme_id=7,
        serial_normalized=None,
    )
    rule = ApplicabilityRule(1, "engine_model", 30, serial_scheme_id=7)
    result = resolve_applicability([rule], context)
    assert result.applies is False
    assert result.reason == "serial_unparseable"


def test_leading_zeroes_are_compared_as_normalized_text():
    context = EngineContext(
        category_id=1,
        brand_id=10,
        engine_model_id=30,
        serial_scheme_id=7,
        serial_normalized="00010",
    )
    rule = ApplicabilityRule(
        1,
        "engine_model",
        30,
        serial_scheme_id=7,
        serial_start_normalized="00002",
        serial_end_normalized="00100",
    )
    assert resolve_applicability([rule], context).applies is True
