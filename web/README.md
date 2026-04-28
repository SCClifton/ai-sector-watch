# web/ - Next.js + MapLibre dashboard prototype

Spike for [#62](https://github.com/SCClifton/ai-sector-watch/issues/62). High-fidelity prototype of a custom dashboard to replace the Streamlit app at `aimap.cliftonfamily.co`. **Not deployed.** The live Streamlit dashboard under `dashboard/` is untouched by this work.

## Stack

- Next.js 16 (app router) + TypeScript + Tailwind v4
- MapLibre GL JS for the map, supercluster for client-side clustering
- `postgres` (postgres-js) reading the live Supabase DB server-side via `SUPABASE_DB_URL`

## Run it

The Supabase connection string lives in the worktree-level `.env.local` as a 1Password secret reference (`op://...`). `web/.env.local` is symlinked to the worktree-level file. Wrap commands with `op run` like everywhere else in this repo:

```bash
cd web
npm install
op run --account my.1password.com --env-file=.env.local -- npm run dev
```

Open http://localhost:3000.

If you only need the build/lint check (no DB access needed):

```bash
npm run build
npm run lint
```

## What's implemented

- `/map` - full-bleed MapLibre map, sector-coloured clustered markers, hover tooltip, click-to-detail panel, URL-driven filter state (sector, stage, country, founded year, name)
- `/api/companies` - server route mirroring `SupabaseSource.list_companies` from `src/ai_sector_watch/storage/data_source.py`

## What's stubbed

- `/`, `/companies`, `/news`, `/about` - render the shell with a "coming in Phase 2" body
- No writes (no Admin queue)
- No authentication
- No tests

## What's deferred to later phases

- Phase 2: feature parity (Companies search + detail, News, Digest, Admin queue with auth, mobile responsive)
- Phase 3: Dockerfile + CI workflow + Azure App Service cutover

## Read-spec (do not edit)

The TS code mirrors behaviour from these Python files; treat them as the source of truth:

- `src/ai_sector_watch/storage/data_source.py` - `SupabaseSource.list_companies` SQL
- `src/ai_sector_watch/discovery/taxonomy.py` - sector tags, labels, colour groups
- `dashboard/components/filters.py` - `apply_filters` filter semantics
- `dashboard/components/map_view.py` - popup design tokens
- `dashboard/static/styles.css` - global design tokens (`--aisw-*`)
- `docs/design-system.md` - the design system rationale
