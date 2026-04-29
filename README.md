# AI Sector Watch

AI Sector Watch is a public map of Australian and New Zealand AI companies.
It combines a verified company index, a public web dashboard, and a private
review workflow for newly discovered candidates.

Public dashboard: https://aimap.cliftonfamily.co

## What It Does

- Shows verified AI companies across Australia and New Zealand on an interactive map.
- Lets users browse companies by sector, stage, country, city, founded year, and name.
- Publishes recent ecosystem activity after automated extraction and review.
- Keeps unreviewed candidates out of the public dashboard.

The project is informational only. It is not investment advice, market sizing,
or a complete record of the ANZ AI ecosystem.

## How It Works

```text
Public signals
     |
     v
Weekly pipeline
     |
     | extracts, validates, classifies, geocodes
     v
Review queue
     |
     | promote verified records only
     v
Supabase Postgres
     |
     v
Next.js public dashboard
```

Key safety rules:

- The public dashboard reads only records marked `verified`.
- New candidates are written as `auto_discovered_pending_review`.
- Pipeline runs are idempotent and safe to rerun.
- Secrets are loaded from environment variables only. Do not commit `.env.local`.
- LLM and enrichment work have per-run budget caps.

## Repository Layout

```text
src/ai_sector_watch/      Python package for ingestion, extraction, discovery, and storage
web/                      Next.js dashboard served in production
dashboard/                Legacy Streamlit dashboard kept during migration
scripts/                  Operator scripts for setup, pipeline runs, and reviewed imports
data/seed/                Seed company data for local fallback and initial bootstrap
data/digests/             Generated public digest markdown
docs/                     Public-safe architecture, operations, and taxonomy notes
tests/                    Pytest suite and fixtures
.github/workflows/        CI, weekly pipeline, and deployment workflows
```

## Local Development

Prerequisites:

- Python 3.12
- Node.js 20
- npm
- Optional: a secret-manager CLI for secret-backed local runs

Install Python tooling:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dashboard,dev]"
```

Install and run the web dashboard:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:3000`.

Without database credentials, pages that need live data may be empty or return
server-side data errors. The Python smoke checks and tests can still run without
live credentials.

## Useful Commands

```bash
pytest -q
ruff check .
black --check .
```

Build the production dashboard:

```bash
cd web
npm run build
npm run lint
```

Run the weekly pipeline locally when secrets are available:

```bash
op run --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5
```

Use `--dry-run` when you want to exercise the pipeline without writing to the
database.

## Documentation

| Topic | File |
|---|---|
| Data model | [`src/ai_sector_watch/storage/supabase_schema.sql`](src/ai_sector_watch/storage/supabase_schema.sql) |
| Pipeline orchestrator | [`src/ai_sector_watch/pipeline/weekly.py`](src/ai_sector_watch/pipeline/weekly.py) |
| Source policy | [`docs/sources.md`](docs/sources.md) |
| Taxonomy | [`docs/taxonomy.md`](docs/taxonomy.md) |
| Operations | [`docs/operations.md`](docs/operations.md) |
| Deployment | [`docs/deployment.md`](docs/deployment.md) |
| Contributor workflow | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Agent workflow | [`AGENTS.md`](AGENTS.md) |

## Data And Privacy

The dashboard is built from public company and ecosystem information, then
reviewed before publication. Review artifacts, source extracts, local caches,
snapshots, and raw audit outputs are operator material and should not be
committed.

Do not commit:

- `.env.local` or any file containing credentials.
- Raw extraction outputs.
- Third-party report text or copied source material.
- Local audit CSV, JSON, Markdown, or snapshot files.
- Personal contact details found in source material.

## Disclaimer

AI Sector Watch may contain errors, omissions, stale links, and imperfect
classifications. Use it as a discovery aid, not as a source of financial,
investment, legal, or hiring advice.
