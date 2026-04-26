# AI Sector Watch

Live, public-facing ecosystem map of the Australian and New Zealand AI startup landscape, updated weekly by an automated agent pipeline.

Public dashboard: https://aimap.cliftonfamily.co (coming online with v0)

## What it does

- Renders ~50+ verified ANZ AI companies on an interactive map of Australia.
- Each marker opens a popup with company name, sector tags, last funding event, summary, and website.
- Sidebar filters: sector, stage, country, founded year, name search.
- Recent-news panel showing the past week's funding, launches, hires, and partnerships.
- Weekly GitHub Actions cron job ingests RSS sources, asks Claude to extract company mentions, validates and classifies new candidates, and writes them to Supabase as `pending` for admin review.

The data layer is Supabase Postgres. The dashboard is Streamlit + streamlit-folium hosted on Azure App Service. The pipeline is Python 3.12 with the Anthropic SDK and `feedparser`.

## Quick start (local)

Prerequisites: Python 3.12, the 1Password CLI (`op`), `gh`, and `az` on PATH.

```bash
# Create venv and install
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dashboard,dev]"

# Wire secrets (copy template, edit op:// references for your vault items)
cp .env.template .env.local
op signin

# Smoke test
op run --env-file=.env.local -- python scripts/verify_setup.py

# Seed the database (one-time, idempotent)
op run --env-file=.env.local -- python scripts/seed_companies.py

# Run the dashboard locally
op run --env-file=.env.local -- streamlit run dashboard/streamlit_app.py
```

## Manual pipeline run

```bash
op run --env-file=.env.local -- python scripts/run_weekly_pipeline.py
```

Or trigger the GitHub Actions workflow on demand:

```bash
gh workflow run weekly.yml
```

## Adding a source

1. Create a new module under `src/ai_sector_watch/sources/` that subclasses `SourceBase` and implements `fetch()`.
2. Add an entry to `docs/sources.md`.
3. Register the source in `src/ai_sector_watch/pipeline/weekly.py`.
4. Add a fixture-backed test under `tests/test_rss_sources.py`.

## Adding a seed company

Edit `data/seed/companies.yaml` and rerun `scripts/seed_companies.py`. The seeder is idempotent (upsert by `(name, country)`).

## Repo layout

See `Sector_Map_PRD.md` §6 for the canonical structure. Key directories:

- `src/ai_sector_watch/` — pipeline package (sources, extraction, discovery, storage, digest)
- `dashboard/` — Streamlit app and pages
- `scripts/` — operator-run entry points
- `data/seed/` — human-curated seed list (YAML)
- `data/digests/` — weekly digest markdown, written by the pipeline and committed back from CI
- `tests/` — pytest, fixture-driven for any external call

## Contributing

This is a single-operator project. Conventions in `AGENTS.md`. Working rules:

- Type hints everywhere.
- `ruff` and `black` configured in `pyproject.toml`.
- All secrets via 1Password (`op run`); bare values never in files.
- All log lines redact tokens.
- Idempotent operations (safe to retry).
- No em dashes in user-facing output.
- Every commit updates `PROJECT_PROGRESS.md`.

## Disclaimer

Data is auto-extracted from public sources by an automated pipeline and may contain errors or omissions.
