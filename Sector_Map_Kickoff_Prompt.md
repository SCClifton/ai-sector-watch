# Claude Code Kickoff Prompt

Paste the block below as your first message to Claude Code. Run it from `/Users/samuelclifton/Documents/Projects` (so the new repo lands at `/Users/samuelclifton/Documents/Projects/AI-Sector-Watch`).

---

I want to build a new project called `ai-sector-watch` (display name "AI Sector Watch"). Save it to `/Users/samuelclifton/Documents/Projects/AI-Sector-Watch`. Reference my existing project at `/Users/samuelclifton/Projects/Home-Energy-Analysis` for conventions, but the new project lives in a different parent folder.

The full PRD is at:

`/Users/samuelclifton/Library/CloudStorage/Dropbox/1. Jobs/2. Opportunities/AirTree/Investment Manager Early Stage AI/Sector_Map_PRD.md`

Read the PRD end to end before writing any code.

## Context you should know

- I have an existing Python project at `/Users/samuelclifton/Projects/Home-Energy-Analysis` that uses similar patterns: Python 3.12, Supabase Postgres for durable storage, idempotent pipelines, scheduled jobs, pytest. Read that project's `README.md` and `PROJECT_PROGRESS.md` for the conventions before scaffolding the new one. The new project should feel like a sibling, not a fresh take.
- I am Sam Clifton, an operator-investor with a deep tech and ML background. I prefer terse, sharp working style. No em dashes in any code comments, docs, or generated output. Active voice. No filler.
- This project supports an active VC application. Working code beats perfect code. Ship a v0 that runs end-to-end on real data and is publicly accessible. Defer everything marked v1 or v2 in the PRD.
- The dashboard frontend is Streamlit + streamlit-folium. The map is the headline feature. Hosting target is Azure App Service with custom domain `aimap.cliftonfamily.co` (confirm subdomain with me before pointing DNS).
- The weekly job runs via GitHub Actions cron. No daemons or always-on workers.

## Credentials and environment

**All credentials live in 1Password and are accessed via the `op` CLI. Never write bare secrets to any file. Never copy secret values into chat or commits.**

Patterns to use:

- `.env.local` contains only `op://Vault/Item/field` references (commit `.env.template`, gitignore `.env.local`).
- Run anything that needs secrets via `op run --env-file=.env.local -- <command>`.
- For GitHub Actions, use repo secrets for v0. Plan v1 migration to `1password/load-secrets-action@v2`.
- For Azure, use `az login` interactively for v0.

Before writing any code, do the following in order:

1. Inspect `~/Projects/Home-Energy-Analysis` for any existing `.env`, `.env.local`, or `.env.template` files. Look for the 1Password reference pattern I already use, if any.
2. Ask me which 1Password vault holds my credentials (default guess: `Private`).
3. Ask me to confirm the exact `op://` references for these secrets:
   - `ANTHROPIC_API_KEY`
   - `SUPABASE_DB_URL` (you may need to ask me to provision a new Supabase project for this app, or confirm reuse of an existing one)
   - `ADMIN_PASSWORD` (for `90_Admin.py`)
   - `GITHUB_TOKEN` if you need to commit digest markdown back from CI
4. Confirm you have `op`, `gh`, and `az` CLIs available. Run `op whoami`, `gh auth status`, `az account show` and report results to me.

If anything is missing or unclear, stop and ask me before proceeding.

## What I want first

Your first response should be a written plan, not code. The plan should:

1. Confirm the PRD is well-formed and flag anything that needs clarification before building
2. Propose a concrete sequence of commits to ship v0, each scoped small enough to verify independently
3. Identify the 3 highest-risk parts of the build and how you propose to de-risk them
4. Confirm the build order: seed list and storage layer first, then a Streamlit dashboard rendering the seeded companies on a map of Australia, **then** the agent pipeline. The map being live with seeded data is the most important early demo artefact.
5. Confirm the credential setup based on your CLI checks above

After I approve the plan, scaffold the project structure and start with the seed list and storage layer first. Get the map rendering with seed data before building any of the agent pipeline.

## Working rules

For every commit:
- Run the relevant tests before declaring it done
- Update `PROJECT_PROGRESS.md` with what shipped, what was tested, known limitations
- Keep diffs small and reviewable

Stop and confirm with me before:
- Choosing a different stack than the PRD specifies
- Adding any source not listed in PRD section 7
- Spending more than 1 USD of API quota in a single test run
- Pushing to GitHub or any remote
- Provisioning any Azure resource
- Pointing a DNS record
- Creating any new 1Password item or new Supabase project

Ready to start. Read the PRD, then run the credential checks, then come back to me with the plan.
