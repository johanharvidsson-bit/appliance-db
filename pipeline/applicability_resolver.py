"""Deterministic in-memory applicability evaluation for RepairBase.

The production query layer can use SQL for candidate selection, but this pure
reference implementation defines and tests the required semantics:
inclusions form a union, refinements inside a rule are ANDed, then exclusions
are subtracted. The most specific matching inclusion determines precedence.
"""

from dataclasses import dataclass
from datetime import date
from typing import Iterable


SPECIFICITY = {
    "global": 0,
    "category": 1,
    "brand": 2,
    "product_line": 3,
    "engine_model": 4,
    "engine_generation": 5,
    "model_variant": 6,
}


@dataclass(frozen=True)
class EngineContext:
    category_id: int
    brand_id: int
    product_line_id: int | None = None
    engine_model_id: int | None = None
    engine_generation_id: int | None = None
    model_variant_id: int | None = None
    model_year: int | None = None
    production_date: date | None = None
    market_code: str | None = None
    serial_scheme_id: int | None = None
    serial_prefix: str | None = None
    serial_normalized: str | None = None


@dataclass(frozen=True)
class ApplicabilityRule:
    rule_id: int
    target_type: str
    target_id: int | None
    is_exclusion: bool = False
    model_year_start: int | None = None
    model_year_end: int | None = None
    production_date_start: date | None = None
    production_date_end: date | None = None
    market_code: str | None = None
    serial_scheme_id: int | None = None
    serial_prefix: str | None = None
    serial_start_normalized: str | None = None
    serial_end_normalized: str | None = None
    range_start_inclusive: bool = True
    range_end_inclusive: bool = True

    @property
    def specificity(self) -> int:
        return SPECIFICITY[self.target_type]


@dataclass(frozen=True)
class ApplicabilityResult:
    applies: bool
    winning_rule_id: int | None
    specificity: int | None
    exclusion_rule_id: int | None = None
    reason: str = "no_matching_inclusion"
    ambiguous_rule_ids: tuple[int, ...] = ()


def _within(value, start, end, start_inclusive=True, end_inclusive=True) -> bool:
    if value is None:
        return start is None and end is None
    if start is not None and (value < start or (value == start and not start_inclusive)):
        return False
    if end is not None and (value > end or (value == end and not end_inclusive)):
        return False
    return True


def _evaluate_rule(rule: ApplicabilityRule, context: EngineContext) -> tuple[bool, str]:
    if rule.target_type == "global":
        target_matches = True
    else:
        target_matches = getattr(context, f"{rule.target_type}_id") == rule.target_id
    if not target_matches:
        return False, "target_mismatch"
    if not _within(context.model_year, rule.model_year_start, rule.model_year_end):
        return False, "model_year_mismatch"
    if not _within(context.production_date, rule.production_date_start, rule.production_date_end):
        return False, "production_date_mismatch"
    if rule.market_code is not None and context.market_code != rule.market_code:
        return False, "market_mismatch"
    if rule.serial_scheme_id is not None:
        if context.serial_scheme_id != rule.serial_scheme_id:
            return False, "serial_scheme_mismatch"
        if rule.serial_prefix is not None and context.serial_prefix != rule.serial_prefix:
            return False, "serial_prefix_mismatch"
        # Normalization/parsing happens in the serial-scheme parser before this
        # resolver. A missing normalized value is never guessed or coerced.
        if context.serial_normalized is None:
            return False, "serial_unparseable"
        if not _within(
            context.serial_normalized,
            rule.serial_start_normalized,
            rule.serial_end_normalized,
            rule.range_start_inclusive,
            rule.range_end_inclusive,
        ):
            return False, "serial_range_mismatch"
    return True, "matched"


def rule_matches(rule: ApplicabilityRule, context: EngineContext) -> bool:
    """Compatibility wrapper for callers that only need a boolean match."""
    return _evaluate_rule(rule, context)[0]


def resolve_applicability(
    rules: Iterable[ApplicabilityRule], context: EngineContext
) -> ApplicabilityResult:
    evaluations = [(rule, *_evaluate_rule(rule, context)) for rule in rules]
    matches = [rule for rule, matched, _ in evaluations if matched]
    exclusions = [rule for rule in matches if rule.is_exclusion]
    if exclusions:
        winner = max(exclusions, key=lambda rule: (rule.specificity, -rule.rule_id))
        return ApplicabilityResult(
            False,
            None,
            None,
            winner.rule_id,
            reason="excluded_by_matching_rule",
        )

    inclusions = [rule for rule in matches if not rule.is_exclusion]
    if not inclusions:
        mismatch_reasons = {
            reason
            for rule, matched, reason in evaluations
            if not rule.is_exclusion and not matched
        }
        reason = (
            "serial_unparseable"
            if "serial_unparseable" in mismatch_reasons
            else "no_matching_inclusion"
        )
        return ApplicabilityResult(False, None, None, reason=reason)

    top_specificity = max(rule.specificity for rule in inclusions)
    top_rules = sorted(
        (rule for rule in inclusions if rule.specificity == top_specificity),
        key=lambda rule: rule.rule_id,
    )
    if len(top_rules) > 1:
        return ApplicabilityResult(
            False,
            None,
            top_specificity,
            reason="ambiguous_same_specificity",
            ambiguous_rule_ids=tuple(rule.rule_id for rule in top_rules),
        )
    winner = top_rules[0]
    return ApplicabilityResult(
        True,
        winner.rule_id,
        winner.specificity,
        reason="matched_most_specific_inclusion",
    )
