# Project Progress

Chronological log of what shipped, what was tested, and known limitations. Update on every commit.

## 2026-04-27 — Commit 01: Repo scaffold

**Shipped:**
- Project tree per PRD §6: `src/ai_sector_watch/{sources,extraction,discovery,storage,digest,pipeline}`, `dashboard/{pages,components,static}`, `scripts/`, `data/{seed,digests}`, `tests/fixtures/`, `docs/`, `.github/workflows/`.
- `pyproject.toml` pinned to Python `>=3.12,<3.14`, with `[dashboard]` and `[dev]` extras. Dependencies: `anthropic`, `feedparser`, `arxiv`, `httpx`, `psycopg[binary]`, `pydantic`, `python-dotenv`, `pyyaml`, `tenacity`. Dashboard extras: `streamlit`, `streamlit-folium`, `folium`, `pandas`. Dev extras: `pytest`, `pytest-cov`, `ruff`, `black`, `responses`.
- ruff + black configured (line length 100, py312 target). Pytest configured with `testpaths = ["tests"]`.
- `.gitignore` covers macOS, secrets, Python caches, venvs, Streamlit secrets, sqlite caches, logs.
- `.env.template` with `op://` references for `ANTHROPIC_API_KEY`, `SUPABASE_DB_URL`, `ADMIN_PASSWORD`, plus non-secret config (`PIPELINE_LOG_LEVEL`, `DIGEST_OUTPUT_DIR`, `ANTHROPIC_BUDGET_USD_PER_RUN`, `ANTHROPIC_MODEL`).
- `README.md` with quick-start, manual pipeline run, source-add and seed-add instructions, repo layout, and disclaimer.
- `AGENTS.md` mirroring the Home-Energy-Analysis tone for working conventions.
- Empty `__init__.py` files in every `src/ai_sector_watch/` subpackage.
- `.venv` built from Homebrew Python 3.12.13.

**Tested:**
- `pip install -e ".[dashboard,dev]"` succeeds in the venv.
- `pytest -q` runs (zero tests, zero failures).
- `ruff check .` passes.

**Known limitations:**
- No code yet beyond package init files. Storage, dashboard, pipeline all empty.
- `op signin` not yet run; nothing requires secrets at this commit.
- No git remote yet; no commits pushed.

**Next:** Commit 02 — static config + ANZ geocoder + sector taxonomy + initial docs.

## 2026-04-27 — Commit 02: Config, geocoder, taxonomy, docs

**Shipped:**
- `src/ai_sector_watch/config.py`: typed `Config` dataclass, env-var loader (auto-loads `.env.local` if present), `configure_logging()` helper.
- `src/ai_sector_watch/discovery/geocoder.py`: 19-city ANZ static lookup, deterministic SHA256-based jitter (~1km radius) keyed by company name so co-located markers spread without moving across reloads. Returns `GeocodeResult` dataclass; `None` for unknown cities.
- `src/ai_sector_watch/discovery/taxonomy.py`: 21 sector tags grouped into 9 colour bands (per PRD §11), 5 stage values, helpers (`is_valid_sector`, `colour_for_sector`, `primary_sector_colour`).
- `docs/sources.md`: canonical source list with URL, type, ANZ relevance.
- `docs/taxonomy.md`: human-readable mirror of the Python taxonomy with colour table and add-a-sector instructions.

**Tested:**
- `pytest -q`: 26 tests pass (geocoder: 9, taxonomy: 9, config: 3, smoke: 1, plus parametrised cities).
- `ruff check .`: clean.

**Known limitations:**
- Capital Brief RSS endpoint still TBC; flagged in `docs/sources.md`.
- Geocoder is ANZ-only by design; non-ANZ companies will return None and won't appear on the map until v1.

**Next:** Commit 03 — Supabase schema and `storage/supabase_db.py` (psycopg, retries, idempotent upserts).

## 2026-04-27 — Commit 03: Supabase schema and storage layer

**Shipped:**
- `src/ai_sector_watch/storage/supabase_schema.sql`: idempotent schema (DO blocks, IF NOT EXISTS) for `companies`, `funding_events`, `news_items`, `ingest_events`, with enums `discovery_status`, `company_stage`, `news_kind`. Unique indexes on `(name_normalised, country)` for companies and `url_hash` for news items. GIN indexes on `sector_tags` and `company_ids`. `updated_at` trigger on companies.
- `src/ai_sector_watch/storage/supabase_db.py`: psycopg 3 client. `get_conn()` retries 6 times with exponential backoff (0.5s -> 8s); `dict_row` row factory. Functions: `apply_schema`, `compute_payload_hash`, `hash_url`, `normalise_name`, `upsert_company`, `set_company_status`, `get_company_by_name`, `list_companies`, `upsert_funding_event`, `upsert_news_item`, `insert_ingest_event`. All upserts are idempotent and never downgrade `verified` companies back to `pending`.
- `scripts/verify_setup.py`: smoke check for Python version, all required env vars, digest dir, Supabase connect, and table presence. Supports `--apply-schema` to apply the schema.

**Tested:**
- `pytest -q`: 33 pass, 1 skipped (the live-DB round-trip auto-skips without `SUPABASE_DB_URL`).
- `ruff check .`: clean.
- `python scripts/verify_setup.py` runs end-to-end without secrets and reports the expected mix of PASS/WARN/FAIL.

**Known limitations:**
- Live integration test for upsert/round-trip still skipped pending Sam's new Supabase project + populated `.env.local`.
- No funding-event or news-item live tests yet; they'll land alongside the pipeline in commit 12.

**Next:** Commit 04 — `data/seed/companies.yaml` (~50 ANZ AI co's) + `scripts/seed_companies.py`.

## 2026-04-27 — Commit 04: Seed list and seeder script

**Shipped:**
- `data/seed/companies.yaml`: 52 hand-curated ANZ AI companies covering pre-seed agents and discovery, AirTree-portfolio scaleups, NZ ecosystem (Soul Machines, Halter, Tracksuit, Auror, Partly), and key infrastructure/tooling players. Each entry has name, country, city, website, sector_tags, stage, optional founded_year, and a 1-3 sentence summary (no em dashes).
- `scripts/seed_companies.py`: loads YAML, runs static validation against geocoder + taxonomy + em-dash rule, then idempotently upserts each entry as `discovery_status = 'verified'` with `discovery_source = 'seed'`. Coordinates jittered per company name. Supports `--dry-run` to validate without DB writes.
- `tests/test_seed_companies.py`: confirms ≥50 entries, every entry validates, no duplicates, AU+NZ coverage; positive guards on em-dash and unknown-sector detection.

**Tested:**
- `pytest -q`: 39 pass, 1 skipped (live DB still gated on SUPABASE_DB_URL).
- `ruff check .`: clean.
- `python scripts/seed_companies.py --dry-run`: 52 entries, validation passes.

**Known limitations:**
- Live `python scripts/seed_companies.py` (no `--dry-run`) still gated on Sam's new Supabase project.
- Sourcegraph included with caveat in description; will be reviewed for ANZ-relevance in admin queue once Sam wires Supabase.

**Next:** Commit 05 — Streamlit shell, page router, footer, Supabase read client.

## 2026-04-27 — Commit 05: Dashboard shell

**Shipped:**
- `src/ai_sector_watch/storage/data_source.py`: `Company` and `NewsItem` dataclasses, `DataSource` Protocol, `SupabaseSource` (production), `YamlSource` (local-dev fallback that reads `data/seed/companies.yaml`), and `get_data_source()` factory. Falls back to YAML when `SUPABASE_DB_URL` is unset; `AISW_FORCE_YAML=1` forces YAML regardless.
- `dashboard/streamlit_app.py`: page-config setup, headline metrics (companies tracked, AU count, NZ count), banner that flags YAML mode in dev, "how to use" intro.
- `dashboard/components/footer.py`: PRD §13 footer with auto-dated "Last updated" string.

**Tested:**
- `pytest -q`: 45 pass, 1 skipped.
- `ruff check .`: clean.
- `streamlit run dashboard/streamlit_app.py` (headless on :8765): root returns HTTP 200, no Python-side errors in logs, page metrics show 52 / AU=46 / NZ=6.

**Known limitations:**
- The Streamlit "pages/" multi-page nav lights up automatically once the per-page files land in commits 06-08; the shell currently shows only the home view.

**Next:** Commit 06 — Map page (folium markers, sector colour, clustering, popup, jitter).

## 2026-04-27 — Commit 06: Map page

**Shipped:**
- `dashboard/components/map_view.py`: `build_map(companies)` returns a folium Map centred on south-east Australia at zoom 4 with carto-positron tiles, MarkerCluster grouping, sector-coloured icons, and click-through popup HTML (name + link + city + stage + founded + sector chips + summary). `_popup_html` strips em dashes per PRD §16. `split_geocoded()` partitions companies that can vs cannot be plotted.
- `dashboard/pages/1_Map.py`: Streamlit page with title, helper caption, dev-mode banner, three metric tiles (on map / tracked / awaiting geocoding), the folium map at 620px height, and an expander listing companies without coords.
- Fix: added `REPO_ROOT` to `sys.path` in both `dashboard/streamlit_app.py` and `dashboard/pages/1_Map.py` so the `dashboard.components.*` imports resolve when Streamlit runs each page.

**Tested:**
- `pytest -q`: 52 pass, 1 skipped (added 7 map_view tests).
- `ruff check .`: clean.
- Browser smoke check via Claude in Chrome MCP: page renders with 52 markers clustered around Sydney (26+14), Melbourne, Brisbane (4), Perth, and NZ (6). Sidebar nav shows the Map page entry.

**Known limitations:**
- Marker colours derive from the first sector tag; map currently has no legend (deferred).
- Popup HTML is built as a string; if a company name ever contained a stray `<` it would break the popup. Acceptable for v0 with curated seed data; will harden in v1.

**Next:** Commit 07 — sidebar filters + companies table below the map.

## 2026-04-27 — Commit 07: Sidebar filters and companies table

**Shipped:**
- `dashboard/components/filters.py`: `FilterState` and `FilterMeta` frozen dataclasses, `derive_meta()` to compute country list and year bounds from the loaded set, `render_sidebar()` to produce the multi-selects + slider + text input, `apply_filters()` pure function (sector / stage / country / founded-year window / case-insensitive name substring), `companies_to_table_rows()` formatter.
- Map page now: derives meta from full company list, renders sidebar filters (defaults to AU+NZ), filters before splitting into geocoded/not, four metric tiles (on map / in view / total / awaiting), Pandas dataframe with `LinkColumn` for the website, and a "no companies match" empty state.

**Tested:**
- `pytest -q`: 63 pass, 1 skipped (added 11 filter tests).
- `ruff check .`: clean.
- Browser smoke check: with no filters → 52 / 52 / 52 / 0; selecting "Foundation models" sector → 1 / 1 / 52 / 0 with a single pink marker in Sydney (Leonardo.Ai). Country chips for AU+NZ appear pre-selected. Year slider auto-bounds to actual founded years (2002-2023).

**Known limitations:**
- The founded-year filter currently keeps companies with no `founded_year` (treats unknown as "could match") to avoid silently hiding 30+ entries; revisit once seed data is more complete.

**Next:** Commit 08 — Companies page + News page + Digest page.






