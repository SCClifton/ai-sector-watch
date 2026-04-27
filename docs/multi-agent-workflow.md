# Multi-agent workflow

How multiple AI tools (Claude Code, Codex, future agents) and humans share this repo without stepping on each other.

**Last updated:** 2026-04-27

---

## The problem

Two AI tools running on the repo at the same time can collide at five levels:

| Level | Failure mode |
|---|---|
| **Same working directory** | Tool A runs `git checkout codex/...` and instantly yanks Tool B's branch out from under it. Branches are pointers; the working tree is a single mutable filesystem state. |
| **Same file edits** | Both edit `pipeline/weekly.py`; the second push silently overwrites the first. |
| **Same issue** | Both pick up #5 thinking it's free; duplicate work, conflicting designs. |
| **Shared remote state** | Both run live pipeline, both apply schema migrations, both touch Azure. |
| **Stale main** | One tool starts from yesterday's `main`, ships a regression of work the other tool merged this morning. |

This document is the protocol that prevents each one.

---

## The protocol, top to bottom

### 0. One worktree per issue (the foundation)

This is the most important rule. Every active issue gets its **own git worktree** — a dedicated directory on disk with its own working tree, sharing the same `.git/` so commits, branches, and refs are unified.

```
~/Documents/Projects/
├── AI-Sector-Watch/                      # main worktree (Sam's reading/coordination tree)
├── AI-Sector-Watch-1-supabase/           # one agent on issue #1
├── AI-Sector-Watch-2-wire-op-refs/       # another agent on issue #2
├── AI-Sector-Watch-4-pipeline/           # another agent on issue #4
└── ...                                   # one per active issue
```

Why per-issue (not per-tool):
- Maps 1:1 to the unit of work. Easier to reason about.
- Sam can fan out N parallel agent sessions on N issues.
- The directory disappears when the PR merges (`scripts/finish_issue.sh <#>`), so the filesystem stays clean.
- A `cd` into the worktree is the entire context switch.

The main worktree (`AI-Sector-Watch/`) stays on `main` and is for reading the codebase and coordinating. **No agent should commit from the main worktree.** If you find yourself wanting to, branch out into a fresh worktree first.

### 1. Issue assignment is the lock

Every code change starts from a GitHub issue. Before writing code, the agent **must** self-assign the issue. If it's already assigned to someone else, pick a different issue.

```bash
# Confirm it is unassigned (or assigned to you)
gh issue view <#> --json assignees -q '.assignees'

# Claim it
gh issue edit <#> --add-assignee @me
```

The Project board's **Workflow** single-select field tracks lifecycle:

- `Backlog` - not started
- `In Progress` - actively being worked on
- `In Review` - PR is open, waiting on Sam
- `Done` - merged

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

The worktree directory mirrors the issue+slug:

```
AI-Sector-Watch-<issue-number>-<short-slug>/
```

### 3. The pre-flight (one command)

```bash
scripts/start_issue.sh <issue-number> [tool-name]
```

That script does everything in one shot:

1. Locates the main worktree, refreshes it (`git fetch && git pull --rebase` if it's on main; just `git fetch` if not, so it doesn't yank the branch out from under another agent).
2. Verifies the issue exists, is open, and isn't assigned to someone else.
3. Self-assigns the issue.
4. Creates the per-issue worktree at `../AI-Sector-Watch-<#>-<slug>/` on branch `<tool>/<#>-<slug>`.
5. Symlinks `.env.local` from the main worktree so secrets resolve.
6. Optionally creates a per-worktree `.venv` (controlled by `AISW_VENV`; see below).
7. Prints the `cd` command and the rest of the next steps.

Manual fallback if the script ever fails (do these from the main worktree):

```bash
cd ~/Documents/Projects/AI-Sector-Watch
git fetch --prune origin
gh issue edit <#> --add-assignee @me
git worktree add ../AI-Sector-Watch-<#>-<slug> -b <tool>/<#>-<slug> origin/main
ln -s "$PWD/.env.local" ../AI-Sector-Watch-<#>-<slug>/.env.local
cd ../AI-Sector-Watch-<#>-<slug>
```

### 4. Per-worktree `.venv` strategy

The Python editable install (`pip install -e .`) writes a `.pth` file containing the absolute path to `src/`. If two worktrees symlink the same `.venv`, both will import from whichever worktree's `src/` was installed last. That's fine for tasks that don't edit `src/ai_sector_watch/` (docs, configs, dashboards), but breaks if you're modifying the package itself.

`scripts/start_issue.sh` honours `AISW_VENV`:

- `AISW_VENV=symlink` (default): symlink to the main worktree's `.venv`. Fastest setup; safe for non-Python edits.
- `AISW_VENV=own`: create a fresh per-worktree `.venv` with `pip install -e ".[dashboard,dev]"`. ~30s setup; safe for any change.
- `AISW_VENV=skip`: don't touch `.venv`. Use if you don't need Python at all (pure docs work).

Default to `own` if your task touches `src/`. Default to `symlink` otherwise.

### 5. Branch protection (enforced by GitHub)

The `main` branch has the following rules:

- **No direct pushes.** Every change goes through a PR.
- **CI must pass** before merge (the `test` job from `.github/workflows/pytest.yml`).
- **Branches must be up to date** with `main` before merge (forces rebase).
- **No force-push.** Trying it returns an error.
- **No branch deletion.**
- **Linear history** required.

Sam can override in genuine emergencies (admin bypass), but should not as a matter of course. If you find yourself wanting to bypass, stop and ask.

### 6. Live infrastructure coordination

Code changes are tracked by branches and PRs. **Live operations** (Azure provisioning, DNS edits, Supabase schema migrations, GitHub repo settings) are not. For these:

1. Open a Draft PR (or comment on the relevant issue) **before** running the operation, with a "Starting <operation> at <UTC time>" line.
2. Run the operation.
3. Comment when done.

This is a soft signal but it works because there are at most a few AI tools and one human in the loop. If we ever scale beyond that, we'll add a real lock service.

The "stop and ask before" gates in [AGENTS.md §4](../AGENTS.md#4-stop-and-ask-before) still apply on top of this — coordination is *additional* to those, not a replacement.

### 7. PR review and merge

- Use the PR template ([.github/pull_request_template.md](../.github/pull_request_template.md)). The "Multi-agent coordination" checklist is mandatory.
- AIs do not auto-merge. **Sam is the merger.**
- Sam squash-merges by default to keep `main` history linear and readable.
- After merge, the AI runs `scripts/finish_issue.sh <#>` to remove the worktree and delete the local branch, then moves the Project card to `Done`.

---

## End-to-end example

You've been told to pick up issue #8 (sector colour legend on the Map page).

```bash
# 1. From the main worktree (or anywhere with the same .git):
cd ~/Documents/Projects/AI-Sector-Watch
scripts/start_issue.sh 8 codex
# -> creates ../AI-Sector-Watch-8-add-a-sector-colour-legend-to-the-map/
# -> on branch codex/8-add-a-sector-colour-legend-to-the-map
# -> symlinks .env.local
# -> claims the issue on GitHub

# 2. cd into the new worktree:
cd ../AI-Sector-Watch-8-add-a-sector-colour-legend-to-the-map

# 3. Make your changes, run tests, commit.
.venv/bin/pytest -q
git add -A
git commit -m "feat(dashboard): add sector legend to map page"

# 4. Push and open a Draft PR:
git push -u origin HEAD
gh pr create --draft --title "[#8] Add sector colour legend" --body "Closes #8"

# 5. When ready: mark the PR ready, ping Sam, get it merged.

# 6. Cleanup after merge:
cd ~/Documents/Projects/AI-Sector-Watch
scripts/finish_issue.sh 8
# -> removes the worktree, deletes the local branch
```

---

## Conflict recovery

### "I started work but someone else already opened a PR for this issue"

Stop. Comment on the existing PR offering to help, or move to a different issue.

### "My branch has merge conflicts with main"

```bash
cd ~/Documents/Projects/AI-Sector-Watch-<#>-<slug>
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

### "Two PRs have file conflicts with each other"

Whoever opened first owns the merge. The second PR rebases after the first lands. If the first PR is stalled (>1 day with no movement), the second PR can take over after commenting on the first issue to claim ownership.

### "I committed in the wrong worktree"

If your commit landed on the wrong branch:

```bash
# In the worktree that has the misplaced commit:
git log -1 --format=%H              # note the SHA
git reset --hard HEAD~1             # remove the commit (only if not pushed)

# In the right worktree:
git cherry-pick <SHA>
```

If the commit was already pushed, leave it; ask Sam.

### "I lost track of where I am"

```bash
git worktree list                   # show all worktrees, branches, HEADs
git branch --show-current           # which branch is THIS worktree on
gh pr list --author @me             # which PRs are open under your name
gh issue list --assignee @me        # which issues are claimed by you
```

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

- LLM provider conversation history (that's per-tool, not shared).
- Local development state on Sam's laptop outside the repo.
- Secrets or 1Password items (only Sam touches these directly; AIs go through `op run`).

If you find yourself wanting a coordination mechanism the protocol doesn't have, propose it as an issue with the `infra` label.
