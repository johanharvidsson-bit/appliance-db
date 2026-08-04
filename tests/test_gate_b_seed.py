from pathlib import Path


SEED = Path("db/seeds/gate_b_five_item_pilot.sql")


def test_gate_b_seed_uses_exact_model_identifiers() -> None:
    sql = SEED.read_text(encoding="utf-8")
    assert "WF45T6000A" in sql
    assert "WF45B6300AC" in sql
    assert "Samsung WF45A'" not in sql
    assert "Samsung WF45B'" not in sql


def test_gate_b_seed_never_resets_reviewed_error_content() -> None:
    sql = SEED.read_text(encoding="utf-8")
    error_insert = sql.index("INSERT INTO public.error_codes")
    translation_insert = sql.index("INSERT INTO public.error_code_translations")
    unrelated_translation = sql.index("-- Keep unrelated integration-test codes")
    assert "ON CONFLICT(brand_id, category_id, code) DO NOTHING" in sql[
        error_insert:translation_insert
    ]
    assert "ON CONFLICT(error_code_id, locale) DO NOTHING" in sql[
        translation_insert:unrelated_translation
    ]
