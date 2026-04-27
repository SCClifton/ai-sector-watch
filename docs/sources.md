# Ingestion Sources

Single source of truth for the RSS, API, and feed endpoints the weekly pipeline pulls from.

To add a source: create a new module under `src/ai_sector_watch/sources/` that subclasses `SourceBase`, append a row to the table below, and register it in `src/ai_sector_watch/pipeline/weekly.py`. Sources outside this list must not be added without updating the PRD.

## Active sources (v0)

| Slug | URL | Type | ANZ relevance | Notes |
|---|---|---|---|---|
| arxiv_cs_ai | https://export.arxiv.org/rss/cs.AI | Papers | Medium | RSS via feedparser |
| arxiv_cs_lg | https://export.arxiv.org/rss/cs.LG | Papers | Medium | RSS via feedparser |
| arxiv_cs_ro | https://export.arxiv.org/rss/cs.RO | Papers | Medium | RSS via feedparser |
| techcrunch_ai | https://techcrunch.com/category/artificial-intelligence/feed/ | News | Low | Global; filter for ANZ mentions |
| startup_daily_au | https://www.startupdaily.net/feed/ | News | High |  |
| smartcompany_startups | https://www.smartcompany.com.au/startupsmart/feed/ | News | High |  |
| capital_brief | https://www.capitalbrief.com/sitemap/news.xml | News sitemap | High | Google News sitemap advertised in robots.txt; native RSS not published as of 2026-04-27 |
| airtree_open_source_vc | https://www.airtree.vc/open-source-vc/rss.xml | Blog | High |  |
| blackbird_blog | https://www.blackbird.vc/blog/feed | Blog | High |  |
| crunchbase_ai | https://news.crunchbase.com/sections/ai/feed/ | News | Medium |  |
| huggingface_papers | https://huggingface.co/api/daily_papers | API JSON | Medium | Custom JSON fetcher, not RSS |
| yc_launches | https://www.ycombinator.com/launches/feed.atom | Launches | Low |  |

## Conventions

- One fetch per source per weekly run.
- `httpx` with a 30s timeout and a polite `User-Agent`: `ai-sector-watch/0.1 (+aimap.cliftonfamily.co)`.
- Idempotent: store a hash of each item; skip if seen.
- Per-source failures must not abort the run; log and continue.
- Never bypass `robots.txt`; never scrape HTML when an RSS or API feed exists.

## Enrichment

Discovery sources tell the pipeline that a company exists; enrichment fills in
authoritative fields directly from the company's own website. Enrichment runs
after LLM validation and before classification, only when a website URL is
known for the candidate.

| Provider | URL | Trigger | Cost | Notes |
|---|---|---|---|---|
| Firecrawl | https://www.firecrawl.dev/ | Per new ANZ candidate with a known website | ~5 credits per scrape (1 scrape + 4 JSON-mode extract) | Implementation: `src/ai_sector_watch/extraction/firecrawl_client.py`. JSON-mode extract uses the `CompanyFacts` schema. |

Skipped when:

- The candidate already exists in the DB (idempotent).
- No website is known (LLM validator did not return one).
- The per-run credit cap (`FIRECRAWL_BUDGET_CREDITS_PER_RUN`, default 200) is reached.

Successful responses are cached on disk under `data/local/firecrawl_cache/` so
reruns do not re-spend credits. The cache key includes the JSON-Schema hash so
a schema change forces a re-scrape.
