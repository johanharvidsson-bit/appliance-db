from pathlib import Path


SQL = (Path(__file__).parents[1] / "db" / "migrations" / "015_url_registry_and_entity_bindings.sql").read_text(encoding="utf-8")


def test_migration_is_additive_internal_and_has_no_redirect_table():
    lowered = SQL.lower()
    assert "create table public.url_registry" in lowered
    assert "create table public.entity_url_bindings" in lowered
    assert "create table public.url_redirects" not in lowered
    assert "enable row level security" in lowered
    assert "force row level security" in lowered
    assert "revoke all on public.url_registry from public, anon, authenticated" in lowered
    assert "grant select on public.url_registry to anon" not in lowered
    assert "grant select on public.entity_url_bindings to anon" not in lowered
    assert "revoke all on function public.touch_information_model_updated_at() from public, anon, authenticated" in lowered


def test_registry_and_binding_invariants_are_present():
    assert "unique (site_id, environment, normalized_url)" in SQL.lower()
    assert "num_nonnulls(brand_id, category_id, model_id, product_code_id" in SQL.lower()
    assert "entity_url_bindings_one_current_primary_uidx" in SQL
    assert "entity_url_bindings_one_current_candidate_uidx" in SQL
    assert "on delete restrict" in SQL.lower()
    assert "on delete cascade" not in SQL.lower()


def test_migration_contains_no_data_backfill_or_public_projection_change():
    lowered = SQL.lower()
    assert "insert into public.url_registry" not in lowered
    assert "insert into public.entity_url_bindings" not in lowered
    assert "api_public.model_pages" not in lowered
    assert "refresh materialized view" not in lowered
    assert "redirect" in lowered  # explanatory no-redirect comment only
