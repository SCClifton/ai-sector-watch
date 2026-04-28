"""Weekly pipeline orchestrator.

Flow:

1. Pull every registered source.
2. For each item, ask the LLM to extract company mentions.
3. Per mention: validate, classify, geocode (ANZ only), upsert as
   pending; or update an existing row's last-mention metadata.
4. Persist the news_item with linked company IDs and a `kind` tag.
5. Record an `ingest_events` row per source attempt and per LLM call run.
6. Write the markdown digest.

Idempotent end-to-end: every upsert keys on stable hashes, news items
key on URL hash, ingest events key on payload hash.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from ai_sector_watch.discovery import classifier as cls_mod
from ai_sector_watch.discovery import validator as val_mod
from ai_sector_watch.discovery.geocoder import geocode_city
from ai_sector_watch.extraction.claude_client import (
    BudgetExceeded,
    ClaudeClient,
)
from ai_sector_watch.extraction.firecrawl_client import (
    FirecrawlBudgetExceeded,
    FirecrawlClient,
    firecrawl_enrich,
)
from ai_sector_watch.extraction.prompts import (
    EXTRACT_COMPANIES_SYSTEM,
    EXTRACT_COMPANIES_USER_TEMPLATE,
    EXTRACT_FUNDING_SYSTEM,
    EXTRACT_FUNDING_USER_TEMPLATE,
)
from ai_sector_watch.extraction.schema import (
    CompanyFacts,
    CompanyMentionList,
    FundingExtraction,
)
from ai_sector_watch.sources import (
    arxiv_source,
    huggingface_papers,
    rss,
    sitemap,
)
from ai_sector_watch.sources.base import RawItem, SourceBase
from ai_sector_watch.storage import supabase_db

LOGGER = logging.getLogger(__name__)

ALLOWED_ANZ_COUNTRIES = {"AU", "NZ", "Australia", "New Zealand"}


def default_sources() -> list[SourceBase]:
    """The full PRD-section-7 source set, instantiated."""
    return [
        rss.startup_daily_au(),
        rss.smartcompany_startups(),
        sitemap.capital_brief(),
        rss.airtree_open_source_vc(),
        rss.blackbird_blog(),
        rss.crunchbase_ai(),
        rss.techcrunch_ai(),
        rss.yc_launches(),
        arxiv_source.arxiv_cs_ai(),
        arxiv_source.arxiv_cs_lg(),
        arxiv_source.arxiv_cs_ro(),
        huggingface_papers.HuggingFacePapers(),
    ]


@dataclass
class PipelineResult:
    sources_attempted: int = 0
    sources_ok: int = 0
    items_seen: int = 0
    items_new: int = 0
    candidates_added: int = 0
    cost_usd: float = 0.0
    firecrawl_credits_used: int = 0
    firecrawl_calls: int = 0
    firecrawl_cache_hits: int = 0
    digest_path: str | None = None
    new_companies: list[str] = field(default_factory=list)
    news_summary: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_weekly_pipeline(
    *,
    sources: Iterable[SourceBase] | None = None,
    client: ClaudeClient | None = None,
    firecrawl_client: FirecrawlClient | None = None,
    items_per_source: int = 25,
    write_to_db: bool = True,
    digest_date: date | None = None,
) -> PipelineResult:
    """End-to-end weekly run.

    Pure-ish: takes its dependencies as params for testability. The
    `scripts/run_weekly_pipeline.py` entry point wires defaults.
    """
    sources = list(sources) if sources is not None else default_sources()
    client = client or ClaudeClient()
    firecrawl_client = firecrawl_client or FirecrawlClient()
    result = PipelineResult()
    today = digest_date or datetime.now(UTC).date()
    raw_items: list[RawItem] = []

    # 1. Ingest -----------------------------------------------------------
    for source in sources:
        result.sources_attempted += 1
        try:
            items = source.fetch(limit=items_per_source)
            raw_items.extend(items)
            result.items_seen += len(items)
            result.sources_ok += 1
            LOGGER.info("source %s ok: %d items", source.slug, len(items))
        except Exception as exc:  # noqa: BLE001
            msg = f"source {source.slug} failed: {type(exc).__name__}: {exc}"
            LOGGER.warning(msg)
            result.errors.append(msg)

    if not raw_items:
        if write_to_db:
            _write_empty_digest(today, result)
        return result

    # 2. Persist news items + extract mentions ---------------------------
    if not write_to_db:
        # Dry-run: still extract so we exercise the LLM client / cache,
        # but don't touch Supabase.
        for item in raw_items:
            try:
                _extract_mentions(client, item)
            except BudgetExceeded as exc:
                result.errors.append(f"budget exceeded after {result.cost_usd:.4f}: {exc}")
                break
        result.cost_usd = client.stats.cost_usd
        return result

    with supabase_db.connection() as conn:
        existing_companies = supabase_db.list_companies(
            conn,
            statuses=("verified", "auto_discovered_pending_review"),
        )
        known_pairs = [
            (supabase_db.normalise_name(c["name"]), str(c["id"])) for c in existing_companies
        ]
        company_names_by_id = {str(c["id"]): c["name"] for c in existing_companies}

        for item in raw_items:
            try:
                mentions = _extract_mentions(client, item)
            except BudgetExceeded as exc:
                result.errors.append(f"budget exceeded after {client.stats.cost_usd:.4f}: {exc}")
                break

            # 3. New companies (ANZ only get coords + verified path)
            new_company_ids: list[str] = []
            for mention in mentions.mentions:
                if not mention.is_anz:
                    continue
                normalised = supabase_db.normalise_name(mention.name)
                if any(p[0] == normalised for p in known_pairs):
                    continue
                # Validate before persisting to keep the queue clean.
                try:
                    validation = val_mod.validate_company(
                        client,
                        name=mention.name,
                        context=item.title + "\n\n" + (item.summary or ""),
                    )
                except BudgetExceeded as exc:
                    result.errors.append(f"budget exceeded: {exc}")
                    break
                if not val_mod.is_acceptable(validation):
                    continue

                # 2. Firecrawl enrichment: scrape the company website for
                # authoritative facts before the classifier runs. Skipped if
                # no website is known. A scrape failure is non-fatal: facts
                # comes back with confidence=0 and we fall through.
                try:
                    facts = firecrawl_enrich(
                        firecrawl_client,
                        client,
                        validation.website,
                        name=validation.canonical_name or mention.name,
                    )
                except FirecrawlBudgetExceeded as exc:
                    result.errors.append(
                        f"firecrawl budget exceeded after "
                        f"{firecrawl_client.stats.credits_used} credits: {exc}"
                    )
                    facts = CompanyFacts.empty()
                except BudgetExceeded as exc:
                    result.errors.append(f"budget exceeded: {exc}")
                    break

                try:
                    classification = cls_mod.classify_company(
                        client,
                        name=mention.name,
                        context=_classifier_context(item, facts),
                    )
                except BudgetExceeded as exc:
                    result.errors.append(f"budget exceeded: {exc}")
                    break

                geo = geocode_city(facts.city or mention.city, jitter_seed=mention.name)
                company_id = supabase_db.upsert_company(
                    conn,
                    name=validation.canonical_name or mention.name,
                    country=facts.country or mention.country or "AU",
                    city=geo.city if geo else (facts.city or mention.city),
                    lat=geo.lat if geo else None,
                    lon=geo.lon if geo else None,
                    website=validation.website,
                    sector_tags=classification.sector_tags,
                    stage=classification.stage,
                    founded_year=facts.founded_year,
                    summary=classification.summary,
                    evidence_urls=facts.evidence_urls,
                    founders=facts.founders,
                    total_raised_usd=facts.total_raised_usd,
                    total_raised_currency_raw=facts.total_raised_currency_raw,
                    total_raised_as_of=facts.total_raised_as_of,
                    total_raised_source_url=facts.total_raised_source_url,
                    valuation_usd=facts.valuation_usd,
                    valuation_currency_raw=facts.valuation_currency_raw,
                    valuation_as_of=facts.valuation_as_of,
                    valuation_source_url=facts.valuation_source_url,
                    headcount_estimate=facts.headcount_estimate,
                    headcount_min=facts.headcount_min,
                    headcount_max=facts.headcount_max,
                    headcount_as_of=facts.headcount_as_of,
                    headcount_source_url=facts.headcount_source_url,
                    profile_confidence=facts.confidence or None,
                    profile_sources=facts.evidence_urls,
                    profile_verified_at=datetime.now(UTC) if facts.confidence else None,
                    discovery_status="auto_discovered_pending_review",
                    discovery_source=item.source_slug,
                )
                company_name = validation.canonical_name or mention.name
                new_company_ids.append(company_id)
                result.new_companies.append(mention.name)
                result.candidates_added += 1
                known_pairs.append((normalised, company_id))
                company_names_by_id[company_id] = company_name

            # 4. News-kind classification + upsert
            try:
                news_class = cls_mod.classify_news(
                    client, title=item.title, body=item.summary or ""
                )
            except BudgetExceeded as exc:
                result.errors.append(f"budget exceeded: {exc}")
                break
            if not news_class.is_relevant and not new_company_ids:
                # Skip noise: not relevant AND introduced no candidates.
                continue

            mention_names = [m.name for m in mentions.mentions]
            linked_ids = _dedupe_ids(
                [
                    *cls_mod.link_news_to_companies(
                        mention_names=mention_names,
                        known_companies=known_pairs,
                    ),
                    *new_company_ids,
                ]
            )

            news_id = supabase_db.upsert_news_item(
                conn,
                source_slug=item.source_slug,
                source_url=item.url,
                title=item.title,
                summary=item.summary,
                published_at=item.published_at,
                kind=news_class.kind,
                company_ids=linked_ids,
                raw_payload={"raw": item.raw, "mention_count": len(mentions.mentions)},
            )
            result.news_summary.append(
                {
                    "id": news_id,
                    "title": item.title,
                    "url": item.url,
                    "source_slug": item.source_slug,
                    "kind": news_class.kind,
                    "company_ids": linked_ids,
                }
            )
            result.items_new += 1
            if news_class.kind == "funding" and linked_ids:
                try:
                    funding_match = _extract_first_funding_event(
                        client,
                        item,
                        company_ids=linked_ids,
                        company_names_by_id=company_names_by_id,
                    )
                except BudgetExceeded as exc:
                    result.errors.append(f"budget exceeded: {exc}")
                    break
                if funding_match is not None:
                    company_id, funding = funding_match
                    supabase_db.upsert_funding_event(
                        conn,
                        company_id=company_id,
                        announced_on=funding.announced_on,
                        stage=_clean_funding_stage(funding.stage),
                        amount_usd=funding.amount_usd,
                        currency_raw=funding.currency_raw,
                        lead_investor=funding.lead_investor,
                        investors=funding.investors,
                        source_url=item.url,
                    )

        # 5. Audit row per run.
        supabase_db.insert_ingest_event(
            conn,
            source_slug="pipeline",
            kind="weekly_run",
            payload={
                "date": today.isoformat(),
                "cost_usd": client.stats.cost_usd,
                "firecrawl_credits_used": firecrawl_client.stats.credits_used,
                "firecrawl_calls": firecrawl_client.stats.calls,
                "firecrawl_cache_hits": firecrawl_client.stats.cache_hits,
            },
            window_start=datetime.combine(today, datetime.min.time(), tzinfo=UTC),
            window_end=datetime.now(UTC),
            status="ok" if not result.errors else "partial",
            error="; ".join(result.errors) if result.errors else None,
            items_seen=result.items_seen,
            items_new=result.items_new,
            cost_usd=client.stats.cost_usd,
        )
        conn.commit()

    result.cost_usd = client.stats.cost_usd
    result.firecrawl_credits_used = firecrawl_client.stats.credits_used
    result.firecrawl_calls = firecrawl_client.stats.calls
    result.firecrawl_cache_hits = firecrawl_client.stats.cache_hits

    # 6. Digest --------------------------------------------------------
    digest_path = _write_digest(today, result)
    result.digest_path = str(digest_path)

    return result


def _classifier_context(item: RawItem, facts: CompanyFacts) -> str:
    """Build the classify-company context: news summary + enriched facts.

    Facts only get appended when the scrape returned something useful
    (confidence > 0); otherwise the context is identical to the
    pre-Firecrawl behaviour.
    """
    news_summary = item.title + "\n\n" + (item.summary or "")
    if facts.confidence <= 0:
        return news_summary
    chunks: list[str] = [news_summary]
    if facts.description:
        chunks.append(f"Company description (from website): {facts.description}")
    if facts.sector_keywords:
        chunks.append("Sector keywords (from website): " + ", ".join(facts.sector_keywords))
    if facts.founded_year:
        chunks.append(f"Founded: {facts.founded_year}")
    return "\n\n".join(chunks)


def _extract_mentions(client: ClaudeClient, item: RawItem) -> CompanyMentionList:
    prompt = EXTRACT_COMPANIES_USER_TEMPLATE.format(
        title=item.title,
        source_slug=item.source_slug,
        url=item.url,
        published_at=item.published_at.isoformat() if item.published_at else "",
        body=item.summary or "",
    )
    response = client.structured_call(
        system=EXTRACT_COMPANIES_SYSTEM,
        prompt=prompt,
        schema_cls=CompanyMentionList,
        max_tokens=512,
    )
    return response.parsed  # type: ignore[return-value]


def _extract_funding(client: ClaudeClient, item: RawItem, company_name: str) -> FundingExtraction:
    prompt = EXTRACT_FUNDING_USER_TEMPLATE.format(
        name=company_name,
        body="\n\n".join([item.title, item.summary or ""]),
    )
    response = client.structured_call(
        system=EXTRACT_FUNDING_SYSTEM,
        prompt=prompt,
        schema_cls=FundingExtraction,
        max_tokens=384,
    )
    return response.parsed  # type: ignore[return-value]


def _extract_first_funding_event(
    client: ClaudeClient,
    item: RawItem,
    *,
    company_ids: list[str],
    company_names_by_id: dict[str, str],
) -> tuple[str, FundingExtraction] | None:
    """Return the linked company whose funding extraction confirms the event."""
    for company_id in company_ids:
        company_name = company_names_by_id.get(company_id)
        if not company_name:
            continue
        funding = _extract_funding(client, item, company_name)
        if funding.has_funding_event:
            return company_id, funding
    return None


def _dedupe_ids(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item_id in ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        out.append(item_id)
    return out


def _clean_funding_stage(stage: str | None) -> str | None:
    if not stage:
        return None
    normalised = stage.lower().replace("-", " ").replace("_", " ").strip()
    normalised = " ".join(normalised.split())
    stage_map = {
        "pre seed": "pre_seed",
        "preseed": "pre_seed",
        "seed": "seed",
        "series a": "series_a",
        "series b": "series_b_plus",
        "series b+": "series_b_plus",
        "series b plus": "series_b_plus",
        "series c": "series_b_plus",
        "series d": "series_b_plus",
        "series e": "series_b_plus",
        "growth": "series_b_plus",
        "late stage": "series_b_plus",
        "mature": "mature",
    }
    return stage_map.get(normalised)


def _write_empty_digest(today: date, result: PipelineResult) -> None:
    from ai_sector_watch.digest.generator import DigestStats, write_digest

    stats = DigestStats(
        sources_attempted=result.sources_attempted,
        sources_ok=result.sources_ok,
        items_seen=0,
        items_new=0,
        candidates_added=0,
        cost_usd=0.0,
    )
    path = write_digest(run_date=today, stats=stats, new_companies=[], news=[])
    result.digest_path = str(path)


def _write_digest(today: date, result: PipelineResult):
    from ai_sector_watch.digest.generator import (
        DigestNewsRow,
        DigestStats,
        write_digest,
    )

    stats = DigestStats(
        sources_attempted=result.sources_attempted,
        sources_ok=result.sources_ok,
        items_seen=result.items_seen,
        items_new=result.items_new,
        candidates_added=result.candidates_added,
        cost_usd=result.cost_usd,
    )
    news_rows = [
        DigestNewsRow(
            title=n["title"],
            url=n["url"],
            source_slug=n["source_slug"],
            kind=n["kind"],
            company_names=[],
        )
        for n in result.news_summary
    ]
    return write_digest(
        run_date=today,
        stats=stats,
        new_companies=result.new_companies,
        news=news_rows,
    )
