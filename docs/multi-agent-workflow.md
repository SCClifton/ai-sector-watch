# Multi-agent workflow

How multiple AI tools (Claude Code, Codex, future agents) and humans share this repo without stepping on each other.

**Last updated:** 2026-04-27

---

## The problem

Two AI tools running on the repo at the same time can collide at four levels:

| Level | Failure mode |
|---|---|
| **Same file edits** | Both edit `pipeline/weekly.py`; the second push silently overwrites the first. |
| **Same issue** | Both pick up #5 thinking it's free; duplicate work, conflicting designs. |
| **Shared remote state** | Both run live pipeline, both apply schema migrations, both touch Azure. |
| **Stale main** | One tool starts from yesterday's `main`, ships a regression of work the other tool merged this morning. |

This document is the protocol that prevents each one.

---

## The protocol

### 1. Issue assignment is the lock

Every code change starts from a GitHub issue. Before writing code, the agent **must** self-assign the issue. If it's already assigned to someone else, pick a different issue.

```bash
# Confirm it is unassigned (or assigned to you)
gh issue view <#> --json assignees -q '.assignees'

# Claim it
gh issue edit <#> --add-assignee @me
```

The Project board's **Workflow** single-select field tracks lifecycle:

- `Backlog` — not started
- `In Progress` — actively being worked on
- `In Review` — PR is open, waiting on Sam
- `Done` — merged

Move the card on every transition. `In Progress` is the human-readable signal that pairs with the issue assignment.

### 2. Branch naming convention

```
<tool>/<issue-number>-<short-slug>
```

Examples:

- `claude-code/4-live-pipeline`
- `codex/8-sector-legend`
- `human/12-firecrawl-spec`

Why: when you run `git branch` or look at the PR list, ownership is obvious without opening the issue.

### 3. The pre-flight (mandatory, every time)

```bash
# 1. Latest main
git fetch
git checkout main
git pull --rebase

# 2. Confirm the issue is yours
gh issue view <#> --json assignees -q '.assignees'

# 3. Claim if not yet
gh issue edit <#> --add-assignee @me

# 4. Move Project status to In Progress (Web UI or via gh project item-edit)

# 5. Branch
git checkout -b <tool>/<#>-<slug>

# 6. After the first commit, open a Draft PR
gh pr create --draft --title "[<#>] <title>" --body "Closes #<#>"
```

Use [`scripts/start_issue.sh <issue-number>`](../scripts/start_issue.sh) to do all of this in one shot.

### 4. Branch protection (enforced by GitHub)

The `main` branch has the following rules:

- **No direct pushes.** Every change goes through a PR.
- **CI must pass** before merge (the `test` job from `.github/workflows/pytest.yml`).
- **Branches must be up to date** with `main` before merge (forces rebase).
- **No force-push.** Trying it returns an error.
- **No branch deletion.**
- **Linear history** required.

Sam can override in genuine emergencies (admin bypass), but should not as a matter of course. If you find yourself wanting to bypass, stop and ask.

### 5. Live infrastructure coordination

Code changes are tracked by branches and PRs. **Live operations** (Azure provisioning, DNS edits, Supabase schema migrations, GitHub repo settings) are not. For these:

1. Open a Draft PR (or comment on the relevant issue) **before** running the operation, with a "Starting <operation> at <UTC time>" line.
2. Run the operation.
3. Comment when done.

This is a soft signal but it works because there are at most two AI tools and one human in the loop. If we ever scale beyond that, we'll add a real lock service.

The "stop and ask before" gates in [AGENTS.md §4](../AGENTS.md#4-stop-and-ask-before) still apply on top of this — coordination is *additional* to those, not a replacement.

### 6. PR review and merge

- Use the PR template ([.github/pull_request_template.md](../.github/pull_request_template.md)). The "Conflicts checked" box is mandatory.
- AIs do not auto-merge. **Sam is the merger.**
- Sam squash-merges by default to keep `main` history linear and readable.
- After merge, the AI: deletes the feature branch, moves the Project card to `Done`, closes any auxiliary subtasks.

---

## Conflict recovery

### "I started work but someone else already opened a PR for this issue"

Stop. Comment on the existing PR offering to help, or move to a different issue.

### "My branch has merge conflicts with main"

```bash
git fetch origin
git rebase origin/main
# resolve conflicts in your editor
git add <resolved files>
git rebase --continue
git push --force-with-lease
```

`--force-with-lease` is allowed on feature branches (just not on `main`). It's safer than `--force` because it refuses to overwrite work you haven't seen.

### "CI is failing on my PR but the failure looks unrelated to my change"

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease
```

Often the failure is from a flaky test or a dependency that updated since you branched. Rebase on latest `main` and let CI rerun.

### "I made a commit straight to main by accident"

Branch protection should have prevented this. If you somehow got past it:

```bash
git checkout main
git pull --rebase
# if your commit is gone (someone else pushed past it), redo on a branch
git checkout -b <tool>/<#>-<slug>
git cherry-pick <your-commit-sha>
git push -u origin HEAD
gh pr create --draft
```

If your commit is still on `main` and was pushed: stop, message Sam.

### "Two PRs have file conflicts with each other"

Whoever opened first owns the merge. The second PR rebases after the first lands. If the first PR is stalled (>1 day with no movement), the second PR can take over after commenting on the first issue to claim ownership.

---

## Who does what

The default mapping (tweak per task):

| Task shape | Best tool |
|---|---|
| Multi-step runbook (cloud, shell, browser MCP) | Claude Code |
| Multi-file refactor or new module across many files | Claude Code |
| Live verification with screenshot evidence | Claude Code (browser MCP) |
| Single-file feature with tests | Codex |
| Idiomatic Python refactor in a known surface | Codex |
| Adding a Pydantic schema or a fixture-driven test | Codex |
| Writing or reviewing prose / docs | Either; Claude Code is slightly better at long prose |
| Anything that creates or rotates a credential | Sam (never the AI) |

When in doubt, the issue itself can tag the suggested tool: add a label like `for-claude-code` or `for-codex`. AIs check the label as part of the pre-flight.

---

## Boundaries

The protocol covers code in this repo. It does **not** cover:

- Anthropic / OpenAI conversation history (that's per-tool, not shared).
- Local development state on Sam's laptop (Sam is one person; no need).
- Secrets or 1Password items (only Sam touches these).

If you find yourself wanting a coordination mechanism the protocol doesn't have, propose it as an issue with the `infra` label.
