from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_SQL = (
    ROOT / "db/migrations/011_repairbase_catalog_applicability.sql"
).read_text(encoding="utf-8")
EVIDENCE_SQL = (
    ROOT / "db/migrations/012_repairbase_evidence_specifications.sql"
).read_text(encoding="utf-8")
PUBLICATION_SQL = (
    ROOT / "db/migrations/013_repairbase_localization_publication.sql"
).read_text(encoding="utf-8")
FIXTURE_SQL = (ROOT / "tests/fixtures/repairbase_phase1.sql").read_text(encoding="utf-8")


def test_catalog_tables_are_isolated_from_legacy_schema():
    expected = {
        "rb_languages",
        "rb_sites",
        "rb_engine_models",
        "rb_engine_generations",
        "rb_model_variants",
        "rb_model_years",
        "rb_applicability_sets",
        "rb_applicability_rules",
    }
    assert all(f"CREATE TABLE {table}" in CATALOG_SQL for table in expected)
    assert "CREATE TABLE models" not in CATALOG_SQL
    assert "CREATE TABLE brands" not in CATALOG_SQL


def test_applicability_has_real_foreign_keys_and_one_target_constraint():
    assert "rb_applicability_rules_one_target" in CATALOG_SQL
    assert "REFERENCES rb_engine_models" in CATALOG_SQL
    assert "REFERENCES rb_engine_generations" in CATALOG_SQL
    assert "REFERENCES rb_model_variants" in CATALOG_SQL
    assert "\n    entity_type " not in CATALOG_SQL
    assert "\n    entity_id " not in CATALOG_SQL
    assert "rb_applicability_set_structure" in CATALOG_SQL


def test_nullable_model_year_uniqueness_uses_partial_indexes():
    assert "rb_model_years_generation_only_uq" in CATALOG_SQL
    assert "WHERE model_variant_id IS NULL" in CATALOG_SQL
    assert "rb_model_years_variant_uq" in CATALOG_SQL
    assert "WHERE model_variant_id IS NOT NULL" in CATALOG_SQL


def test_catalog_branch_contradictions_have_composite_foreign_keys():
    assert "rb_engine_models_line_chain_fk" in CATALOG_SQL
    assert "REFERENCES rb_product_lines(product_line_id, brand_id, category_id)" in CATALOG_SQL
    assert "rb_model_years_variant_chain_fk" in CATALOG_SQL
    assert "REFERENCES rb_model_variants(model_variant_id, engine_generation_id)" in CATALOG_SQL


def test_assertions_use_fk_safe_owners_and_publication_gate():
    assert "CREATE TABLE rb_engine_generation_assertions" in EVIDENCE_SQL
    assert "CREATE TABLE rb_model_variant_assertions" in EVIDENCE_SQL
    assert "subject_domain" not in EVIDENCE_SQL
    assert "subject_key" not in EVIDENCE_SQL
    assert "rb_assertion_publication_gate" in EVIDENCE_SQL
    assert "AFTER INSERT OR UPDATE ON rb_technical_assertions" in EVIDENCE_SQL
    assert "rb_technical_assertions_protect_published" in EVIDENCE_SQL
    assert "rb_evidence_links_protect_published" in EVIDENCE_SQL
    assert "rb_source_revisions_immutable" in EVIDENCE_SQL


def test_hosted_manual_requires_permission():
    assert "rb_manuals_hosting_rights" in EVIDENCE_SQL
    assert "hosted_file_url IS NULL OR hosting_permitted IS TRUE" in EVIDENCE_SQL


def test_pages_use_fk_safe_subjects_and_site_scope_validation():
    assert "rb_pages_one_subject" in PUBLICATION_SQL
    assert "rb_pages_type_matches_subject" in PUBLICATION_SQL
    assert "rb_pages_validate_site_scope" in PUBLICATION_SQL
    assert "\n    subject_domain " not in PUBLICATION_SQL
    assert "\n    subject_key " not in PUBLICATION_SQL


def test_localized_page_collisions_and_cross_site_leakage_are_rejected():
    assert "rb_pages_canonical_path_uq" in PUBLICATION_SQL
    assert "ON rb_pages (site_id, language_code, canonical_path)" in PUBLICATION_SQL
    assert "rb_pages_active_slug_uq" in PUBLICATION_SQL
    assert "page subject category is not enabled for site" in PUBLICATION_SQL
    assert "page subject brand is not enabled for site" in PUBLICATION_SQL


def test_page_publication_requires_revision_and_index_requires_publication():
    assert "rb_pages_publication_gate" in PUBLICATION_SQL
    assert "published page must reference a page revision" in PUBLICATION_SQL
    assert "only published pages may be indexed" in PUBLICATION_SQL
    assert "FOREIGN KEY (published_revision_id, page_id)" in PUBLICATION_SQL
    assert "rb_page_revisions_immutable" in PUBLICATION_SQL


def test_hreflang_redirects_and_audit_are_scoped():
    assert "rb_pages_hreflang_language_uq" in PUBLICATION_SQL
    assert "hreflang cluster cannot cross sites or content identities" in PUBLICATION_SQL
    assert "rb_redirects_active_path_uq" in PUBLICATION_SQL
    assert "redirect target must belong to the same site and language" in PUBLICATION_SQL
    assert "rb_technical_assertions_audit" in PUBLICATION_SQL
    assert "rb_pages_audit" in PUBLICATION_SQL


def test_fixture_is_transactional_and_contains_both_pilot_models():
    assert FIXTURE_SQL.startswith("-- Transactional integration fixture")
    assert "BEGIN;" in FIXTURE_SQL
    assert FIXTURE_SQL.rstrip().endswith("ROLLBACK;")
    assert "fixture-yamaha-f150" in FIXTURE_SQL
    assert "fixture-mercury-150-fourstroke" in FIXTURE_SQL
