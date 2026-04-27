# AI Sector Watch

Live, public-facing ecosystem map of the Australian and New Zealand AI startup landscape, updated weekly by an automated agent pipeline.

**Public dashboard:** https://aimap.cliftonfamily.co

---

## Table of contents

1. [What this is](#what-this-is)
2. [How it works](#how-it-works)
3. [Repo layout](#repo-layout)
4. [Quick start (local)](#quick-start-local)
5. [Running the pipeline](#running-the-pipeline)
6. [Common tasks](#common-tasks)
7. [Where to find things](#where-to-find-things)
8. [Working conventions](#working-conventions)
9. [Disclaimer](#disclaimer)

---

## What this is

AI Sector Watch is two things bolted together:

1. **A read-only public map.** Streamlit dashboard with an interactive folium map of Australia and New Zealand. Each marker is a verified AI company. Filter by sector, stage, country, year, or name. Click a marker for a popup with the company's profile and link.
2. **A weekly agent pipeline.** A GitHub Actions cron job ingests RSS feeds and APIs, asks an LLM to extract company mentions, validates and classifies new candidates against a fixed taxonomy, and writes them to Supabase as `pending` for human review. Verified companies appear on the public map; pending ones never do.

The two halves are decoupled: the dashboard reads from Supabase, the pipeline writes to it.

## How it works

```
                           ┌─────────────────────────────┐
                           │  GitHub Actions cron        │
                           │  (Sunday 18:00 UTC)         │
                           └──────────────┬──────────────┘
                                          │
                                          ▼
   ┌──────────────┐    ┌────────────────────────────────────────┐
   │ RSS / arXiv  │───▶│  weekly_pipeline.py                    │
   │ HF papers    │    │   1. fetch every source                │
   └──────────────┘    │   2. LLM extracts company mentions     │
                       │   3. validate + classify per candidate │
                       │   4. geocode (ANZ city table)          │
                       │   5. upsert pending + news + digest    │
                       └─────────────────┬──────────────────────┘
                                         │
                                         ▼
                           ┌─────────────────────────────┐
                           │  Supabase Postgres          │
                           │  (companies, news_items,    │
                           │   funding_events, ingest)   │
                           └──────────────┬──────────────┘
                                          │ read
                                          ▼
                           ┌─────────────────────────────┐
                           │  Streamlit dashboard        │
                           │  on Azure App Service       │
                           │  https://aimap.cliftonfamily.co │
                           └─────────────────────────────┘
```

Hard limits on the weekly run:
- LLM spend capped at `ANTHROPIC_BUDGET_USD_PER_RUN` (default $2). When the cap is hit, the run records `partial` and exits cleanly.
- Successful LLM responses cached on disk by `(model, system, prompt, schema_class)` so reruns are free within the cache TTL.
- Per-source failures don't abort the run; they're logged, recorded, and skipped.

## Repo layout

```
ai-sector-watch/
├── src/ai_sector_watch/
│   ├── config.py             # typed env-var loader
│   ├── sources/              # one file per RSS / API source
│   │   ├── base.py           # SourceBase ABC + RawItem dataclass
│   │   ├── rss.py            # generic RSS via feedparser + httpx
│   │   ├── arxiv_source.py   # arXiv cs.AI / cs.LG / cs.RO
│   │   └── huggingface_papers.py
│   ├── extraction/           # LLM client + prompts + Pydantic schemas
│   │   ├── claude_client.py  # budget-capped, on-disk-cached
│   │   ├── prompts.py
│   │   └── schema.py
│   ├── discovery/            # post-extraction reasoning
│   │   ├── geocoder.py       # static ANZ city lookup with jitter
│   │   ├── taxonomy.py       # 21 sectors, 5 stages, colour bands
│   │   ├── validator.py
│   │   └── classifier.py
│   ├── storage/              # Supabase access layer
│   │   ├── supabase_db.py    # psycopg with retry/backoff
│   │   ├── supabase_schema.sql
│   │   └── data_source.py    # dashboard read API (Supabase + YAML fallback)
│   ├── digest/generator.py   # weekly markdown writer
│   └── pipeline/weekly.py    # the orchestrator
├── dashboard/
│   ├── streamlit_app.py      # home page (entry point)
│   ├── pages/
│   │   ├── 1_Map.py          # the headline view
│   │   ├── 2_Companies.py
│   │   ├── 3_News.py
│   │   ├── 4_Digest.py
│   │   └── 90_Admin.py       # password-gated review queue
│   └── components/           # reusable Streamlit components
├── scripts/
│   ├── verify_setup.py       # PASS/WARN/FAIL smoke check
│   ├── seed_companies.py     # bootstrap from data/seed/companies.yaml
│   └── run_weekly_pipeline.py
├── data/
│   ├── seed/companies.yaml   # ~50 hand-curated ANZ AI companies
│   └── digests/              # weekly markdown, committed by CI
├── docs/
│   ├── sources.md            # canonical list of RSS / API endpoints
│   ├── taxonomy.md           # sector + stage enums (mirrors Python)
│   ├── operations.md         # cron + cost + rollback runbook
│   └── deployment.md         # Azure + DNS + TLS runbook
├── tests/                    # pytest, fixture-driven
├── .github/workflows/
│   ├── pytest.yml            # on push + PR
│   ├── weekly.yml            # the cron + workflow_dispatch
│   └── deploy.yml            # build container, push to GHCR, deploy to Azure
├── Dockerfile
├── pyproject.toml
├── AGENTS.md                 # working conventions for AI/human contributors
└── PROJECT_PROGRESS.md       # chronological build log
```

## Quick start (local)

Prerequisites:
- Python 3.12 (`brew install python@3.12`)
- 1Password CLI (`brew install 1password-cli`)
- GitHub CLI (`brew install gh`) and Azure CLI (`brew install azure-cli`) if you'll touch CI / Azure

```bash
# Clone
gh repo clone SCClifton/ai-sector-watch
cd ai-sector-watch

# Create venv and install (the [dashboard,dev] extras pull in Streamlit + tests)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dashboard,dev]"

# Wire secrets. Copy the template and edit op:// references to point at your
# 1Password items. .env.local is gitignored.
cp .env.template .env.local
op signin

# Sanity check (without secrets you'll see WARN/FAIL on Supabase rows; that's fine)
python scripts/verify_setup.py

# Run the dashboard against the YAML fallback (no Supabase needed)
AISW_FORCE_YAML=1 streamlit run dashboard/streamlit_app.py
# -> open http://localhost:8501
```

Once your Supabase project is provisioned and your 1Password references are wired:

```bash
op run --account my.1password.com --env-file=.env.local -- python scripts/verify_setup.py --apply-schema
op run --account my.1password.com --env-file=.env.local -- python scripts/seed_companies.py
op run --account my.1password.com --env-file=.env.local -- streamlit run dashboard/streamlit_app.py
```

## Running the pipeline

Locally, with secrets:

```bash
op run --account my.1password.com --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5
```

`--limit N` caps items per source (useful for cheap test runs). `--dry-run` exercises every step except the Supabase writes.

Via GitHub Actions (manual trigger):

```bash
gh workflow run weekly.yml -f limit=10
gh run watch
```

The cron fires every Sunday 18:00 UTC (Monday morning Sydney time).

## Common tasks

### Add a data source

1. Create a new module under `src/ai_sector_watch/sources/` that subclasses `SourceBase` and implements `fetch()` returning `list[RawItem]`.
2. Add a row to [`docs/sources.md`](docs/sources.md).
3. Register the factory in `default_sources()` in [`src/ai_sector_watch/pipeline/weekly.py`](src/ai_sector_watch/pipeline/weekly.py).
4. Add a fixture-driven test under [`tests/test_rss_sources.py`](tests/test_rss_sources.py).

### Add a seed company

Append a block to [`data/seed/companies.yaml`](data/seed/companies.yaml) (schema is documented at the top of the file), then:

```bash
python scripts/seed_companies.py --dry-run    # validate
op run --account my.1password.com --env-file=.env.local -- python scripts/seed_companies.py    # apply
```

The seeder is idempotent (upsert by `(name_normalised, country)`).

### Add a sector tag

1. Add a `Sector(...)` entry to `SECTORS` in [`src/ai_sector_watch/discovery/taxonomy.py`](src/ai_sector_watch/discovery/taxonomy.py). Pick an existing colour group or add a new group + colour.
2. Mirror the change in [`docs/taxonomy.md`](docs/taxonomy.md).
3. The SQL stores `sector_tags` as `TEXT[]`, so no migration needed.
4. `pytest tests/test_taxonomy.py` to confirm.

### Promote / reject an auto-discovered company

Hit the **Admin** page (password-gated). The pipeline writes new candidates as `auto_discovered_pending_review`. Verified ones appear on the public map. Rejected ones stay in the DB but never surface.

## Where to find things

| Question | File |
|---|---|
| What does the data model look like? | [`src/ai_sector_watch/storage/supabase_schema.sql`](src/ai_sector_watch/storage/supabase_schema.sql) |
| How does the pipeline orchestrate the run? | [`src/ai_sector_watch/pipeline/weekly.py`](src/ai_sector_watch/pipeline/weekly.py) |
| What sources do we ingest? | [`docs/sources.md`](docs/sources.md) |
| What sectors and stages exist? | [`docs/taxonomy.md`](docs/taxonomy.md) |
| How do I run the cron in CI? | [`.github/workflows/weekly.yml`](.github/workflows/weekly.yml) and [`docs/operations.md`](docs/operations.md) |
| How is the dashboard deployed? | [`docs/deployment.md`](docs/deployment.md) and [`Dockerfile`](Dockerfile) |
| What conventions should I follow when contributing? | [`AGENTS.md`](AGENTS.md) |
| What got built and when? | [`PROJECT_PROGRESS.md`](PROJECT_PROGRESS.md) |

## Working conventions

Full detail in [`AGENTS.md`](AGENTS.md). Short version:

- Python 3.12, type hints everywhere, ruff + black configured in `pyproject.toml`.
- All secrets via 1Password (`op run --account my.1password.com --env-file=.env.local -- ...`). Bare values never in files; `.env.local` is gitignored; only `.env.template` (with `op://` references) is committed.
- Idempotent operations: every upsert keys on a stable hash; the pipeline is safe to rerun.
- No em dashes in any user-facing output (digest, dashboard copy, popups). Use a colon, comma, or " - " instead.
- Every commit updates `PROJECT_PROGRESS.md`.
- The public map only shows `discovery_status = 'verified'`. Auto-discovered candidates wait in the admin queue.

## Disclaimer

Data is auto-extracted from public sources by an automated pipeline and may contain errors or omissions. Don't rely on it for investment decisions.
