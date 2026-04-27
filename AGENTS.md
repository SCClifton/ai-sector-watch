# AGENTS.md

Operating manual for any human or AI agent working in this repo. Read this before you write code.

**Last updated:** 2026-04-27

---

## 1. What this project is

A live, public-facing ecosystem map of the Australian and New Zealand AI startup landscape, updated weekly by an automated agent pipeline.

- **Public dashboard:** Streamlit + streamlit-folium, hosted on Azure App Service at `aimap.cliftonfamily.co`.
- **Storage:** Supabase Postgres. The dashboard reads live; the pipeline writes.
- **Pipeline:** Python 3.12 + Anthropic SDK + feedparser. Runs weekly via GitHub Actions cron.
- **Discovery flow:** every news item is read by an LLM that extracts company mentions. New ANZ candidates are validated, classified against a fixed sector taxonomy, geocoded against a static city table, and written as `auto_discovered_pending_review`. Verified companies appear on the public map; pending ones never do.

For the architecture diagram and the full repo layout, see [README.md](README.md).

## 2. Sources of truth

When you're not sure where the canonical answer lives:

| Question | File |
|---|---|
| What is this project, top to bottom? | [README.md](README.md) |
| What got built and when? | [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) |
| What sources do we ingest? | [docs/sources.md](docs/sources.md) |
| What sectors and stages exist? | [docs/taxonomy.md](docs/taxonomy.md) |
| How does the cron and digest work? | [docs/operations.md](docs/operations.md) |
| How is Azure set up? | [docs/deployment.md](docs/deployment.md) |
| What does the data model look like? | [src/ai_sector_watch/storage/supabase_schema.sql](src/ai_sector_watch/storage/supabase_schema.sql) |
| What does the orchestrator do? | [src/ai_sector_watch/pipeline/weekly.py](src/ai_sector_watch/pipeline/weekly.py) |

If two sources of truth disagree, fix the disagreement in the same commit. Don't paper over it.

## 3. Non-negotiables

These are hard rules. If a task seems to require breaking one, stop and ask.

1. **Never commit secrets.** `.env.local` is gitignored. Only `.env.template` (which holds `op://` references, not values) is in the repo. Run secret-bearing commands via `op run --env-file=.env.local -- <cmd>`.
2. **Public map only shows verified companies.** `discovery_status = 'verified'` is the gate. Auto-discovered candidates wait in the admin queue at `/Admin`.
3. **Idempotent operations.** Every upsert keys on a stable hash (URL hash for news, normalised name + country for companies, payload hash for ingest events). Reruns must be safe.
4. **UTC at storage boundaries.** Local time is for human-facing surfaces only.
5. **LLM spend cap.** `ANTHROPIC_BUDGET_USD_PER_RUN` (default $2) is enforced in `extraction/claude_client.py`. Don't bypass it. Don't raise it without a reason.
6. **Type hints everywhere.** `ruff check .` and `black --check .` run in CI.
7. **No em dashes in user-facing output.** Digest markdown, dashboard copy, popup HTML. Use a colon, comma, or " - " instead. Docstrings are fine.
8. **Update `PROJECT_PROGRESS.md` in every commit** that ships shipped functionality.

## 4. Stop and ask before

- Choosing a different stack than the one already in place (Streamlit + Supabase + Anthropic + GitHub Actions + Azure).
- Adding a data source that isn't in [`docs/sources.md`](docs/sources.md).
- Spending more than $1 of LLM quota in a single test or development run.
- Pushing to GitHub when the local commit hasn't been reviewed.
- Provisioning any Azure resource.
- Pointing or changing a DNS record.
- Creating a new 1Password item or a new Supabase project.
- Force-pushing or rewriting history on `main`.

## 5. Repo conventions

### Code

- **Python 3.12.** Pinned in `pyproject.toml` as `requires-python = ">=3.12,<3.14"`. Build a `.venv` from `python3.12 -m venv .venv`.
- **Package layout.** All importable code lives under `src/ai_sector_watch/`. The dashboard scripts under `dashboard/` add `REPO_ROOT` and `REPO_ROOT/src` to `sys.path` at the top of each entry point so Streamlit can resolve them.
- **Lint.** `ruff` and `black` configured in `pyproject.toml` with `line-length = 100`. CI fails on either.
- **Tests.** `pytest`, fixture-driven for anything external. HTTP fetches are mocked by monkeypatching `httpx.Client.get` (we don't use the `responses` library because it only mocks `requests`). Live-DB tests auto-skip when `SUPABASE_DB_URL` is unset.

### Commits

- One concern per commit.
- Conventional Commits format: `<type>(<scope>): <subject>` (e.g. `feat(dashboard): add filters`). Subject line ≤ 72 chars.
- Commit hooks reject AI-tool attribution (`Co-Authored-By: Claude ...`, `Generated with ...`). Don't add those.
- Each commit either runs green tests or documents the manual smoke check that was performed.
- Update `PROJECT_PROGRESS.md` in the same commit.

### Branching

- Trunk-based. Work directly on `main` for now (single-operator project). Feature branches when a change is non-trivial enough to want a pre-merge review.

### Style

- Terse, sharp, active voice. No filler.
- Doc strings on every public function and class. Single-line is fine when the signature is self-documenting.
- Helper docstrings can use em dashes; user-facing copy cannot.

## 6. How to do common things

### Add a data source

1. New module under `src/ai_sector_watch/sources/<slug>.py`. Subclass `SourceBase`. Implement `fetch(limit)` returning `list[RawItem]`.
2. Append a row to [`docs/sources.md`](docs/sources.md).
3. Register the factory in `default_sources()` in [`src/ai_sector_watch/pipeline/weekly.py`](src/ai_sector_watch/pipeline/weekly.py).
4. Add a fixture-driven test under [`tests/test_rss_sources.py`](tests/test_rss_sources.py).

### Add a seed company

1. Append a YAML block to [`data/seed/companies.yaml`](data/seed/companies.yaml). Schema is documented at the top of the file.
2. `python scripts/seed_companies.py --dry-run` to validate.
3. `op run --env-file=.env.local -- python scripts/seed_companies.py` to apply (idempotent).

### Add a sector tag

1. Add a `Sector(...)` entry to `SECTORS` in [`src/ai_sector_watch/discovery/taxonomy.py`](src/ai_sector_watch/discovery/taxonomy.py). Pick an existing colour group or add a new one to `_GROUP_COLOURS`.
2. Mirror the change in [`docs/taxonomy.md`](docs/taxonomy.md).
3. The SQL stores `sector_tags` as `TEXT[]`, so no migration is needed.
4. `pytest tests/test_taxonomy.py`.

### Promote / reject an auto-discovered company

Open the `/Admin` page (password-gated by `ADMIN_PASSWORD`). The pipeline writes new candidates as `auto_discovered_pending_review`. Promote moves them to `verified` (visible on the public map). Reject keeps them in the DB but never surfaces them.

### Run tests

```bash
pytest -q
ruff check .
black --check .
```

### Trigger the weekly pipeline manually

```bash
op run --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5
# or
gh workflow run weekly.yml -f limit=5
```

## 7. Tone for AI agents

Sam is an experienced operator with a deep tech and ML background. Write terse and sharp. Default to action; explain only when the action is non-obvious. Don't apologise. Don't editorialise. Don't add filler. State results and decisions directly.

When in doubt: read the file, fix the bug, write the test, ship the diff.
