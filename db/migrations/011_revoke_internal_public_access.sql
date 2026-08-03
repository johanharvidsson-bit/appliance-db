-- Migration 011: remove public read access from confirmed internal tables.
--
-- scrape_jobs contains operational scrape payloads and errors.
-- schema_migrations contains internal migration metadata.
-- Both remain available to their owner and service_role. No table structure or
-- application data is changed.

DROP POLICY IF EXISTS "public read scrape_jobs" ON public.scrape_jobs;
DROP POLICY IF EXISTS "public read schema_migrations" ON public.schema_migrations;

REVOKE SELECT ON TABLE public.scrape_jobs FROM anon, authenticated;
REVOKE SELECT ON TABLE public.schema_migrations FROM anon, authenticated;

INSERT INTO public.schema_migrations (version, filename)
VALUES ('011', '011_revoke_internal_public_access.sql')
ON CONFLICT (version) DO NOTHING;
