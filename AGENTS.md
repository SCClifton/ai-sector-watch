# AGENTS.md

Operating manual for any human or AI agent working in this repo. Read this before you write code.

**Last updated:** 2026-04-28

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

1. **Never commit secrets.** `.env.local` is gitignored. Only `.env.template` (which holds `op://` references, not values) is in the repo. Run secret-bearing commands via `op run --account my.1password.com --env-file=.env.local -- <cmd>`.
2. **Public map only shows verified companies.** `discovery_status = 'verified'` is the gate. Auto-discovered candidates wait in the admin queue at `/Admin`.
3. **Idempotent operations.** Every upsert keys on a stable hash (URL hash for news, normalised name + country for companies, payload hash for ingest events). Reruns must be safe.
4. **UTC at storage boundaries.** Local time is for human-facing surfaces only.
5. **LLM spend cap.** `ANTHROPIC_BUDGET_USD_PER_RUN` (default $2) is enforced in `extraction/claude_client.py`. Don't bypass it. Don't raise it without a reason.
6. **Type hints everywhere.** `ruff check .` and `black --check .` run in CI.
7. **No em dashes in user-facing output.** Digest markdown, dashboard copy, popup HTML. Use a colon, comma, or " - " instead. Docstrings are fine.
8. **Update `PROJECT_PROGRESS.md` only for milestones** (closing a Now/Next issue, shipping a public feature, breaking something publicly). For everything else, the PR body is the record. This keeps parallel PRs from serially conflicting on the same file.

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
- Update `PROJECT_PROGRESS.md` in the same commit only for milestones.

### Branching

- Trunk-based through per-issue worktrees. Do not commit directly on `main`; branch from `origin/main` with `scripts/start_issue.sh`.

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
3. `op run --account my.1password.com --env-file=.env.local -- python scripts/seed_companies.py` to apply (idempotent).

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
op run --account my.1password.com --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5
# or
gh workflow run weekly.yml -f limit=5
```

## 7. Multi-tool coordination

Multiple AI tools (Claude Code, Codex, future agents) work in this repo concurrently. **Each active issue gets its own git worktree.** That is the foundation; everything else builds on it. Full detail and recovery procedures live in [docs/multi-agent-workflow.md](docs/multi-agent-workflow.md).

### One worktree per issue

The repo lives in `~/Documents/Projects/AI-Sector-Watch/` (the "main worktree", on `main`, used by Sam for reading and coordinating). Every active issue gets a sibling directory:

```
~/Documents/Projects/
├── AI-Sector-Watch/                    # main, reading/coordinating only
├── AI-Sector-Watch-1-supabase/         # one agent on issue #1
├── AI-Sector-Watch-2-wire-op-refs/     # another agent on issue #2
├── AI-Sector-Watch-4-pipeline/         # another agent on issue #4
└── ...
```

All siblings share the same `.git/`. They have isolated working trees, so two agents editing files at the same time never collide. The directory disappears when the PR merges.

**Never commit from the main worktree.** Always work in a per-issue worktree.

### Pre-flight (one command)

```bash
scripts/start_issue.sh <issue-number> [tool-name]
```

That script verifies the issue is open and unassigned, claims it, creates the per-issue worktree at `../AI-Sector-Watch-<#>-<slug>/` on branch `<tool>/<#>-<slug>`, symlinks `.env.local`, and prints the next steps. Run it from any existing worktree (it discovers the main worktree automatically).

If the script ever fails, the manual fallback is documented in [docs/multi-agent-workflow.md §3](docs/multi-agent-workflow.md).

### Agent slash command (optional)

A tool-neutral runbook for the full pre-flight → work → Draft PR loop lives at `.claude/commands/issue.md` (Claude Code) and `.codex/prompts/issue.md` (Codex). Bodies are identical apart from the default tool name. Invoke as `/issue <free-form narration>` — pass an issue number to skip drafting, or describe a new task to have it drafted via the right `.github/ISSUE_TEMPLATE/`. To wire up another agent (Gemini, etc.), copy either body into that agent's prompts directory and change the default tool name in the meta paragraph.

### Branch and merge rules

- **No direct commits to `main`.** Branch protection enforces this.
- **PR must pass CI** (`pytest.yml`) before merge.
- **One human merger** (Sam). AIs do not auto-merge.
- **No force-push to `main`.** Branch protection rejects it. If history rewrite is unavoidable, ask Sam.
- Rebase on `main` before opening a PR for review.
- After merge, run `scripts/finish_issue.sh <#>` to remove the worktree and delete the local branch.

### Live infrastructure coordination

For changes that touch shared remote state (Azure resources, DNS records, Supabase schema migrations, GitHub repo settings), an in-flight signal is required. Open a draft PR or comment on the relevant issue *before* running the operation. The "stop and ask before" gates in §4 still apply.

### When two PRs overlap

Whoever opens their PR first owns the file conflict resolution. The second PR rebases. If the first PR is stalled (>1 day with no movement), the second PR can take over after commenting on the first issue to claim ownership.

## 8. Tone for AI agents

Sam is an experienced operator with a deep tech and ML background. Write terse and sharp. Default to action; explain only when the action is non-obvious. Don't apologise. Don't editorialise. Don't add filler. State results and decisions directly.

When in doubt: read the file, fix the bug, write the test, ship the diff.
