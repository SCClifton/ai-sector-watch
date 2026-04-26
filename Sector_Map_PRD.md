# AI Sector Watch — v0 PRD

**Owner:** Sam Clifton
**Created:** 2026-04-27
**Updated:** 2026-04-27 (Streamlit, Azure, weekly cadence, ANZ map locked in)
**Target v0 ship:** Within 6 to 8 hours of focused work

## 1. What this is

A live, public-facing ecosystem map of the Australian and New Zealand AI startup landscape, updated weekly by an automated agent pipeline.

The headline view is an interactive map of Australia. Each dot is an AI-native or AI-applied company. Click a dot, get a popup with the company name, sector tags, last funding event, a one-paragraph summary, and a link to its website. A side panel shows the same companies as a filterable list, plus the current week's relevant news.

A weekly automated job ingests news from public sources, extracts company mentions, validates new candidates, and updates the database. The dashboard reads live from the database.

## 2. Why this exists

Two reasons:

1. **Operational tool.** A live ecosystem map is a real productivity multiplier for AI sourcing, competitive intelligence, and thesis development as a venture investor.
2. **Demonstrative build.** A working public dashboard built end-to-end by a single operator is direct, shareable evidence of agentic AI fluency. It anchors the AirTree application's "what have you built with AI" and "first thing you'd do Monday" answers.

## 3. Goals (v0)

- **G1.** Public Streamlit dashboard at `aimap.cliftonfamily.co` (or chosen subdomain) with an interactive Australia map showing seeded ANZ AI companies.
- **G2.** Click-through company popups with name, sector, summary, last funding, link.
- **G3.** Weekly GitHub Actions job that ingests news, auto-discovers new companies, and writes to Supabase.
- **G4.** Filter sidebar on map and list (sector, stage, founded year, country).
- **G5.** Recent news panel showing the past week's relevant funding, launches, hires, and partnerships.
- **G6.** Admin review queue for auto-discovered companies before they appear on the public map.
- **G7.** Test coverage on each pipeline stage. Idempotent loads.
- **G8.** Public deploy with footer caveat that data is auto-extracted and may contain errors.

## 4. Non-goals (v0)

- Daily updates (weekly is enough for v0)
- Email or Slack notifications
- LinkedIn or Twitter scraping
- Multi-user accounts
- Watchlist or saved searches
- Realtime alerting
- Anthropic Agent Skills integration (planned for v1)
- Tavily or Exa search (planned for v1)
- Heat map or theme view (planned for v1)
- Backfill beyond what RSS exposes

## 5. Users and stories

**Primary user: Sam, the operator-investor (also the author).**

- As a VC investor, I want to open the map on Monday and see the ANZ AI ecosystem at a glance, with last week's movements highlighted.
- As a sourcing user, I want to filter by sector and stage so I can focus on pre-seed and seed AI startups.
- As an external viewer (e.g. AirTree partner reviewing the application), I want a polished, working public artefact that proves the author can ship an agentic system end-to-end.

**Secondary user: anyone visiting the public URL.**

- As a curious visitor, I want to see the ANZ AI ecosystem visualised. I should never see broken or low-quality entries.

## 6. Architecture

### Stack

- **Frontend:** Streamlit + streamlit-folium for the map, Pandas tables for list views, Tailwind via Streamlit theming where possible.
- **Backend / data:** Supabase Postgres for durable storage. Local SQLite cache only used in development. Production Streamlit reads directly from Supabase via psycopg.
- **Pipeline:** Python 3.12, Anthropic Python SDK (Claude Sonnet) for entity extraction and validation, `feedparser` for RSS, `arxiv` for arXiv, `httpx` for HTTP.
- **Scheduling:** GitHub Actions cron, runs weekly. Manual trigger available via `workflow_dispatch`.
- **Hosting:** Azure App Service or Container Apps for the Streamlit dashboard. Custom domain `aimap.cliftonfamily.co` via Cloudflare or Azure DNS.
- **Testing:** pytest, ruff, black.

### High-level flow

```
GitHub Actions (Sunday 18:00 UTC weekly)
   |
   v
weekly_pipeline.py
   - Ingest from RSS sources
   - Extract candidates with Claude
   - For each new candidate company:
       validate, geocode, sector-classify, mark pending
   - For each new news item: link to company, classify
   - Upsert to Supabase
   - Commit weekly digest markdown back to repo
   |
   v
Supabase Postgres
   |
   v (read)
Streamlit on Azure (always-on)
   |
   v
aimap.cliftonfamily.co (public)
```

### Repo layout

```
ai-sector-watch/
  pyproject.toml
  README.md
  .env.example
  src/ai_sector_watch/
    config.py
    sources/
      base.py
      rss.py
      arxiv_source.py
      huggingface_papers.py
    extraction/
      claude_client.py
      schema.py
      prompts.py
    discovery/
      validator.py        # validates auto-discovered companies
      geocoder.py         # static ANZ city lookup
      classifier.py       # sector classification
    storage/
      supabase_db.py
      supabase_schema.sql
    digest/
      generator.py
    pipeline/
      weekly.py
  scripts/
    seed_companies.py     # bootstrap seed list
    run_weekly_pipeline.py
    verify_setup.py
  dashboard/
    streamlit_app.py
    pages/
      1_Map.py
      2_Companies.py
      3_News.py
      4_Digest.py
      90_Admin.py         # auto-discovery review queue
    components/
      map_view.py
      filters.py
      popup.py
    static/
      footer.md
  data/
    seed/companies.yaml   # human-curated seed list
    digests/              # weekly digest markdown
  .github/workflows/
    weekly.yml
    deploy.yml
  tests/
    test_rss_sources.py
    test_extraction.py
    test_storage.py
    test_validator.py
    test_geocoder.py
    test_pipeline_integration.py
  docs/
    sources.md
    taxonomy.md
    operations.md
    deployment.md
```

## 7. Data sources (v0)

Same starter list as before, weekly pull (one fetch per source per week).

| Source | URL | Type | ANZ relevance |
|---|---|---|---|
| arXiv cs.AI | https://export.arxiv.org/rss/cs.AI | Papers | Medium |
| arXiv cs.LG | https://export.arxiv.org/rss/cs.LG | Papers | Medium |
| arXiv cs.RO | https://export.arxiv.org/rss/cs.RO | Papers | Medium |
| TechCrunch AI | https://techcrunch.com/category/artificial-intelligence/feed/ | News | Low |
| Startup Daily AU | https://www.startupdaily.net/feed/ | News | High |
| Smartcompany Startups | https://www.smartcompany.com.au/startupsmart/feed/ | News | High |
| Capital Brief | (RSS check) | News | High |
| AirTree Open Source VC | https://www.airtree.vc/open-source-vc/rss.xml | Blog | High |
| Blackbird blog | https://www.blackbird.vc/blog/feed | Blog | High |
| Crunchbase News AI | https://news.crunchbase.com/sections/ai/feed/ | News | Medium |
| HuggingFace papers | https://huggingface.co/api/daily_papers | API JSON | Medium |
| Y Combinator launches | https://www.ycombinator.com/launches/feed.atom | Launches | Low |

Source modules inherit from `SourceBase`. Adding a source is a single new file plus an entry in `docs/sources.md`.

## 8. Initial seed list

Bootstrap with ~50 ANZ AI companies pulled from existing research files in this folder:

- From `Top 10 Australian:NZ pre-Series A AI startups.md` and `anz-ai-startups.md`: Marqo, Composite (NZ), Kismet, SourseAI, Relevance AI, Breaker, Imitation Machines, PaperLab, Everbility, Prefactor, Alloy, Algenie, OptiGrid, Hevi, Everlab, Harrison.ai
- AirTree portfolio: Canva (excluded as too well known unless it makes sense), Linktree, Eucalyptus, Employment Hero, Immutable, Safety Culture, Go1, plus AI-flavoured AirTree portcos
- Fresh additions: Diraq, Advanced Navigation, Anduril Australia, plus others from Sam's existing research

Format: `data/seed/companies.yaml` with fields `name`, `country`, `city`, `website`, `sector_tags`, `stage`, `description_seed`. Seed script reads this and upserts into Supabase. Mark all seeded entries as `discovery_status = 'verified'`.

## 9. Sector taxonomy (v0)

Same fixed list as before, with stage values:

**Sectors:** foundation_models, ai_infrastructure, vector_search_and_retrieval, evals_and_observability, vertical_legal, vertical_healthcare, vertical_finance, vertical_sales_marketing, vertical_security, robotics_industrial, robotics_autonomous_vehicles, robotics_household, ai_for_science_biology, ai_for_science_chemistry, ai_for_science_materials, ai_for_climate_energy, defence_and_dual_use, edge_and_on_device, developer_tools, agents_and_orchestration, creative_and_media

**Stages:** pre_seed, seed, series_a, series_b_plus, mature

Editable in `docs/taxonomy.md`.

## 10. Auto-discovery flow

For each ingested news item, Claude extracts mentioned companies. For each company name not already in `companies` table:

1. **Validate.** Claude is asked: is this a real AI-native or AI-applied company? Return yes / no with reasoning.
2. **Locate.** Claude returns city and country if known. Geocoder converts to lat/lon using static ANZ city table. If outside ANZ, mark `country` accordingly.
3. **Classify.** Claude assigns sector tags from the fixed taxonomy.
4. **Summarise.** Claude writes a one-paragraph summary based on the news item plus its own knowledge.
5. **Stage and funding.** If the news item describes a funding event, extract round stage, amount, lead investor, all investors. Persist to `funding_events`.
6. **Persist.** Insert company with `discovery_status = 'auto_discovered_pending_review'`.

Pending companies do **not** appear on the public map. They show only in `90_Admin.py`. Sam reviews and either promotes to `verified` or marks `rejected`.

This keeps the public map clean while the pipeline still does the work.

## 11. Map page design

### Layout

- Full-width Streamlit page with a 70/30 split: map on the left, sidebar filters on the right.
- Below the map: a Pandas table of currently-filtered companies, sortable by name, last funding date, sector.
- A small "what's new this week" callout above the map.

### Map (streamlit-folium)

- Centred on Australia at zoom level 4.
- One marker per company, lat/lon from city lookup.
- Marker colour mapped to broad sector group (infra, vertical, robotics, science, climate, defence, dev tools).
- Marker clustering enabled to handle Sydney density.
- Popup HTML on click: company name, link, city, stage, sector tags, summary, last funding event.

### Sidebar filters

- Sector (multi-select)
- Stage (multi-select)
- Country (default ANZ only, can include global)
- Founded year range
- Search by company name

### City lookup table

Static dictionary in `src/ai_sector_watch/discovery/geocoder.py`:

```python
ANZ_CITIES = {
    "Sydney": (-33.8688, 151.2093),
    "Melbourne": (-37.8136, 144.9631),
    "Brisbane": (-27.4698, 153.0251),
    "Perth": (-31.9505, 115.8605),
    "Adelaide": (-34.9285, 138.6007),
    "Canberra": (-35.2809, 149.1300),
    "Hobart": (-42.8821, 147.3272),
    "Darwin": (-12.4634, 130.8456),
    "Newcastle": (-32.9283, 151.7817),
    "Gold Coast": (-28.0167, 153.4000),
    "Auckland": (-36.8485, 174.7633),
    "Wellington": (-41.2865, 174.7762),
    "Christchurch": (-43.5320, 172.6306),
}
```

Apply small jitter when multiple companies map to the same city so markers don't fully overlap.

## 12. Other dashboard pages

- **Companies:** filterable list view of all verified companies.
- **News:** chronological feed of relevant news items linked to companies.
- **Digest:** rendered weekly markdown digests, latest first.
- **Admin (gated by simple env-var password):** review queue for auto-discovered candidates.

## 13. Public footer (visible on every page)

> AI Sector Watch is a research project. Data is auto-extracted from public sources by an automated pipeline and may contain errors or omissions. Last updated: {date}. Built by Sam Clifton.

## 14. Scheduling

`.github/workflows/weekly.yml`:

```yaml
on:
  schedule:
    - cron: "0 18 * * 0"   # Sunday 18:00 UTC = Monday 04:00 Sydney
  workflow_dispatch:
```

Job runs `python scripts/run_weekly_pipeline.py`, requires secrets `ANTHROPIC_API_KEY` and `SUPABASE_DB_URL`. Commits weekly digest markdown to repo as a record.

Manual `workflow_dispatch` trigger available so you can run on demand from GitHub UI.

## 15. Hosting

### Dashboard

Azure App Service (Linux, Python 3.12) running `streamlit run dashboard/streamlit_app.py --server.port 8000 --server.address 0.0.0.0`.

Or Azure Container Apps if you prefer container-first. Either works.

### Custom domain

`aimap.cliftonfamily.co` (placeholder, confirm subdomain) pointed at the Azure resource via CNAME. Use Azure-managed TLS or Cloudflare in front.

### CI/CD

`.github/workflows/deploy.yml` builds and pushes on merge to `main`.

## 16. Conventions

- Python type hints everywhere
- ruff and black configured in `pyproject.toml`
- pytest, integration tests over fixture set under `tests/fixtures/`
- All secrets in env vars, never in git history
- All log lines redact tokens
- No em dashes in any user-facing output
- Idempotent operations (safe to retry)
- Single source of truth for sources in `docs/sources.md`
- Every commit updates `PROJECT_PROGRESS.md`

## 17. Credentials and environment variables

**All credentials are managed via 1Password. No bare secrets in files, ever.**

### Local dev pattern

`.env.local` contains only `op://` references, not values:

```
ANTHROPIC_API_KEY=op://Private/Anthropic API Key/credential
SUPABASE_DB_URL=op://Private/Supabase AI Sector Watch/connection_string
ADMIN_PASSWORD=op://Private/AI Sector Watch Admin/password
GITHUB_TOKEN=op://Private/GitHub PAT/token
```

Run anything that needs secrets via `op run`:

```
op run --env-file=.env.local -- python scripts/run_weekly_pipeline.py
op run --env-file=.env.local -- streamlit run dashboard/streamlit_app.py
```

The actual vault and item names are confirmed by Sam at session start. Default vault: `Private`. Claude Code should inspect `~/Projects/Home-Energy-Analysis` for existing 1Password reference patterns and ask Sam if anything is unclear.

### Non-secret env vars

```
PIPELINE_LOG_LEVEL=INFO
DIGEST_OUTPUT_DIR=./data/digests
ANTHROPIC_BUDGET_USD_PER_RUN=2
```

### GitHub Actions

For v0: secrets mirrored into GitHub repo secrets (`Settings -> Secrets and variables -> Actions`). Required:

- `ANTHROPIC_API_KEY`
- `SUPABASE_DB_URL`
- `ADMIN_PASSWORD` (only if needed at build time)

For v1: migrate to `1password/load-secrets-action@v2` with a 1Password service account token.

### Azure

For v0: `az login` interactively from local machine, deploy via Azure CLI or GitHub Actions with `azure/login@v2` using OIDC federated credentials (recommended) or a service principal stored in 1Password.

`.env.local` and `.env.example` both ignored from git via `.gitignore`. Only `.env.template` committed (showing the `op://` reference shape, not values).

## 18. Success criteria for v0

- `python scripts/verify_setup.py` passes
- `python scripts/seed_companies.py` populates ~50 companies in Supabase, all `verified`
- `python scripts/run_weekly_pipeline.py` runs end-to-end on real data, writes a digest, ingests at least 5 news items, and adds at least 1 candidate to the auto-discovery queue
- `pytest -q` passes with at least 30 tests
- Streamlit dashboard runs locally and shows the map with seeded companies
- Public deployment at chosen subdomain returns 200 and renders the map
- GitHub Actions weekly workflow set up with `workflow_dispatch` and verified once via manual trigger
- README documents setup, manual trigger, adding a source, adding a seed company

## 19. v1 scope (out of v0, document only)

- Migrate the weekly orchestrator to Anthropic Agent Skills or scheduled Claude tasks for the AirTree narrative
- Tavily or Exa for AI-native web search beyond RSS
- Email digest delivery
- Watchlist with starred companies and alerts
- Auto-generated weekly competitive briefs
- Theme-level signal scores and a heat map page
- Per-company timeline view
- Better entity resolution (fuzzy match on name and domain)
- Slack delivery

## 20. v2 scope

- LinkedIn ingestion via official API or vendor
- Streamlit replaced or augmented with a custom React frontend if styling becomes a constraint
- Real-time price-of-funding heat map
- Investor-side view: who's leading what, follow-on patterns
- Automated outreach: draft cold emails to founders surfaced as high-signal

## 21. Open questions (resolved 2026-04-27)

- Project name: `ai-sector-watch` (final, lowercase repo name; display name "AI Sector Watch")
- Project location: `/Users/samuelclifton/Documents/Projects/AI-Sector-Watch`
- Subdomain: `aimap.cliftonfamily.co` (default, confirm with Sam)
- Hosting: Azure App Service (default) or Container Apps
- Scheduling: GitHub Actions cron, weekly Sunday 18:00 UTC
- Discovery: Hybrid, with admin review queue gating public visibility
- Access: Public, no auth (footer caveat)
- Credentials: 1Password via `op` CLI (vault name to confirm at session start, default `Private`)
- Stage filters: pre_seed, seed, series_a, series_b_plus, mature
- News criteria: funding events, product launches, key hires, major partnerships
- Anthropic budget: 2 USD per run hard cap
