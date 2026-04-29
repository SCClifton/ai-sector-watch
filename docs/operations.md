# Operations

This is the public-safe operations guide. Keep credentials, raw extracts,
review artifacts, account identifiers, and incident details out of this file.

## Weekly Pipeline

`.github/workflows/weekly.yml` runs the ingestion pipeline on a weekly schedule
and also supports manual dispatch.

The workflow:

1. Installs the Python package.
2. Verifies setup and applies idempotent schema changes.
3. Runs `scripts/run_weekly_pipeline.py` with a bounded item limit.
4. Commits generated public digests under `data/digests/`.
5. Uploads the pipeline summary as a short-lived workflow artifact.

Required production secrets are configured in GitHub Actions. Do not document
secret values, account IDs, tenant IDs, or private vault paths in this repo.

## Manual Run

Local dry run:

```bash
op run --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5 --dry-run
```

Local write run:

```bash
op run --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5
```

Production dispatch:

```bash
gh workflow run weekly.yml -f limit=10
gh run watch
```

Use small limits first. Do not run unbounded source, enrichment, or LLM jobs
from a development environment.

## Review Artifacts

Company audits, enrichment reviews, manual import extracts, and pre-write
snapshots are local operator artifacts. They may contain copied source text,
contact details, evidence URLs, and intermediate model output.

Rules:

- Write review artifacts under `docs/data-audits/` or another ignored local
  path.
- Do not commit generated audit CSV, JSON, Markdown, snapshots, or copied
  source material.
- Commit only code, tests, public-safe summaries, and final public digests.

## Company Profile Audits

Use profile audits when the live dataset needs a reviewed accuracy pass. The
audit script reads from Supabase and writes local artifacts only.

Start with a dry run:

```bash
op run --env-file=.env.local -- python scripts/audit_company_profiles.py --limit 5 --dry-run
```

Run a small enriched batch only after checking estimated cost:

```bash
op run --env-file=.env.local -- python scripts/audit_company_profiles.py --limit 5 --enrich
```

Apply approved updates explicitly:

```bash
op run --env-file=.env.local -- python scripts/apply_company_profile_updates.py docs/data-audits/YYYY-MM-DD-company-accuracy.json --apply
```

Safety gates:

- `--enrich` requires `--limit`.
- Apply scripts default to dry run.
- Live apply refuses unresolved secret references.
- Large live batches need human review before running.

## Reviewed Imports

Manual source imports improve company metadata and funding history. They are
deliberately separate from the weekly pipeline.

Typical flow:

1. Discover candidate source material into a local ignored artifact.
2. Extract selected material into local Markdown, CSV, and JSON.
3. Review rows and keep uncertain entries marked for review.
4. Dry-run the reviewed payload.
5. Apply only after review.

Rules:

- Discovery and extraction never write Supabase.
- Apply defaults to dry run.
- Affected-row snapshots stay local and ignored.
- New companies are inserted only as `auto_discovered_pending_review`.
- Existing verified companies may receive reviewed metadata updates.
- Public pages continue to rely on `discovery_status = 'verified'`.

## Cost Guardrails

- Anthropic spend is capped per run by `ANTHROPIC_BUDGET_USD_PER_RUN`.
- Enrichment spend is capped per run by `FIRECRAWL_BUDGET_CREDITS_PER_RUN`.
- Successful local responses are cached under `data/local/`.
- Pipeline summaries report LLM spend and enrichment usage.

Do not raise caps or run large live batches without review.

## Rollback

If a weekly run writes bad data:

1. Find the relevant `ingest_events` row by timestamp.
2. Use linked records to identify affected writes.
3. Prefer targeted correction over a full reset.

For a full development reset, drop and reapply the schema, then reseed from
reviewed seed data. Do not run destructive production operations without human
approval.

## Known Operational Notes

- Database pooler connections can fail on the first attempt. The DB client
  retries with exponential backoff.
- The production dashboard is the Next.js app under `web/`.
- The legacy Streamlit app remains in `dashboard/` during the migration window.
