-- Migration 028: public read access for guides/guide_translations.
--
-- guides/guide_translations/guide_error_codes/guide_faults were created
-- (migration 016) with RLS policies scoped "TO api_public_owner" - a role
-- meant to own the api_public.* views from migration 019's multisite
-- publication layer. But nothing else in the frontend or pipeline uses that
-- layer yet (faults/models/error_codes/articles are all read directly by
-- anon/authenticated via a plain GRANT + permissive RLS, migrations 007/027).
-- Left as-is, guides were unreachable by anon/authenticated at the GRANT
-- level (not just filtered by RLS) - "permission denied for table guides".
-- This widens the existing policies to also cover anon/authenticated,
-- matching the simpler convention every other public-facing table already
-- uses, rather than introducing a second, inconsistent access pattern.
BEGIN;

ALTER POLICY "api public owner published guides" ON public.guides
    TO api_public_owner,anon,authenticated;
ALTER POLICY "api public owner published guide content" ON public.guide_translations
    TO api_public_owner,anon,authenticated;
ALTER POLICY "api public owner verified guide errors" ON public.guide_error_codes
    TO api_public_owner,anon,authenticated;
ALTER POLICY "api public owner verified guide faults" ON public.guide_faults
    TO api_public_owner,anon,authenticated;

GRANT SELECT ON public.guides,public.guide_translations,
    public.guide_error_codes,public.guide_faults TO anon,authenticated;

INSERT INTO public.schema_migrations(version,filename)
VALUES('028','028_guide_public_read_access.sql') ON CONFLICT(version) DO NOTHING;
NOTIFY pgrst,'reload schema';
COMMIT;
