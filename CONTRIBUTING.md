# Contributing

This is a single-operator project, but contributions are welcome.

Before you write code, read:

1. [README.md](README.md) — what the project is, how it's structured, how to run it.
2. [AGENTS.md](AGENTS.md) — working conventions, non-negotiables, how to do common things.

## Quick contributor checklist

- [ ] Python 3.12 venv created (`python3.12 -m venv .venv`).
- [ ] `pip install -e ".[dashboard,dev]"`.
- [ ] `pytest -q`, `ruff check .`, `black --check .` all pass.
- [ ] Your change updates `PROJECT_PROGRESS.md` if it ships functionality.
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

Multiple contributors (Claude Code, Codex, humans) may be in the repo at the same time. Read [`docs/multi-agent-workflow.md`](docs/multi-agent-workflow.md) before you start a task. The short version:

1. Pull the latest `main`.
2. Self-assign the issue (`gh issue edit <#> --add-assignee @me`). Issue assignment is the lock.
3. Set the Project's **Workflow** field to **In Progress**.
4. Branch as `<tool>/<issue-number>-<slug>` — e.g. `codex/8-sector-legend`.
5. Open a Draft PR after the first commit.
6. Rebase on `main` before requesting review.

Use [`scripts/start_issue.sh <issue-number>`](scripts/start_issue.sh) to do steps 1-4 in one shot.

Code of conduct: be terse, be sharp, be kind.
