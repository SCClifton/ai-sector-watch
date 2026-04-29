# Project Progress

Public-safe milestone log. Keep raw operational notes, account identifiers,
incident details, copied source material, review artifacts, and personal
contact details out of this file. Routine fixes belong in PR bodies.

## Current State

- Production serves the custom Next.js dashboard under `web/`.
- The legacy Streamlit dashboard remains under `dashboard/` during migration.
- Supabase Postgres is the live data store.
- Weekly ingestion writes reviewed public digests and pending company
  candidates for human review.
- The public dashboard shows verified companies only.

## Recent Milestones

### 2026-04-30: Deep-Research Profile Refresh

- Applied a manual deep-research verification pass across 39 verified
  companies, writing richer summaries, current funding (with as-of dates and
  source URLs), updated headcount, founded years, stages, and cities.
- Each updated row carries a stamped `profile_verified_at` and a confidence
  score so downstream surfaces can show provenance.
- Companies flagged as defunct, non-ANZ, or non-AI were captured in a separate
  triage artifact and will be rejected via a follow-up change.

### 2026-04-29: Custom Web Dashboard

- Replaced the initial Streamlit-first public experience with a custom Next.js
  dashboard.
- Added the interactive map, company directory, news feed, about page, and
  password-gated admin queue.
- Added a container deployment path and health endpoint.

### 2026-04-29: Reviewed Funding Import Path

- Added a guarded manual import workflow for reviewed funding and company-stage
  updates.
- Kept new companies pending until explicitly promoted.
- Added public funding display on company profiles.

### 2026-04-28: Company Profile Enrichment

- Added richer company profile fields for founders, funding, valuation,
  headcount, confidence, and verification timestamp.
- Added reviewed update tooling for operator-controlled profile corrections.

### 2026-04-27: Public Dashboard V0

- Launched the first public dashboard.
- Added map, company list, news, digest, and admin review surfaces.
- Added CI checks for tests, linting, and formatting.

### 2026-04-27: Pipeline Foundation

- Added the Python ingestion, extraction, discovery, storage, digest, and
  weekly orchestration modules.
- Added idempotent storage writes and review-gated company discovery.
- Added seed data and fixture-driven tests.

### 2026-04-27: Multi-Agent Workflow

- Added the per-issue worktree workflow for parallel AI and human contributors.
- Added helper scripts for issue startup and cleanup.
- Documented branch, PR, and review rules.

## Test Baseline

Expected local checks:

```bash
pytest -q
ruff check .
black --check .
cd web && npm run build
cd web && npm run lint
```

Live database and pipeline checks require environment secrets and should be run
only with bounded limits.
