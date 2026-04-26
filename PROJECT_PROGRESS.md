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

