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

### 2026-04-30: Mobile Public Dashboard Optimisation

- Added mobile-first navigation and responsive filter sheets for the public
  map and company directory while preserving the desktop dashboard layout.
- Made the map route app-like on phones: no global footer, touch-sized map
  controls, mobile search, a bottom action bar, and a bottom company detail
  sheet.
- Tightened mobile layouts for the home page, company profiles, news, about,
  and footer so shared links render cleanly on narrow screens.

### 2026-04-30: Surface Freshness On The Map And Directory

- Recently verified and newly funded companies now read at a glance on every
  public surface: badges in the directory list, the company profile, and the
  map detail panel; an outline ring on the corresponding map markers.
- Added a Freshness filter chip and matching sort options ("Recently verified",
  "Recently funded") to the companies directory. A unified sort dropdown
  replaces the previous header-only column sort.
- Uses existing fields only (`profile_verified_at`, `total_raised_as_of`); no
  schema or API change. Thresholds: 14 days for verified, 90 days for funded.

### 2026-04-30: Verification Tooling Committed

- Added the deep-research verification toolkit to the repo so future re-runs
  do not depend on local stash state: a sector-by-sector prompt template,
  a per-group prompt generator, a response parser tolerant of Gemini and
  ChatGPT output styles, and a verified-companies dump helper.
- Hardened the parser so string `profile_confidence` labels (e.g. `"high"`,
  `"medium"`, `"low"`) are normalised to floats automatically. Removes the
  manual JSON-edit step that has been needed each apply cycle.
- Added fixture-driven tests for both the generator and the parser; full
  `pytest`, `ruff` and `black` pass.

### 2026-04-30: Re-Run Verification For Four Missed Companies

- Filled coverage gap from the original deep-research pass (the first-listed
  company in four cohorts was dropped from Gemini's JSON output despite being
  discussed in the prose).
- Wrote substantive updates for AutoGrab (Melbourne, Series B+, 91 staff),
  Advanced Navigation (headcount 188), and Cortical Labs (Melbourne, Series A,
  35 staff).
- Atlassian's re-verification flagged it for rejection on a strict AI-first
  reading; held that decision for a human policy call (mirrors the precedent
  set for Canva, kept in the review pile rather than rejected).

### 2026-04-30: Dropped Founders From Public Profile

- Removed the founders field from the public companies API and from the
  click-on-company detail panels on the map and the company profile page.
- Removed founders from the apply gate so future profile updates that include
  it are rejected at validation time.
- Kept the database column intact so the admin queue still shows founders for
  human review of pending companies. No data loss.

### 2026-04-30: Rejected 16 Out-Of-Scope Companies

- Removed 16 companies from the public map after a deep-research review found
  them defunct, headquartered outside Australia or New Zealand, or not
  AI-focused.
- Added `scripts/apply_company_rejections.py` for repeatable, dry-run-by-default
  rejection apply, with per-row audit captured in `ingest_events`.

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
