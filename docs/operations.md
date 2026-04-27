# Operations

## Weekly cron

`.github/workflows/weekly.yml` runs the ingestion pipeline every Sunday at 18:00 UTC (Monday morning Sydney). It also accepts `workflow_dispatch` so you can run on demand from the Actions UI or via `gh workflow run weekly.yml`.

The workflow:
1. Installs the package with the `dev` extra (no Streamlit needed for the cron).
2. Runs `scripts/verify_setup.py --apply-schema` (idempotent: makes sure tables exist).
3. Runs `scripts/run_weekly_pipeline.py --limit 25`.
4. Commits any new digests under `data/digests/` back to `main`.
5. Uploads the JSON summary as an artifact (kept for 30 days).

Required GitHub repo secrets:
- `ANTHROPIC_API_KEY`
- `SUPABASE_DB_URL`
- `ADMIN_PASSWORD` (only for the deploy workflow)
- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (deploy workflow OIDC)

For v0 these are mirrored from 1Password into repo secrets manually. For v1 we'll switch to `1password/load-secrets-action@v2`.

## Manual run

Local:

```bash
op run --account my.1password.com --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5
```

Production (via gh):

```bash
gh workflow run weekly.yml -f limit=10
```

Watch a run:

```bash
gh run watch
```

## Cost guardrails

- The pipeline hard-caps Anthropic spend per run via `ANTHROPIC_BUDGET_USD_PER_RUN` (default $2). When the cap is hit mid-run, the orchestrator records a `partial` ingest event and writes a digest of what it managed to do.
- Successful LLM responses are cached on disk under `data/local/claude_cache/` keyed by `(model, system, prompt, schema_class)`. CI runs see a cold cache; local development reruns are free after the first call.
- Firecrawl enrichment is hard-capped per run via `FIRECRAWL_BUDGET_CREDITS_PER_RUN` (default 200 credits, ~25 candidates at 8 credits each). Each enrichment pre-flights the full 8-credit estimate before dispatching. When the cap is hit, enrichment short-circuits to an empty `CompanyFacts` and the rest of the run continues.
- Successful Firecrawl enrichment responses are cached on disk under `data/local/firecrawl_cache/` keyed by `(website, company_name, json_schema_hash)`. The schema hash means a `CompanyFacts` schema change forces a fresh enrichment on the next run.
- The pipeline JSON summary (`scripts/run_weekly_pipeline.py`) reports `firecrawl_credits_used`, `firecrawl_calls`, and `firecrawl_cache_hits` alongside Anthropic spend so spend is observable from cron logs.

## Rollback

If a weekly run writes bad data:
- The data is in Supabase, not the repo. To revert a single run, find its `ingest_events` row by date and use the linked `news_items` to identify writes.
- For a full reset, drop and reapply the schema:
  ```sql
  DROP TABLE IF EXISTS news_items, funding_events, companies, ingest_events CASCADE;
  DROP TYPE IF EXISTS discovery_status, company_stage, news_kind;
  ```
  Then re-run `python scripts/seed_companies.py`.

## On-call

This is a single-operator project. Sam owns it. There is no on-call rotation.

## Known operational quirks

- Supabase pooler connections occasionally fail on the first attempt. The DB client retries 6 times with exponential backoff; you'll see warnings in the logs but the run should still succeed.
- Streamlit on Azure Web App for Containers needs `--server.headless true --server.address 0.0.0.0` and the right port (matches `WEBSITES_PORT` config). See `docs/deployment.md`.
