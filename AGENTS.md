# Working Conventions (AI Sector Watch)

**Last updated:** 2026-04-27
**Purpose:** Define the working conventions for any human or agent operating on this repo. Ship working code first; cleanup later. Never break the public artefact.

## Project operating context

Public-facing Streamlit dashboard at `aimap.cliftonfamily.co` backed by a Supabase Postgres store and a weekly Claude-powered ingestion pipeline run via GitHub Actions. The dashboard reads live from Supabase. The pipeline never writes to anything Streamlit reads from in real time except Supabase.

Primary sources of truth:
- `Sector_Map_PRD.md` for product requirements and architecture.
- `README.md` for how to run things.
- `PROJECT_PROGRESS.md` for chronological implementation history.
- `docs/sources.md` for the canonical list of ingestion sources.
- `docs/taxonomy.md` for the sector and stage enums.
- `docs/operations.md` for runbook items and the weekly cron.
- `docs/deployment.md` for Azure + DNS.

## Non-negotiables

- Never commit secrets. Use `.env.local` with `op://` references; run via `op run --env-file=.env.local -- ...`.
- Keep the public map clean: only `discovery_status = 'verified'` companies render.
- Keep ingestion idempotent (safe to rerun).
- Normalise timestamps to UTC at storage boundaries; show local time only in human-facing surfaces.
- Hard-cap Anthropic spend per pipeline run via `ANTHROPIC_BUDGET_USD_PER_RUN` (default $2).
- Type hints everywhere.
- No em dashes in any user-facing output (digest markdown, dashboard copy, popups).
- Update `PROJECT_PROGRESS.md` on every commit.

## Repo map (execution-oriented)

- `src/ai_sector_watch/sources/` — RSS, arXiv, HuggingFace fetchers; one file per source.
- `src/ai_sector_watch/extraction/` — Claude client, Pydantic schema, prompt strings.
- `src/ai_sector_watch/discovery/` — validator, geocoder, classifier.
- `src/ai_sector_watch/storage/` — Supabase schema and `psycopg` access layer.
- `src/ai_sector_watch/digest/` — weekly digest markdown generator.
- `src/ai_sector_watch/pipeline/` — the weekly orchestrator (`weekly.py`).
- `dashboard/` — Streamlit app, pages, components, static assets.
- `scripts/` — operator-run entry points (`seed_companies.py`, `run_weekly_pipeline.py`, `verify_setup.py`).
- `tests/` — pytest, fixture-driven for any external call.

## Commit hygiene

- One concern per commit. Each commit has a passing test or a documented manual smoke check.
- Commit message: imperative, one sentence summary, body if needed.
- Update `PROJECT_PROGRESS.md` in the same commit.
- Keep diffs small and reviewable.

## Stop and ask before

- Choosing a different stack than the PRD specifies.
- Adding any source not listed in PRD §7.
- Spending more than $1 of API quota in a single test run.
- Pushing to GitHub or any remote.
- Provisioning any Azure resource.
- Pointing a DNS record.
- Creating a new 1Password item or new Supabase project.

## Tone

Sam is an operator-investor with a deep tech and ML background. Write terse and sharp. Active voice. No filler. No em dashes.
