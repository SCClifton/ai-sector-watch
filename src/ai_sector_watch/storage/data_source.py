"""Read-side data access for the dashboard.

Two backends:

- `SupabaseSource` — production, reads via psycopg from Supabase.
- `YamlSource` — local dev fallback, reads `data/seed/companies.yaml` and
  pretends every entry is a verified company. Used when `SUPABASE_DB_URL`
  is unset so the dashboard renders during early local development.

Both backends return plain `Company` and `NewsItem` dataclasses so dashboard
code never has to know which source it is reading from.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import yaml

from ai_sector_watch.config import REPO_ROOT
from ai_sector_watch.discovery.geocoder import geocode_city
from ai_sector_watch.storage import supabase_db

SEED_PATH = REPO_ROOT / "data" / "seed" / "companies.yaml"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FundingEvent:
    """Latest funding event attached to a company."""

    id: str
    announced_on: date | None
    stage: str | None
    amount_usd: Decimal | None
    currency_raw: str | None
    lead_investor: str | None
    investors: list[str]
    source_url: str | None


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    country: str | None
    city: str | None
    lat: float | None
    lon: float | None
    website: str | None
    sector_tags: list[str]
    stage: str | None
    founded_year: int | None
    summary: str | None
    discovery_status: str
    discovery_source: str | None
    latest_funding_event: FundingEvent | None = None


@dataclass(frozen=True)
class NewsItem:
    id: str
    source_slug: str
    source_url: str
    title: str
    summary: str | None
    published_at: datetime | None
    kind: str
    company_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LlmSpendSummary:
    """Aggregate LLM spend for recent weekly pipeline runs."""

    total_usd: Decimal
    average_usd: Decimal
    run_count: int


class DataSource(Protocol):
    backend: str

    def list_companies(self, *, statuses: tuple[str, ...] = ("verified",)) -> list[Company]: ...

    def recent_news(self, *, limit: int = 50) -> list[NewsItem]: ...

    def llm_spend_summary(self) -> LlmSpendSummary | None: ...


# ---------------------------------------------------------------------------
# YAML fallback
# ---------------------------------------------------------------------------


class YamlSource:
    """Read-only source backed by data/seed/companies.yaml."""

    backend = "yaml"

    def __init__(self, path: Path = SEED_PATH) -> None:
        self.path = path

    def _load(self) -> list[Company]:
        with self.path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        entries = data.get("companies", [])
        out: list[Company] = []
        for i, entry in enumerate(entries):
            geo = geocode_city(entry.get("city"), jitter_seed=entry.get("name"))
            out.append(
                Company(
                    id=f"yaml-{i}",
                    name=entry["name"],
                    country=entry.get("country"),
                    city=geo.city if geo else entry.get("city"),
                    lat=geo.lat if geo else None,
                    lon=geo.lon if geo else None,
                    website=entry.get("website"),
                    sector_tags=list(entry.get("sector_tags") or []),
                    stage=entry.get("stage"),
                    founded_year=entry.get("founded_year"),
                    summary=(entry.get("description_seed") or "").strip() or None,
                    discovery_status="verified",
                    discovery_source="seed",
                )
            )
        return out

    def list_companies(self, *, statuses: tuple[str, ...] = ("verified",)) -> list[Company]:
        if "verified" not in statuses:
            return []
        return self._load()

    def recent_news(self, *, limit: int = 50) -> list[NewsItem]:
        return []

    def llm_spend_summary(self) -> LlmSpendSummary | None:
        return None


# ---------------------------------------------------------------------------
# Supabase backend
# ---------------------------------------------------------------------------


class SupabaseSource:
    """Read-only source backed by Supabase Postgres."""

    backend = "supabase"

    def list_companies(self, *, statuses: tuple[str, ...] = ("verified",)) -> list[Company]:
        with supabase_db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.*,
                    fe.id AS latest_funding_id,
                    fe.announced_on AS latest_funding_announced_on,
                    fe.stage AS latest_funding_stage,
                    fe.amount_usd AS latest_funding_amount_usd,
                    fe.currency_raw AS latest_funding_currency_raw,
                    fe.lead_investor AS latest_funding_lead_investor,
                    fe.investors AS latest_funding_investors,
                    fe.source_url AS latest_funding_source_url
                FROM companies c
                LEFT JOIN LATERAL (
                    SELECT id, announced_on, stage, amount_usd, currency_raw,
                           lead_investor, investors, source_url, created_at
                    FROM funding_events
                    WHERE company_id = c.id
                    ORDER BY announced_on DESC NULLS LAST, created_at DESC
                    LIMIT 1
                ) fe ON TRUE
                WHERE c.discovery_status = ANY(%s)
                ORDER BY c.name
                """,
                (list(statuses),),
            )
            rows = cur.fetchall()
        return [_company_from_row(r) for r in rows]

    def recent_news(self, *, limit: int = 50) -> list[NewsItem]:
        with supabase_db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_slug, source_url, title, summary,
                       published_at, kind, company_ids
                FROM news_items
                ORDER BY published_at DESC NULLS LAST, fetched_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [
            NewsItem(
                id=str(r["id"]),
                source_slug=r["source_slug"],
                source_url=r["source_url"],
                title=r["title"],
                summary=r["summary"],
                published_at=r["published_at"],
                kind=r["kind"],
                company_ids=[str(cid) for cid in (r["company_ids"] or [])],
            )
            for r in rows
        ]

    def llm_spend_summary(self) -> LlmSpendSummary | None:
        with supabase_db.connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(cost_usd)::int AS run_count,
                    SUM(cost_usd) AS total_usd,
                    AVG(cost_usd) AS average_usd
                FROM ingest_events
                WHERE kind = 'weekly_run'
                  AND cost_usd IS NOT NULL
                  AND fetched_at >= NOW() - INTERVAL '4 weeks'
                """)
            row = cur.fetchone()
        if not row or row["run_count"] == 0:
            return None
        return LlmSpendSummary(
            total_usd=row["total_usd"],
            average_usd=row["average_usd"],
            run_count=row["run_count"],
        )


def _company_from_row(r: dict) -> Company:
    latest_funding_event = None
    if r.get("latest_funding_id"):
        latest_funding_event = FundingEvent(
            id=str(r["latest_funding_id"]),
            announced_on=r.get("latest_funding_announced_on"),
            stage=r.get("latest_funding_stage"),
            amount_usd=r.get("latest_funding_amount_usd"),
            currency_raw=r.get("latest_funding_currency_raw"),
            lead_investor=r.get("latest_funding_lead_investor"),
            investors=list(r.get("latest_funding_investors") or []),
            source_url=r.get("latest_funding_source_url"),
        )
    return Company(
        id=str(r["id"]),
        name=r["name"],
        country=r.get("country"),
        city=r.get("city"),
        lat=r.get("lat"),
        lon=r.get("lon"),
        website=r.get("website"),
        sector_tags=list(r.get("sector_tags") or []),
        stage=r.get("stage"),
        founded_year=r.get("founded_year"),
        summary=r.get("summary"),
        discovery_status=r["discovery_status"],
        discovery_source=r.get("discovery_source"),
        latest_funding_event=latest_funding_event,
    )


def safe_llm_spend_summary(source: DataSource) -> tuple[LlmSpendSummary | None, Exception | None]:
    """Return spend summary without letting a backend failure break dashboard rendering."""
    try:
        return source.llm_spend_summary(), None
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("llm spend summary unavailable from %s: %s", source.backend, exc)
        return None, exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_data_source() -> DataSource:
    """Return the appropriate backend.

    Falls back to YAML when `SUPABASE_DB_URL` is unset so the dashboard
    renders during early local dev. Set `AISW_FORCE_YAML=1` to force the
    YAML backend regardless of `SUPABASE_DB_URL`.
    """
    if os.environ.get("AISW_FORCE_YAML") == "1":
        return YamlSource()
    if not os.environ.get("SUPABASE_DB_URL"):
        return YamlSource()
    return SupabaseSource()
