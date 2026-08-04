REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO outboard_app;
GRANT SELECT ON
  rb_sites,
  rb_brands,
  rb_engine_models,
  rb_engine_model_translations,
  rb_pages,
  rb_page_revisions
TO outboard_app;
