BEGIN;

INSERT INTO rb_languages(language_code, canonical_name, native_name)
VALUES ('sv', 'Swedish', 'Svenska') ON CONFLICT (language_code) DO NOTHING;

INSERT INTO rb_sources(source_type, title, publisher, document_number, publication_date,
    language_code, rights_holder, hosting_permitted, license_notes, source_authority)
VALUES ('owner_manual', 'F150A/FL150A Ägarens verkstadshandbok', 'Yamaha Motor Co., Ltd.',
    '63P-28199-85-M0', DATE '2007-02-01', 'sv', 'Yamaha Motor Co., Ltd.', FALSE,
    'User-supplied manual retained privately for evidence review; not licensed for public hosting.', 1.0)
ON CONFLICT (publisher, document_number) WHERE document_number IS NOT NULL DO NOTHING;

INSERT INTO rb_source_revisions(source_id, revision_label, content_hash, retrieved_at)
SELECT source_id, 'Första utgåva, februari 2007',
       'eac1fd00adc939e2f20ed7fbe5375543e221522e1b27d3bb32097631bf384237', now()
FROM rb_sources WHERE publisher = 'Yamaha Motor Co., Ltd.' AND document_number = '63P-28199-85-M0'
ON CONFLICT (source_id, content_hash) DO NOTHING;

INSERT INTO rb_engine_models(model_key, brand_id, category_id, canonical_name, normalized_model_code, horsepower_hp, fuel_type)
SELECT 'yamaha-f150a', b.brand_id, c.category_id, 'Yamaha F150A', 'F150A', 150, 'gasoline'
FROM rb_brands b CROSS JOIN rb_product_categories c
WHERE b.brand_key = 'yamaha' AND c.category_key = 'outboard-engines'
ON CONFLICT (brand_id, normalized_model_code) DO NOTHING;

INSERT INTO rb_engine_models(model_key, brand_id, category_id, canonical_name, normalized_model_code, horsepower_hp, fuel_type)
SELECT 'yamaha-fl150a', b.brand_id, c.category_id, 'Yamaha FL150A', 'FL150A', 150, 'gasoline'
FROM rb_brands b CROSS JOIN rb_product_categories c
WHERE b.brand_key = 'yamaha' AND c.category_key = 'outboard-engines'
ON CONFLICT (brand_id, normalized_model_code) DO NOTHING;

INSERT INTO rb_applicability_sets(applicability_key, name)
VALUES ('fault-code:yamaha:f150a-fl150a:check-engine', 'Yamaha F150A and FL150A CHECK ENGINE')
ON CONFLICT (applicability_key) DO NOTHING;

INSERT INTO rb_applicability_rules(applicability_set_id, engine_model_id, notes_internal)
SELECT a.applicability_set_id, m.engine_model_id, 'Directly named on manual cover 63P-28199-85-M0.'
FROM rb_applicability_sets a CROSS JOIN rb_engine_models m
WHERE a.applicability_key = 'fault-code:yamaha:f150a-fl150a:check-engine'
  AND m.normalized_model_code IN ('F150A', 'FL150A')
  AND NOT EXISTS (SELECT 1 FROM rb_applicability_rules r
      WHERE r.applicability_set_id = a.applicability_set_id
        AND r.engine_model_id = m.engine_model_id AND r.is_exclusion = FALSE);

INSERT INTO rb_manuals(manual_key, manual_type, title, document_number, revision, publication_date,
    rights_holder, hosting_permitted, source_id, publication_state)
SELECT 'yamaha-63p-28199-85-m0', 'owner', title, document_number, 'Första utgåva',
       publication_date, rights_holder, FALSE, source_id, 'review'
FROM rb_sources WHERE publisher = 'Yamaha Motor Co., Ltd.' AND document_number = '63P-28199-85-M0'
ON CONFLICT (manual_key) DO NOTHING;

INSERT INTO rb_manual_applicability(manual_id, applicability_set_id)
SELECT m.manual_id, a.applicability_set_id FROM rb_manuals m CROSS JOIN rb_applicability_sets a
WHERE m.manual_key = 'yamaha-63p-28199-85-m0'
  AND a.applicability_key = 'fault-code:yamaha:f150a-fl150a:check-engine'
ON CONFLICT DO NOTHING;

INSERT INTO rb_fault_codes(fault_code_key, brand_id, applicability_set_id, display_code, normalized_code,
    title, description, editorial_review_state, publication_state)
SELECT 'yamaha-f150a-fl150a-check-engine', b.brand_id, a.applicability_set_id,
       'CHECK ENGINE', 'CHECK ENGINE', 'Varning för motorfel',
       'På Yamaha F150A och FL150A blinkar motorfelsindikatorn när ett motorfel upptäcks under gång. Yamaha instruerar föraren att gå till närmaste hamn och omedelbart kontakta en Yamaha-återförsäljare.',
       'needs_review', 'draft'
FROM rb_brands b CROSS JOIN rb_applicability_sets a
WHERE b.brand_key = 'yamaha' AND a.applicability_key = 'fault-code:yamaha:f150a-fl150a:check-engine'
ON CONFLICT (fault_code_key) DO NOTHING;

INSERT INTO rb_fault_code_sources(fault_code_id, source_revision_id, source_locator, support_type, verified_by, verified_at)
SELECT fc.fault_code_id, sr.source_revision_id,
       'PDF page 36; printed page 30; section "Varning för motorfel"', 'direct', 'codex-pdf-review', now()
FROM rb_fault_codes fc
JOIN rb_sources s ON s.publisher = 'Yamaha Motor Co., Ltd.' AND s.document_number = '63P-28199-85-M0'
JOIN rb_source_revisions sr ON sr.source_id = s.source_id
  AND sr.content_hash = 'eac1fd00adc939e2f20ed7fbe5375543e221522e1b27d3bb32097631bf384237'
WHERE fc.fault_code_key = 'yamaha-f150a-fl150a-check-engine'
ON CONFLICT (fault_code_id, source_revision_id, source_locator) DO NOTHING;

COMMIT;
