#!/bin/bash
# Pre-flight helper for picking up a GitHub issue.
#
# Usage:
#   scripts/start_issue.sh <issue-number> [tool-name]
#
# Default tool-name is "claude-code" (override with second arg or AISW_TOOL env).
# Exits non-zero if the issue is already assigned to someone else.
#
# What it does (in order):
#   1. git fetch + git checkout main + git pull --rebase
#   2. Verifies the issue exists and is unassigned (or assigned to you)
#   3. Claims the issue (gh issue edit --add-assignee @me)
#   4. Creates a feature branch named <tool>/<#>-<slug>
#   5. Prints the next steps (move Project status, open Draft PR after first commit)

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <issue-number> [tool-name]" >&2
  exit 2
fi

ISSUE="$1"
TOOL="${2:-${AISW_TOOL:-claude-code}}"

# Sanitise tool name.
case "$TOOL" in
  claude-code|codex|human|*)
    ;;
esac

REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner')
ME=$(gh api user -q '.login')

echo "==> Repo:    $REPO"
echo "==> Issue:   #$ISSUE"
echo "==> Tool:    $TOOL"
echo "==> Me:      $ME"

# Step 1: latest main.
echo
echo "==> Updating main"
git fetch --prune
git checkout main
git pull --rebase

# Step 2: verify issue and ownership.
echo
echo "==> Inspecting issue"
ISSUE_JSON=$(gh issue view "$ISSUE" --json number,title,state,assignees,labels)
STATE=$(echo "$ISSUE_JSON" | jq -r '.state')
TITLE=$(echo "$ISSUE_JSON" | jq -r '.title')
ASSIGNEES=$(echo "$ISSUE_JSON" | jq -r '.assignees[].login // empty' | tr '\n' ' ')

echo "    Title:     $TITLE"
echo "    State:     $STATE"
echo "    Assignees: ${ASSIGNEES:-<none>}"

if [[ "$STATE" != "OPEN" ]]; then
  echo "ERROR: issue #$ISSUE is $STATE; pick a different issue." >&2
  exit 1
fi

if [[ -n "$ASSIGNEES" && "$ASSIGNEES" != *"$ME"* ]]; then
  echo "ERROR: issue #$ISSUE is already assigned to $ASSIGNEES (not you)." >&2
  echo "       If you believe the assignee has stalled (>1 day), comment first." >&2
  exit 1
fi

# Step 3: claim if not yet.
if [[ "$ASSIGNEES" != *"$ME"* ]]; then
  echo
  echo "==> Claiming issue (self-assign)"
  gh issue edit "$ISSUE" --add-assignee "@me"
else
  echo
  echo "==> Already assigned to you; skipping claim."
fi

# Step 4: create branch.
SLUG=$(echo "$TITLE" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' \
  | cut -c1-40)
BRANCH="${TOOL}/${ISSUE}-${SLUG}"

echo
echo "==> Creating branch: $BRANCH"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "    Branch already exists locally; checking out."
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH"
fi

# Step 5: print next steps.
cat <<EOF

==> Pre-flight complete.

Next steps:
  1. Make your first commit, then open a Draft PR:
       gh pr create --draft --title "[#$ISSUE] $TITLE" --body "Closes #$ISSUE"
  2. Move the Project card to "In Progress" (Workflow field).
  3. Run tests before pushing:
       pytest -q && ruff check . && black --check .
  4. When ready for review, mark the PR as ready and ping Sam.

Reminders:
  - No direct commits to main (branch protection enforces this).
  - Update PROJECT_PROGRESS.md in any commit that ships functionality.
  - No em dashes in user-facing copy.
  - Read AGENTS.md and docs/multi-agent-workflow.md if anything is unclear.
EOF
