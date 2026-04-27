# Contributing

This is a single-operator project, but contributions are welcome.

Before you write code, read:

1. [README.md](README.md) — what the project is, how it's structured, how to run it.
2. [AGENTS.md](AGENTS.md) — working conventions, non-negotiables, how to do common things.

## Quick contributor checklist

- [ ] Python 3.12 venv created (`python3.12 -m venv .venv`).
- [ ] `pip install -e ".[dashboard,dev]"`.
- [ ] `pytest -q`, `ruff check .`, `black --check .` all pass.
- [ ] If your change is a milestone (closes a Now/Next issue, ships a public feature, breaks something), update `PROJECT_PROGRESS.md`. Otherwise the PR body is the record.
- [ ] Your change has a test or a documented manual smoke check.
- [ ] No em dashes in user-facing copy (digest, dashboard, popups).
- [ ] No bare secrets in any committed file.

## Reporting an issue

Use the issue templates under [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE) so we can triage quickly:

- **Bug report** — something is broken, here's how to reproduce.
- **Feature request** — a new feature, source, or change.
- **Data correction** — a company on the map is wrong (sector, stage, location, summary).

## Pull requests

Every change to `main` goes through a PR. Branch protection rejects direct pushes. The PR template lives at [`.github/pull_request_template.md`](.github/pull_request_template.md) and asks for the things a reviewer needs to see.

## Working in parallel (multiple humans / AI tools)

Multiple contributors (Claude Code, Codex, humans) may be in the repo at the same time. **Each active issue gets its own git worktree** — a sibling directory that shares the same `.git/`. Two agents working on different issues never collide because they're in different working directories.

Read [`docs/multi-agent-workflow.md`](docs/multi-agent-workflow.md) for the full protocol. The one-liner:

```bash
scripts/start_issue.sh <issue-number> [tool-name]
```

That script: refreshes main, claims the issue, creates `../AI-Sector-Watch-<#>-<slug>/` on branch `<tool>/<#>-<slug>`, symlinks `.env.local`, and prints the next steps. Then `cd` into the new worktree and work there.

After your PR merges:

```bash
scripts/finish_issue.sh <issue-number>
```

Removes the worktree and the local branch.

Code of conduct: be terse, be sharp, be kind.
