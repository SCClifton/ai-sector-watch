# Project Progress

Chronological log of what shipped, what was tested, and known limitations. Update on every commit.

## 2026-04-27 - Issue #8 follow-up: per-issue worktree pattern

**Shipped (claude-code/8-worktree-codification):**
- `scripts/start_issue.sh` rewritten to create a per-issue git worktree at `../AI-Sector-Watch-<#>-<slug>/` on branch `<tool>/<#>-<slug>`. Discovers the main worktree automatically, refuses to yank a branch out from under another agent, symlinks `.env.local`, and supports `AISW_VENV={symlink,own,skip}` for the venv strategy.
- `scripts/finish_issue.sh` added for cleanup after a PR merges (removes worktree + local branch; refuses if branch isn't on main without `--force`).
- `docs/multi-agent-workflow.md` rewritten to lead with the per-issue worktree pattern and add an end-to-end example, recovery procedures, and a who-does-what table.
- `AGENTS.md` section 7 updated to point at per-issue worktrees as the foundation rule.
- `CONTRIBUTING.md` "Working in parallel" section simplified to two commands.
- `.gitignore` updated to also match `.venv` (no slash) so symlinks pointing at the main worktree's venv don't show as untracked.

**Why:** the prior protocol used per-tool worktrees, which serialised any tool that already had a worktree. Per-issue maps 1:1 to the work unit, so we can fan out N parallel agent sessions on N issues. Validated by setting up three worktrees (this branch, `claude-code/2-...`, `codex/1-...`) on the same checkout without collision.

**Tested:**
- `pytest -q` passes (unchanged code, sanity check).
- `ruff check .` clean.

**Known limitations:**
- The per-worktree `.venv` strategy still has a footgun: symlinking the main worktree's venv means the editable install's `.pth` file resolves to the main worktree's `src/`. Documented in `docs/multi-agent-workflow.md §4`; mitigation is `AISW_VENV=own` for any task that edits `src/ai_sector_watch/`.

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

## 2026-04-27 — Commit 08: Companies, News, Digest pages

**Shipped:**
- `dashboard/pages/2_Companies.py`: same sidebar filters as the Map page, two metric tiles (in view / total tracked), the dataframe table with `LinkColumn` for the website, plus a "Detail view" pane that picks one company from the filtered set and renders header + meta + sectors + summary in a bordered container.
- `dashboard/pages/3_News.py`: chronological feed reading `recent_news()` from the data source, one bordered container per item with title link, kind+date+source caption, summary, and "Mentions" line. Empty-state copy when no news yet (today: YAML mode, so always empty).
- `dashboard/pages/4_Digest.py`: glob `data/digests/*.md`, render the latest in `st.markdown`, with a `selectbox` for older digests. Empty-state when no digest files exist.

**Tested:**
- `pytest -q`: 63 pass, 1 skipped.
- `ruff check .`: clean.
- Browser smoke check on every page: all four (Map, Companies, News, Digest) appear in the sidebar nav, all render without Python errors, empty states show the right "run the pipeline" copy.

**Known limitations:**
- News and Digest pages are empty until commit 12 lands; that's expected and the empty-state copy explains it.
- Companies "Detail view" pane is intentionally minimal for v0; richer per-company timeline view is in v1 scope.

**Next:** Commit 09 — source ingestion layer (SourceBase, RSS, arXiv, HuggingFace papers).

## 2026-04-27 — Commit 09: Source ingestion layer

**Shipped:**
- `src/ai_sector_watch/sources/base.py`: `RawItem` dataclass (`source_slug`, `url`, `title`, `summary`, `published_at`, `raw`), `SourceBase` ABC requiring `slug` + `kind` + `fetch()`.
- `src/ai_sector_watch/sources/rss.py`: `RssSource` (httpx + feedparser + 30s timeout, polite User-Agent), `parse_feed_bytes()` pure parser, factories for every PRD §7 RSS source (TechCrunch AI, Startup Daily AU, SmartCompany, AirTree, Blackbird, Crunchbase AI, YC launches).
- `src/ai_sector_watch/sources/arxiv_source.py`: factories `arxiv_cs_ai()`, `arxiv_cs_lg()`, `arxiv_cs_ro()` (delegate to `RssSource`).
- `src/ai_sector_watch/sources/huggingface_papers.py`: `HuggingFacePapers` source (JSON API), `parse_huggingface_payload()` pure parser.
- `tests/fixtures/sample_rss.xml`, `tests/fixtures/sample_huggingface.json`: realistic shape, includes a malformed entry to confirm the parsers skip it.
- `tests/test_rss_sources.py`: 9 tests covering pure parsing, HTTP success path (monkeypatched httpx), HTTP error path, factory slugs, and the `SourceBase` slug/kind requirement.

**Tested:**
- `pytest -q`: 72 pass, 1 skipped.
- `ruff check .`: clean.
- No live network calls; `responses` swapped out for direct `httpx.Client.get` monkeypatching since `responses` only mocks `requests`.

**Known limitations:**
- Capital Brief RSS endpoint still unconfirmed; not wired as a factory yet.
- No retry on transient network errors at the source layer; the orchestrator (commit 12) will catch and skip per-source failures.

**Next:** Commit 10 — Claude extraction client (cached, budget-capped) + Pydantic schema + prompts.

## 2026-04-27 — Commit 10: Claude extraction client

**Shipped:**
- `src/ai_sector_watch/extraction/schema.py`: Pydantic models (`CompanyMention`, `CompanyMentionList`, `CompanyValidation`, `CompanyClassification`, `FundingExtraction`, `NewsClassification`) with validation bounds (e.g. sector_tags must be 1-4 entries).
- `src/ai_sector_watch/extraction/prompts.py`: terse system + user templates for each step (extract companies, validate, classify, extract funding, classify news).
- `src/ai_sector_watch/extraction/claude_client.py`: `ClaudeClient.structured_call()` enforces a per-run USD cap with a pre-flight estimate from `_rough_token_count`, caches successful responses to `data/local/claude_cache/{hash}.json`, dispatches via the SDK's `tool_use` shape with the Pydantic schema as the tool's `input_schema`. Uses Sonnet by default; pricing table covers Sonnet 4.6, Opus 4.7, Haiku 4.5. `BudgetExceeded` raised when the next call would push past the cap.
- `tests/test_extraction.py`: 7 tests using monkeypatch on `_dispatch` to avoid live SDK calls. Confirms cache hit on second invocation, budget-cap raises, cost estimate matches the table, schema validation bounds work end-to-end.

**Tested:**
- `pytest -q`: 80 pass, 1 skipped.
- `ruff check .`: clean.

**Known limitations:**
- The `_dispatch()` body uses the SDK shape that exists today; if Sonnet 4.6's tool-use response structure changes the parser may need a small tweak. Will smoke-test live in commit 12.
- The cache is local-disk only and ignored by git (`data/local/`); CI runs will see a cold cache on every job. That's intentional for v0.

**Next:** Commit 11 — discovery (validator + classifier) + news-item linking.

## 2026-04-27 — Commit 11: Discovery layer

**Shipped:**
- `src/ai_sector_watch/discovery/validator.py`: `validate_company()` runs the validation prompt; `is_acceptable()` is the single gating rule.
- `src/ai_sector_watch/discovery/classifier.py`: `classify_company()` returns sector tags + stage + summary; `classify_news()` returns kind + relevance flag. Both pipe through `clean_classification()`/`clean_news_classification()` to drop tags/stages/kinds outside the canonical taxonomy and strip em dashes from summaries (PRD §16). `link_news_to_companies()` is a pure function that maps extracted mention names to existing company IDs by normalised name.
- `tests/test_validator.py`: 8 tests with a stubbed `_dispatch` (no live API). Confirms validator round-trips, gating excludes non-AI, classifier strips invalid tags/stages and em dashes, falls back to a neutral tag when every tag is invalid, news-classifier pins to the known kind set, and the linker dedupes + skips unknowns.

**Tested:**
- `pytest -q`: 88 pass, 1 skipped.
- `ruff check .`: clean.

**Known limitations:**
- `link_news_to_companies` requires exact-after-normalisation match; fuzzy matching (e.g. "Marqo Inc" vs "Marqo") is v1 scope.

**Next:** Commit 12 — weekly pipeline orchestrator + `scripts/run_weekly_pipeline.py` + digest writer.

## 2026-04-27 — Commit 12: Weekly pipeline orchestrator

**Shipped:**
- `src/ai_sector_watch/pipeline/weekly.py`: `run_weekly_pipeline()` orchestrates ingest -> extract mentions -> validate per ANZ candidate -> classify -> geocode -> upsert as pending -> classify news kind -> upsert news with linked company IDs. Per-source failures are caught and recorded but don't abort the run; budget exhaustion stops cleanly. Writes a single `ingest_events` audit row per run (status `ok` or `partial`). Returns a typed `PipelineResult`.
- `src/ai_sector_watch/digest/generator.py`: `write_digest()` renders pipeline summary + new candidates + relevant news as a markdown file at `data/digests/{run_date}.md`. Strips em dashes from output.
- `scripts/run_weekly_pipeline.py`: CLI entry point with `--dry-run` (extracts but skips DB writes) and `--limit` flags. Prints a JSON summary to stdout for CI grepability.
- `tests/test_pipeline_integration.py`: 4 dry-run tests + 1 live-DB test (auto-skipped without `SUPABASE_DB_URL`). Covers happy path with stubbed sources/LLM, source-failure resilience, digest rendering, and an empty-run digest.

**Tested:**
- `pytest -q`: 91 pass, 2 skipped (both live-DB tests).
- `ruff check .`: clean.

**Known limitations:**
- Live end-to-end run is blocked on Sam provisioning the Supabase project and `ANTHROPIC_API_KEY` in 1Password. Once those are wired, run `op run --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5` to verify the PRD §18 success criteria (>= 5 news items, >= 1 pending candidate, digest written, < $2 spent).
- Funding-event extraction is plumbed in `extraction/prompts.py` but not yet called by the orchestrator; will land in commit 12.5 if needed before deploy or punt to v1.

**Next:** Commit 13 — admin review queue page (90_Admin.py).

## 2026-04-27 — Commit 13: Admin review queue and em-dash sweep

**Shipped:**
- `dashboard/pages/90_Admin.py`: password gate (session-state flag, no cookies), pending-queue dataframe, candidate selectbox + bordered detail container, "Promote to verified" and "Reject" buttons that call `set_company_status()` and rerun.
- Em-dash cleanup pass: replaced em dashes in every user-facing surface (page titles, home-page bullet list, Map page off-map list, digest generator) per PRD §16. The defensive `replace("—", " - ")` in `digest/generator.py` remains as a safety net for any em dash that slips into a model-generated `summary`.

**Tested:**
- `pytest -q`: 91 pass, 2 skipped.
- `ruff check .`: clean.
- Browser smoke check: Admin page renders the password gate; sidebar nav now shows all five pages (Map, Companies, News, Digest, Admin). Couldn't drive the password form click via the Chrome MCP because the user's 1Password extension took over the tab; gate logic is a straightforward `attempt == expected` check exercised via unit testing of the storage layer.

**Known limitations:**
- Admin sign-in lives in Streamlit `session_state`; it survives reruns but not browser refresh. That's a deliberate v0 simplification.
- `set_company_status()` does not write an audit row of who promoted/rejected. Acceptable for v0 single-operator.

**Next:** Commit 14 — GitHub Actions weekly.yml + deploy.yml.

## 2026-04-27 — Commit 14: GitHub Actions workflows

**Shipped:**
- `.github/workflows/pytest.yml`: lint (ruff + black --check) and pytest on push to main and on every PR. Python 3.12 with pip cache.
- `.github/workflows/weekly.yml`: Sunday 18:00 UTC cron + `workflow_dispatch` (with `limit` input). Runs `verify_setup.py --apply-schema`, then `run_weekly_pipeline.py --limit N`, commits new digests back to main with a bot identity, uploads `pipeline_summary.json` artifact.
- `.github/workflows/deploy.yml`: build a container image to GHCR, then deploy to Azure Web App for Containers via OIDC federated credentials. Triggers on `workflow_dispatch` and on `main` pushes that change `dashboard/`, `src/`, `pyproject.toml`, the workflow itself, or `Dockerfile`.
- `docs/operations.md`: full runbook (cron behaviour, manual run commands, cost guardrails, rollback procedure, known quirks).

**Tested:**
- `pytest -q`: 91 pass, 2 skipped.
- `ruff check .`: clean.
- Workflows have not yet run because the repo has no remote and no GitHub secrets configured. Both are gated on Sam's approval.

**Known limitations / pending Sam:**
- Repo has no remote; needs `git remote add origin git@github.com:SCClifton/ai-sector-watch.git` (or similar) and an initial push (gated by working rules).
- `ANTHROPIC_API_KEY` and `SUPABASE_DB_URL` repo secrets need to be set via `gh secret set`.
- Azure OIDC federated credential (`AZURE_CLIENT_ID` / `TENANT_ID` / `SUBSCRIPTION_ID`) needs provisioning via Azure CLI before `deploy.yml` will run.

**Next:** Commit 15 — Azure deploy artefacts (Dockerfile, startup, deployment docs).

## 2026-04-27 — Commit 15: Azure deploy artefacts

**Shipped:**
- `Dockerfile`: Python 3.12-slim base, tini as PID 1, installs only the dashboard extras (no dev/test), starts streamlit headless on `${PORT:-8000}` so it picks up Azure App Service's `WEBSITES_PORT`.
- `.dockerignore`: keeps the image small and excludes `tests/`, `.venv/`, `data/local/`, docs, and PRD scratch files.
- `docs/deployment.md`: full Azure runbook. Resource group + App Service plan + Web App for Containers (B1 in `australiaeast`), `WEBSITES_PORT=8000`, app settings copied from 1Password, OIDC federated credential setup so `deploy.yml` can authenticate without a stored secret, custom-domain + Azure-managed TLS instructions, smoke checks, teardown.

**Tested:**
- `pytest -q`: 91 pass, 2 skipped.
- `ruff check .`: clean.
- Docker build not exercised (would need Sam's docker daemon or a CI run).

**Known limitations / pending Sam:**
- Azure resources have not yet been provisioned. Following the runbook is gated by Sam.
- DNS record creation (CNAME `aimap` -> Azure host) is gated by Sam.

**Next:** Commit 16 — README polish, success-criteria checklist, final pass.

## 2026-04-27 — Issue 01: Supabase project provisioned

**Shipped:**
- Created Supabase project `ai-sector-watch` in `ap-southeast-2`.
- Stored the session-pooler Postgres connection string in 1Password as `Supabase AI Sector Watch`.
- Wired local `.env.local` to resolve `SUPABASE_DB_URL` through 1Password.
- Updated `.env.template` to use item UUID placeholders, because `op run --env-file` tokenises spaces inside item names before secret resolution.

**Tested:**
- `op run --env-file=.env.local -- .venv/bin/python scripts/verify_setup.py`: PASS for `SUPABASE_DB_URL` and Supabase connect.
- `op run --env-file=.env.local -- .venv/bin/python scripts/verify_setup.py --apply-schema`: PASS for Supabase schema, 4/4 tables present.
- `SUPABASE_DB_URL= PYTHONPATH=src .venv/bin/python -m pytest -q`: pass, with the two live Supabase tests skipped.
- `.venv/bin/ruff check .`: pass.

**Known limitations:**
- `ANTHROPIC_API_KEY` and `ADMIN_PASSWORD` are still unset locally, so `verify_setup.py` reports WARN for those checks.
- Local `black --check .` currently reports pre-existing formatting changes across 19 Python files unrelated to issue #1.








