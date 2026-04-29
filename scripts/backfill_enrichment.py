#!/usr/bin/env python3
"""Backfill Firecrawl enrichment for existing verified companies.

Reads verified companies from Supabase in recency order, enriches each company
through the Firecrawl multi-source path, and writes only enrichment-backed
fields. Human-curated fields are preserved unless --force-overwrite is passed.

Usage:
    op run --env-file=.env.local -- python scripts/backfill_enrichment.py --limit 5 --dry-run
    op run --env-file=.env.local -- python scripts/backfill_enrichment.py --limit 20
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.discovery.geocoder import geocode_city  # noqa: E402
from ai_sector_watch.extraction.claude_client import BudgetExceeded, ClaudeClient  # noqa: E402
from ai_sector_watch.extraction.firecrawl_client import (  # noqa: E402
    DEFAULT_CREDITS_PER_ENRICH,
    FirecrawlBudgetExceeded,
    FirecrawlClient,
    firecrawl_enrich,
)
from ai_sector_watch.extraction.schema import CompanyFacts  # noqa: E402
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger("backfill_enrichment")
DEFAULT_MAX_AGE_YEARS = 10
DEFAULT_SKIP_IF_NEWER_THAN_DAYS = 30
FORCE_OVERWRITE_REVIEW_LIMIT = 10
MAX_COMPANIES_PER_RUN_WITHOUT_REVIEW = 100


@dataclass
class BackfillSummary:
    """Operator-facing summary emitted as JSON at the end of the run."""

    total_processed: int = 0
    total_updated: int = 0
    total_skipped_recent: int = 0
    credits_used: int = 0
    llm_calls: int = 0
    started_at: str = ""
    ended_at: str = ""
    errors: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        """Return the exact JSON-compatible summary shape."""
        return asdict(self)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list | tuple | set):
        return len(value) == 0
    return False


def _normalise_enriched_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_recently_enriched(
    company: dict[str, Any],
    *,
    now: datetime,
    skip_if_newer_than_days: int,
) -> bool:
    """Return true when a company was enriched inside the skip window."""
    enriched_at = _normalise_enriched_at(company.get("enriched_at"))
    if enriched_at is None:
        return False
    return enriched_at >= now - timedelta(days=skip_if_newer_than_days)


def sort_company_rows(companies: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort companies by founded_year descending with null years last, then name."""

    def key(company: dict[str, Any]) -> tuple[int, int, str]:
        founded_year = company.get("founded_year")
        if isinstance(founded_year, int):
            return (0, -founded_year, str(company.get("name") or "").lower())
        return (1, 0, str(company.get("name") or "").lower())

    return sorted(companies, key=key)


def limit_company_rows(
    companies: Iterable[dict[str, Any]],
    *,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Apply a process limit after deterministic recency sorting."""
    sorted_rows = sort_company_rows(companies)
    if limit is None:
        return sorted_rows
    return sorted_rows[:limit]


def _maybe_set(
    updates: dict[str, Any],
    *,
    column: str,
    existing: Any,
    incoming: Any,
    force_overwrite: bool,
) -> None:
    if _is_empty(incoming):
        return
    if force_overwrite or _is_empty(existing):
        updates[column] = incoming


def _has_enrichment_signal(facts: CompanyFacts) -> bool:
    """Return true when Firecrawl produced at least one usable fact."""
    values = (
        facts.founded_year,
        facts.description,
        facts.founders,
        facts.city,
        facts.country,
        facts.sector_keywords,
        facts.last_funding_summary,
        facts.total_raised_usd,
        facts.total_raised_currency_raw,
        facts.total_raised_source_url,
        facts.valuation_usd,
        facts.valuation_currency_raw,
        facts.valuation_source_url,
        facts.headcount_estimate,
        facts.headcount_min,
        facts.headcount_max,
        facts.headcount_source_url,
        facts.evidence_urls,
    )
    return any(not _is_empty(value) for value in values)


def build_update_payload(
    company: dict[str, Any],
    facts: CompanyFacts,
    *,
    force_overwrite: bool,
) -> dict[str, Any]:
    """Build the safe update payload for one enriched company row."""
    updates: dict[str, Any] = {}
    has_fact_signal = _has_enrichment_signal(facts)
    _maybe_set(
        updates,
        column="founded_year",
        existing=company.get("founded_year"),
        incoming=facts.founded_year,
        force_overwrite=force_overwrite,
    )
    _maybe_set(
        updates,
        column="summary",
        existing=company.get("summary"),
        incoming=facts.description,
        force_overwrite=force_overwrite,
    )
    _maybe_set(
        updates,
        column="city",
        existing=company.get("city"),
        incoming=facts.city,
        force_overwrite=force_overwrite,
    )
    _maybe_set(
        updates,
        column="country",
        existing=company.get("country"),
        incoming=facts.country,
        force_overwrite=force_overwrite,
    )
    _maybe_set(
        updates,
        column="founders",
        existing=company.get("founders"),
        incoming=facts.founders,
        force_overwrite=force_overwrite,
    )
    for column in (
        "total_raised_usd",
        "total_raised_currency_raw",
        "total_raised_as_of",
        "total_raised_source_url",
        "valuation_usd",
        "valuation_currency_raw",
        "valuation_as_of",
        "valuation_source_url",
        "headcount_estimate",
        "headcount_min",
        "headcount_max",
        "headcount_as_of",
        "headcount_source_url",
    ):
        _maybe_set(
            updates,
            column=column,
            existing=company.get(column),
            incoming=getattr(facts, column),
            force_overwrite=force_overwrite,
        )

    if has_fact_signal:
        city_for_geo = str(updates.get("city") or company.get("city") or "").strip()
        geo = geocode_city(city_for_geo, jitter_seed=str(company.get("name") or ""))
        if geo is not None:
            if force_overwrite or _is_empty(company.get("lat")):
                updates["lat"] = geo.lat
            if force_overwrite or _is_empty(company.get("lon")):
                updates["lon"] = geo.lon

    if facts.evidence_urls:
        updates["evidence_urls"] = facts.evidence_urls
        updates["profile_sources"] = facts.evidence_urls
    if facts.confidence:
        updates["profile_confidence"] = facts.confidence
    return updates


def _iso_now() -> datetime:
    return datetime.now(UTC)


def _company_label(company: dict[str, Any]) -> str:
    founded_year = company.get("founded_year")
    year = str(founded_year) if founded_year is not None else "unknown year"
    return f"{company.get('name')} ({year})"


def _guard_review_limits(
    *,
    companies_to_enrich: int,
    force_overwrite: bool,
    dry_run: bool,
) -> list[str]:
    errors: list[str] = []
    if force_overwrite and companies_to_enrich > FORCE_OVERWRITE_REVIEW_LIMIT:
        errors.append(
            "--force-overwrite would touch more than 10 companies; ask the maintainer before running it"
        )
    if not dry_run and companies_to_enrich > MAX_COMPANIES_PER_RUN_WITHOUT_REVIEW:
        errors.append(
            "run would backfill more than 100 companies; ask the maintainer before running it"
        )
    return errors


def run_backfill(
    *,
    limit: int | None,
    max_age_years: int,
    skip_if_newer_than_days: int,
    dry_run: bool,
    force_overwrite: bool,
) -> BackfillSummary:
    """Run the enrichment backfill and return the operator summary."""
    started_at = _iso_now()
    summary = BackfillSummary(started_at=started_at.isoformat())

    with supabase_db.connection() as conn:
        if not dry_run:
            supabase_db.apply_schema(conn)

        rows = supabase_db.list_companies_for_enrichment(
            conn,
            max_age_years=max_age_years,
            limit=limit,
        )
        companies = limit_company_rows(rows, limit=limit)
        now = _iso_now()
        recent = [
            company
            for company in companies
            if is_recently_enriched(
                company,
                now=now,
                skip_if_newer_than_days=skip_if_newer_than_days,
            )
        ]
        companies_to_enrich = [company for company in companies if company not in recent]
        summary.total_skipped_recent = len(recent)

        guard_errors = _guard_review_limits(
            companies_to_enrich=len(companies_to_enrich),
            force_overwrite=force_overwrite,
            dry_run=dry_run,
        )
        if guard_errors:
            summary.errors.extend(guard_errors)
            for error in guard_errors:
                LOGGER.error(error)
            summary.ended_at = _iso_now().isoformat()
            return summary

        firecrawl_client = FirecrawlClient()
        llm_client = ClaudeClient()
        estimated_credits = len(companies_to_enrich) * DEFAULT_CREDITS_PER_ENRICH
        if dry_run:
            LOGGER.info(
                "--dry-run: no company rows will be updated; estimated Firecrawl credits=%d",
                estimated_credits,
            )

        total = len(companies)
        for index, company in enumerate(companies, start=1):
            name = str(company.get("name") or "")
            if company in recent:
                LOGGER.info("[%d/%d] skipping %s: enriched recently", index, total, name)
                continue

            if dry_run:
                summary.total_processed += 1
                remaining = max(
                    firecrawl_client.budget_credits
                    - summary.total_processed * DEFAULT_CREDITS_PER_ENRICH,
                    0,
                )
                LOGGER.info(
                    "[%d/%d] would enrich %s, estimated %d credits, budget remaining %d",
                    index,
                    total,
                    _company_label(company),
                    DEFAULT_CREDITS_PER_ENRICH,
                    remaining,
                )
                continue

            website = company.get("website")
            try:
                facts = firecrawl_enrich(
                    firecrawl_client,
                    llm_client,
                    str(website) if website else None,
                    name=name,
                )
            except FirecrawlBudgetExceeded as exc:
                summary.errors.append(
                    f"firecrawl budget exceeded after {firecrawl_client.stats.credits_used} credits: {exc}"
                )
                break
            except BudgetExceeded as exc:
                summary.errors.append(f"llm budget exceeded: {exc}")
                break
            except Exception as exc:  # noqa: BLE001
                summary.errors.append(f"{name}: {type(exc).__name__}: {exc}")
                LOGGER.warning("enrichment failed for %s: %s", name, exc)
                continue

            updates = build_update_payload(
                company,
                facts,
                force_overwrite=force_overwrite,
            )
            summary.total_processed += 1
            if not updates:
                LOGGER.info(
                    "[%d/%d] enriching %s... no usable updates, skipping write",
                    index,
                    total,
                    name,
                )
                continue
            supabase_db.update_company_enrichment(
                conn,
                str(company["id"]),
                updates=updates,
                enriched_at=_iso_now(),
            )
            conn.commit()
            summary.total_updated += 1
            remaining = max(
                firecrawl_client.budget_credits - firecrawl_client.stats.credits_used, 0
            )
            LOGGER.info(
                "[%d/%d] enriching %s... done, %d credits used, budget remaining %d",
                index,
                total,
                name,
                firecrawl_client.stats.credits_used,
                remaining,
            )

        summary.credits_used = firecrawl_client.stats.credits_used
        summary.llm_calls = llm_client.stats.calls

    summary.ended_at = _iso_now().isoformat()
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read target companies and estimate credits without writing company rows",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of companies to consider this run",
    )
    parser.add_argument(
        "--max-age-years",
        type=int,
        default=DEFAULT_MAX_AGE_YEARS,
        help="Only include companies founded within this many years, plus unknown years",
    )
    parser.add_argument(
        "--skip-if-newer-than-days",
        type=int,
        default=DEFAULT_SKIP_IF_NEWER_THAN_DAYS,
        help="Skip rows enriched within this many days",
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="Overwrite existing human-curated fields for at most 10 companies",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    if args.limit is not None and args.limit < 1:
        LOGGER.error("--limit must be a positive integer")
        return 2
    if args.max_age_years < 0:
        LOGGER.error("--max-age-years must be zero or greater")
        return 2
    if args.skip_if_newer_than_days < 0:
        LOGGER.error("--skip-if-newer-than-days must be zero or greater")
        return 2

    summary = run_backfill(
        limit=args.limit,
        max_age_years=args.max_age_years,
        skip_if_newer_than_days=args.skip_if_newer_than_days,
        dry_run=args.dry_run,
        force_overwrite=args.force_overwrite,
    )
    print(json.dumps(summary.to_json_dict(), indent=2, sort_keys=True))
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
