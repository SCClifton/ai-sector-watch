---
description: Pre-flight an issue (existing or new), enter its worktree, do the work, open a Draft PR.
argument-hint: <free-form narration; mention an issue number to skip drafting>
---

You are starting work on a GitHub issue in the AI-Sector-Watch repo. Operating manual: `AGENTS.md`. Worktree protocol: `docs/multi-agent-workflow.md`. Both are authoritative — re-read if you are unsure.

This command is tool-agnostic. The default tool name is `claude-code` because this file lives at `.claude/commands/issue.md`. The mirror file `.codex/prompts/issue.md` defaults to `codex`. If you are a different agent and reading this body directly, substitute `<TOOL>` with your own short identifier (e.g. `human`, `gemini`).

The user's narration:

$ARGUMENTS

## Step 1 — classify the narration

Scan `$ARGUMENTS` for an issue reference: `#123`, `issue 123`, `issue #123`. If found, treat 123 as `<#>` and skip to Step 3. Otherwise this is a new issue — go to Step 2.

If the narration explicitly names a tool to use (e.g. "use codex", "as human", "tool: gemini"), record that as `<TOOL>` for Step 3. Otherwise `<TOOL>` defaults to `claude-code` from this file.

## Step 2 — draft and create the issue (new-issue path only)

1. Pick the right template from `.github/ISSUE_TEMPLATE/`:
   - `bug_report.md` if the narration describes broken behaviour.
   - `data_correction.md` if it is about a wrong company entry on the map.
   - `feature_request.md` otherwise (default).
2. Draft a title (use the template's `title:` prefix — `[bug] `, `[feature] `, or `[data] `) and a body that fills every section of the template. Keep it terse and active. Do not add fields the template does not have.
3. Show the user the proposed title and body and ask: "Create this issue? (y/n, or edits)". Do not proceed without explicit confirmation.
4. On confirm, run `gh issue create --title "<title>" --body "<body>" --label "<template-label>"`. Capture the issue number from the URL it prints. Set `<#>` to that number.

## Step 3 — pre-flight

Idempotency check first. From any working directory:

    git worktree list --porcelain | grep -E "branch refs/heads/.+/<#>-" | head -1

If a worktree already exists for this issue, parse its directory from `git worktree list` and skip to Step 4. Otherwise:

    scripts/start_issue.sh <#> <TOOL>

This must be run from a directory inside the repo (any worktree is fine — it discovers the main worktree automatically). The script self-assigns the issue, creates the per-issue worktree on branch `<TOOL>/<#>-<slug>`, symlinks `.env.local`, and moves the Project card to In Progress. Read its stdout: the `==> Worktree:` line is the absolute path of the new worktree. Capture it as `<WT>`.

If `start_issue.sh` fails: stop, surface the error, ask the user. Do not improvise the manual fallback unless explicitly told to.

If the task touches `src/ai_sector_watch/`, set `AISW_VENV=own` in the environment before invoking the script so the worktree gets its own venv (the editable install path otherwise resolves to the main worktree's `src/`).

## Step 4 — enter the worktree

Every subsequent shell command must run with `<WT>` as its working directory. `cd` does not persist between Bash tool calls — pass absolute paths or chain with `&&` inside a single call:

    cd <WT> && <command>

Verify you are in the right place once: `cd <WT> && git rev-parse --show-toplevel && git branch --show-current`. The branch must be `<TOOL>/<#>-<slug>`. If you ever see `main` here, stop — you are in the main worktree and committing is forbidden.

## Step 5 — do the work

Follow `AGENTS.md` strictly. Hard rules from §3 and §4:

- No secrets in the diff. `.env.local` is the only secrets file and it is gitignored. For commands that need secrets: `op run --env-file=.env.local -- <cmd>`.
- LLM dev runs cap at $1; the runtime cap is $2 via `ANTHROPIC_BUDGET_USD_PER_RUN`. Do not bypass.
- Type hints everywhere. `ruff check .` and `black --check .` must pass.
- No em dashes in user-facing copy (digest markdown, dashboard, popup HTML). Docstrings can use them.
- One concern per commit. Conventional Commits: `<type>(<scope>): <subject>`, subject ≤ 72 chars. No AI attribution trailers — the commit hook rejects them.
- Update `PROJECT_PROGRESS.md` only if this change is a milestone (closes a Now/Next issue, ships a public feature, or breaks something). For everything else the PR body is the record.

Stop and ask before any of these:
- Choosing a different stack than Streamlit + Supabase + Anthropic + GitHub Actions + Azure.
- Adding a data source not already in `docs/sources.md`.
- A test or dev run that would spend more than $1 of LLM quota.
- Pushing when the local commit has not been reviewed.
- Provisioning Azure, changing DNS, creating a secret-manager item, creating a Supabase project.
- Force-pushing or rewriting history on `main`.

After your code change runs green locally:

    cd <WT> && .venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/black --check .

Commit:

    cd <WT> && git add <specific files> && git commit -m "<conventional message>"

## Step 6 — push and open a Draft PR

    cd <WT> && git push -u origin HEAD
    cd <WT> && PR_BODY="$(mktemp)" && cp .github/pull_request_template.md "$PR_BODY" && printf "\nCloses #%s\n" "<#>" >> "$PR_BODY" && gh pr create --draft --title "[#<#>] <issue title>" --body-file "$PR_BODY"

Use the issue title verbatim from `gh issue view <#> --json title -q .title`.

## Reporting back

When you finish a step, state the result in one line. Do not recap the rules. If you hit a "stop and ask" boundary or a script failure, stop immediately and surface what you saw.
