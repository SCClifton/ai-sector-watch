# Source Policy

This project uses public information to discover and enrich candidate companies.
The public repository documents the policy and source families, not a complete
operational map of every endpoint, query, or reviewed extract.

## Source Families

| Family | Use | Public-safety note |
|---|---|---|
| News and startup publications | Identify company announcements and ecosystem activity. | Use feed or sitemap interfaces where available. |
| Research and model-release signals | Detect AI-native activity connected to ANZ companies. | Filter heavily for relevance before review. |
| Investor and ecosystem publications | Cross-check funding, stage, and company metadata. | Reviewed imports only. Raw extracts stay local. |
| Company-owned pages | Confirm website, location, summary, and operating context. | Store concise facts, not copied page text. |

## Reviewed News Sources

The weekly pipeline includes these reviewed ANZ startup publication feeds:

| Slug | Feed | Rationale |
|---|---|---|
| `startup_daily_au` | Startup Daily RSS | Broad Australian and New Zealand startup coverage. |
| `smartcompany_startups` | SmartCompany StartupSmart RSS | Australian startup funding, launches, and operator news. |
| `innovationaus_startups` | InnovationAus Startups RSS | Australian technology, deep tech, policy, and startup coverage. |
| `startupnews_au` | Startup News RSS | Western Australian startup ecosystem coverage. |
| `nzentrepreneur` | NZ Entrepreneur RSS | New Zealand founder, startup, and ecosystem coverage. |

## Inclusion Rules

- Only use sources that are publicly accessible and permitted by their access
  terms.
- Prefer feeds, APIs, and sitemaps over HTML scraping.
- Respect `robots.txt` and rate limits.
- Store source-derived facts in concise form. Do not commit copied articles,
  reports, pages, or full extraction payloads.
- Keep raw review artifacts under ignored local paths.
- New sources must be reviewed in a PR before they are used in production.

## Pipeline Rules

- One fetch per active source per weekly run.
- Each fetched item is keyed by a stable hash so reruns are idempotent.
- Per-source failures are logged and skipped without failing the whole run.
- New candidates are inserted as `auto_discovered_pending_review`.
- Public surfaces must read only `discovery_status = 'verified'`.

## Adding A Source

1. Add or update the relevant source implementation under
   `src/ai_sector_watch/sources/`.
2. Register it in `default_sources()` in
   `src/ai_sector_watch/pipeline/weekly.py`.
3. Add a fixture-driven test under `tests/`.
4. Update this policy if the new source changes the source family, review
   process, or public-safety constraints.

## Reviewed Imports

Manual imports are separate from the weekly pipeline. They must write local
review artifacts first and require an explicit apply step before any database
write.

Rules for reviewed imports:

- Extraction does not write to Supabase.
- Apply commands default to dry run.
- Snapshots and raw review artifacts stay local and ignored.
- New companies remain pending until promoted by a reviewer.
