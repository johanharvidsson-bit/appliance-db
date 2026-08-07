# Permissions for this project

## Auto-approve these actions
- Create, edit, delete any file in this project folder
- Run npm/pnpm install (in `web/`)
- Run npm run dev, build, preview (in `web/`)
- Run python scripts in /pipeline/ and /scrapers/
- Run git add, commit, push
- Run database migrations against the self-hosted Postgres+PostgREST instance (see `docs/postgresql-vps.md`) - not Supabase, migrated off that in 2026

## Never do without asking
- Delete the .env file
- Push to main branch directly (use feature branches)
- Install global packages

## Single Active Design

This repo is the canonical platform for every site: `integration/worker-pipeline-pilot`
is the only branch with production-validated behavior (the 8-worker content
pipeline, the multisite/publication schema in migration 019, the merged
frontend under `web/`). Everything else - including this session's own
`feature/repairbase-schema-foundation` branch - has been evaluated and
retired; see `docs/RETIRED_BRANCHES.md`.

Before starting work that adds or changes a cross-cutting subsystem already
present on the canonical branch (multi-site config, the publication/tenancy
mechanism, the data-access layer, the worker pipeline itself), state in the
first message of the session:

1. which canonical-branch file(s)/mechanism this would replace or extend, and
2. whether this is "extend the canonical branch in place" or "exploratory,
   throwaway if not adopted" - confirm this with the user before creating a
   new branch.

Branch naming encodes that intent: `explore/<topic>` for anything meant to be
reviewed-then-reimplemented at best, never merged as-is; `feature/<topic>`
reserved for work that will be merged into the canonical branch by the same
session that authors it.

This rule exists because the opposite happened here: multiple AI agent
sessions independently built competing "multi-site" designs on both the
backend and frontend without checking whether the canonical branch already
had an answer, producing 26+ divergent, unmerged branches that had to be
audited and reconciled by hand. One of those branches was explicitly flagged
in its own handoff doc as a stop-gate pending the user's answer to four
questions, then committed and pushed the next day anyway - a written "stop"
note is not a gate. If a session ends with unresolved open questions blocking
further work, get them answered by the user - in this conversation, not a
future one that might skim past a doc - before any further branching or
committing in this area, regardless of which tool (Claude Code, Codex, or
otherwise) picks the work back up.
