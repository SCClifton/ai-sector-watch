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
