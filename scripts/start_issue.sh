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
#   1. Locate the main worktree and refresh it (`git fetch && git pull --rebase`)
#      so we branch from the latest main.
#   2. Verifies the issue exists and is unassigned (or assigned to you).
#   3. Claims the issue (gh issue edit --add-assignee @me).
#   4. Creates a per-issue worktree at ../AI-Sector-Watch-<#>-<slug>/ on
#      branch <tool>/<#>-<slug>. The worktree is the agent's isolated
#      working directory; multiple agents can run in parallel because each
#      lives in its own.
#   5. Symlinks .env.local from the main worktree so secrets resolve.
#   6. Optionally creates a per-worktree .venv (controlled by AISW_VENV).
#   7. Prints the next steps (cd into the worktree, open Draft PR, etc.).

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <issue-number> [tool-name]" >&2
  exit 2
fi

ISSUE="$1"
TOOL="${2:-${AISW_TOOL:-claude-code}}"

# Discover the main worktree root by walking up from this script's location.
# `git rev-parse --show-toplevel` would give us THIS worktree, but we want the
# canonical (first-listed) worktree to anchor relative paths.
MAIN_WT=$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')
if [[ -z "$MAIN_WT" ]]; then
  echo "ERROR: could not locate main worktree" >&2
  exit 1
fi

REPO=$(cd "$MAIN_WT" && gh repo view --json nameWithOwner -q '.nameWithOwner')
ME=$(gh api user -q '.login')

echo "==> Repo:         $REPO"
echo "==> Issue:        #$ISSUE"
echo "==> Tool:         $TOOL"
echo "==> Me:           $ME"
echo "==> Main worktree: $MAIN_WT"

# Step 1: refresh main in the canonical worktree.
echo
echo "==> Refreshing main"
(
  cd "$MAIN_WT"
  current=$(git branch --show-current)
  if [[ "$current" != "main" ]]; then
    echo "    Main worktree is on '$current' (not main). Skipping pull --rebase to avoid"
    echo "    yanking the branch out from under another agent. Will branch from origin/main."
    git fetch --prune origin
  else
    git fetch --prune origin
    git pull --rebase
  fi
)

# Step 2: verify issue and ownership.
echo
echo "==> Inspecting issue"
ISSUE_JSON=$(gh issue view "$ISSUE" --repo "$REPO" --json number,title,state,assignees,labels)
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
  gh issue edit "$ISSUE" --repo "$REPO" --add-assignee "@me"
else
  echo
  echo "==> Already assigned to you; skipping claim."
fi

# Step 4: derive slug and worktree path.
SLUG=$(echo "$TITLE" \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' \
  | cut -c1-40 \
  | sed -E 's/-+$//')
BRANCH="${TOOL}/${ISSUE}-${SLUG}"
WT_DIR="$(dirname "$MAIN_WT")/$(basename "$MAIN_WT")-${ISSUE}-${SLUG}"

echo
echo "==> Branch:    $BRANCH"
echo "==> Worktree:  $WT_DIR"

# Step 5: create the worktree.
if [[ -d "$WT_DIR" ]]; then
  echo "    Worktree directory already exists; assuming it's the right one."
  if ! (cd "$WT_DIR" && git rev-parse --git-dir >/dev/null 2>&1); then
    echo "ERROR: $WT_DIR exists but is not a worktree. Move or remove it." >&2
    exit 1
  fi
else
  if git -C "$MAIN_WT" show-ref --verify --quiet "refs/heads/$BRANCH"; then
    echo "    Branch already exists; checking it out into a new worktree."
    git -C "$MAIN_WT" worktree add "$WT_DIR" "$BRANCH"
  else
    echo "    Creating fresh branch + worktree from origin/main."
    git -C "$MAIN_WT" worktree add "$WT_DIR" -b "$BRANCH" origin/main
  fi
fi

# Step 6: link .env.local and optionally create a venv.
if [[ -f "$MAIN_WT/.env.local" && ! -e "$WT_DIR/.env.local" ]]; then
  ln -s "$MAIN_WT/.env.local" "$WT_DIR/.env.local"
  echo "    Linked .env.local"
fi

if [[ -d "$MAIN_WT/.venv" && ! -e "$WT_DIR/.venv" ]]; then
  case "${AISW_VENV:-symlink}" in
    own)
      echo "    Creating per-worktree venv (this takes ~30s)"
      (cd "$WT_DIR" && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dashboard,dev]" --quiet)
      ;;
    skip)
      echo "    AISW_VENV=skip; not creating .venv"
      ;;
    *)
      ln -s "$MAIN_WT/.venv" "$WT_DIR/.venv"
      echo "    Linked .venv (note: editable install paths may still resolve to main worktree;"
      echo "                  set AISW_VENV=own if you'll be editing src/ai_sector_watch/)"
      ;;
  esac
fi

# Step 6.5: move the Project card to "In Progress".
# Project metadata is hard-coded for this repo because gh has no nice
# generic way to look it up. If you ever rename or recreate the project,
# update these constants.
PROJECT_NUMBER=3
PROJECT_OWNER="SCClifton"
PROJECT_ID="PVT_kwHOCnSDOc4BVz2x"
WORKFLOW_FIELD_ID="PVTSSF_lAHOCnSDOc4BVz2xzhRNAXY"
WORKFLOW_IN_PROGRESS="e00b541b"
PROJECT_CARD_MOVED=0

set +e
ITEM_ID=$(
  gh project item-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json --limit 200 \
    | jq -r --argjson n "$ISSUE" '.items[] | select(.content.number == $n) | .id' \
    | head -1
)
if [[ -n "$ITEM_ID" && "$ITEM_ID" != "null" ]]; then
  gh project item-edit \
    --id "$ITEM_ID" \
    --project-id "$PROJECT_ID" \
    --field-id "$WORKFLOW_FIELD_ID" \
    --single-select-option-id "$WORKFLOW_IN_PROGRESS" >/dev/null 2>&1 \
    && { echo "    Project Workflow set to In Progress"; PROJECT_CARD_MOVED=1; } \
    || echo "    (could not move Project card; do it manually)"
else
  echo "    Issue not on Project board yet; skipping Workflow move"
fi
set -e

if [[ "$PROJECT_CARD_MOVED" == "1" ]]; then
  PROJECT_CARD_NOTE='Project card has already been moved to "In Progress".'
else
  PROJECT_CARD_NOTE='Move the Project card to "In Progress" if it is on the board.'
fi

# Step 7: print next steps.
cat <<EOF

==> Pre-flight complete.

cd into the worktree:
  cd $WT_DIR

Cache 1Password auth ONCE for this shell session (one Touch ID tap, then
~30 minutes of free op access; without this, every op call re-prompts):
  eval \$(op signin --account my.1password.com)

Make your first commit, then open a Draft PR:
  gh pr create --draft --title "[#$ISSUE] $TITLE" --body "Closes #$ISSUE"

Run secret-bearing commands with the explicit 1Password account:
  op run --account my.1password.com --env-file=.env.local -- <your command>

$PROJECT_CARD_NOTE

When ready for review, mark the PR as ready and ping Sam.

When the PR merges, clean up the worktree:
  git worktree remove $WT_DIR

Reminders:
  - No direct commits to main (branch protection enforces this).
  - Update PROJECT_PROGRESS.md in any commit that ships functionality.
  - No em dashes in user-facing copy.
  - Read AGENTS.md and docs/multi-agent-workflow.md if anything is unclear.
EOF
