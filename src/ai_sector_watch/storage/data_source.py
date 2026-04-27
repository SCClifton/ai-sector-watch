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

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

import yaml

from ai_sector_watch.config import REPO_ROOT
from ai_sector_watch.discovery.geocoder import geocode_city
from ai_sector_watch.storage import supabase_db

SEED_PATH = REPO_ROOT / "data" / "seed" / "companies.yaml"


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


class DataSource(Protocol):
    backend: str

    def list_companies(self, *, statuses: tuple[str, ...] = ("verified",)) -> list[Company]: ...

    def recent_news(self, *, limit: int = 50) -> list[NewsItem]: ...


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


# ---------------------------------------------------------------------------
# Supabase backend
# ---------------------------------------------------------------------------


class SupabaseSource:
    """Read-only source backed by Supabase Postgres."""

    backend = "supabase"

    def list_companies(self, *, statuses: tuple[str, ...] = ("verified",)) -> list[Company]:
        with supabase_db.connection() as conn:
            rows = supabase_db.list_companies(conn, statuses=statuses)
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


def _company_from_row(r: dict) -> Company:
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
    )


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
