"""Supabase Postgres data access layer.

Single connection helper plus typed upsert/query functions for `companies`,
`funding_events`, `news_items`, and `ingest_events`. Uses psycopg 3 with a
short retry/backoff wrapper (Supabase pooler endpoints occasionally drop the
first connection).

The schema lives in `supabase_schema.sql` next to this file. Apply it via
`scripts/verify_setup.py --apply-schema` or by piping it into psql.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import resources
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Json

LOGGER = logging.getLogger(__name__)

# ----- Connection helpers ----------------------------------------------------


def _get_db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise KeyError(
            "SUPABASE_DB_URL is not set. Run with `op run --account my.1password.com --env-file=.env.local -- ...`"
        )
    return url


def get_conn(*, autocommit: bool = False) -> psycopg.Connection:
    """Open a Supabase connection with retry/backoff.

    Retries up to 6 times with exponential backoff (0.5s, 1s, 2s, 4s, 8s, 8s)
    to handle the pooler's occasional first-connection rejection.
    """
    db_url = _get_db_url()
    max_attempts = 6
    sleep_s = 0.5
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return psycopg.connect(
                db_url,
                autocommit=autocommit,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
                row_factory=dict_row,
            )
        except Exception as exc:  # noqa: BLE001 — broad ok at boundary
            last_exc = exc
            LOGGER.warning("supabase connect attempt %d/%d failed: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                time.sleep(min(sleep_s, 8.0))
                sleep_s *= 2
    assert last_exc is not None
    raise last_exc


@contextmanager
def connection(*, autocommit: bool = False) -> Iterator[psycopg.Connection]:
    """Context-managed connection that always closes."""
    conn = get_conn(autocommit=autocommit)
    try:
        yield conn
    finally:
        conn.close()


# ----- Schema management -----------------------------------------------------


def load_schema_sql() -> str:
    return (
        resources.files("ai_sector_watch.storage")
        .joinpath("supabase_schema.sql")
        .read_text(encoding="utf-8")
    )


def apply_schema(conn: psycopg.Connection) -> None:
    """Apply the canonical schema to the given connection. Idempotent."""
    sql = load_schema_sql()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


# ----- Hashing helpers (idempotency) -----------------------------------------


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """SHA256 of canonical JSON. Used for ingest event de-dup."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def normalise_name(name: str) -> str:
    return " ".join(name.lower().split())


# ----- Company upsert --------------------------------------------------------


def upsert_company(
    conn: psycopg.Connection,
    *,
    name: str,
    country: str | None,
    city: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    website: str | None = None,
    sector_tags: list[str] | None = None,
    stage: str | None = None,
    founded_year: int | None = None,
    summary: str | None = None,
    evidence_urls: list[str] | None = None,
    founders: list[str] | None = None,
    total_raised_usd: float | Decimal | None = None,
    total_raised_currency_raw: str | None = None,
    total_raised_as_of: date | None = None,
    total_raised_source_url: str | None = None,
    valuation_usd: float | Decimal | None = None,
    valuation_currency_raw: str | None = None,
    valuation_as_of: date | None = None,
    valuation_source_url: str | None = None,
    headcount_estimate: int | None = None,
    headcount_min: int | None = None,
    headcount_max: int | None = None,
    headcount_as_of: date | None = None,
    headcount_source_url: str | None = None,
    profile_confidence: float | Decimal | None = None,
    profile_sources: list[str] | None = None,
    profile_verified_at: datetime | None = None,
    discovery_status: str = "auto_discovered_pending_review",
    discovery_source: str | None = None,
) -> str:
    """Insert or update a company keyed by (normalised name, country).

    Returns the row's UUID as a string.
    """
    name_normalised = normalise_name(name)
    sector_tags = sector_tags or []
    evidence_urls = evidence_urls or []
    founders = founders or []
    profile_sources = profile_sources or []
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO companies (
                name, name_normalised, website, country, city, lat, lon,
                sector_tags, stage, founded_year, summary, evidence_urls,
                founders, total_raised_usd, total_raised_currency_raw,
                total_raised_as_of, total_raised_source_url, valuation_usd,
                valuation_currency_raw, valuation_as_of, valuation_source_url,
                headcount_estimate, headcount_min, headcount_max,
                headcount_as_of, headcount_source_url, profile_confidence,
                profile_sources, profile_verified_at,
                discovery_status, discovery_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (name_normalised, COALESCE(country, ''))
            DO UPDATE SET
                website          = COALESCE(EXCLUDED.website, companies.website),
                city             = COALESCE(EXCLUDED.city, companies.city),
                lat              = COALESCE(EXCLUDED.lat, companies.lat),
                lon              = COALESCE(EXCLUDED.lon, companies.lon),
                sector_tags      = CASE
                    WHEN EXCLUDED.sector_tags = '{}' THEN companies.sector_tags
                    ELSE EXCLUDED.sector_tags
                END,
                stage            = COALESCE(EXCLUDED.stage, companies.stage),
                founded_year     = COALESCE(EXCLUDED.founded_year, companies.founded_year),
                summary          = COALESCE(EXCLUDED.summary, companies.summary),
                evidence_urls    = CASE
                    WHEN EXCLUDED.evidence_urls = '{}' THEN companies.evidence_urls
                    ELSE EXCLUDED.evidence_urls
                END,
                founders         = CASE
                    WHEN EXCLUDED.founders = '{}' THEN companies.founders
                    ELSE EXCLUDED.founders
                END,
                total_raised_usd = COALESCE(EXCLUDED.total_raised_usd, companies.total_raised_usd),
                total_raised_currency_raw = COALESCE(EXCLUDED.total_raised_currency_raw, companies.total_raised_currency_raw),
                total_raised_as_of = COALESCE(EXCLUDED.total_raised_as_of, companies.total_raised_as_of),
                total_raised_source_url = COALESCE(EXCLUDED.total_raised_source_url, companies.total_raised_source_url),
                valuation_usd = COALESCE(EXCLUDED.valuation_usd, companies.valuation_usd),
                valuation_currency_raw = COALESCE(EXCLUDED.valuation_currency_raw, companies.valuation_currency_raw),
                valuation_as_of = COALESCE(EXCLUDED.valuation_as_of, companies.valuation_as_of),
                valuation_source_url = COALESCE(EXCLUDED.valuation_source_url, companies.valuation_source_url),
                headcount_estimate = COALESCE(EXCLUDED.headcount_estimate, companies.headcount_estimate),
                headcount_min = COALESCE(EXCLUDED.headcount_min, companies.headcount_min),
                headcount_max = COALESCE(EXCLUDED.headcount_max, companies.headcount_max),
                headcount_as_of = COALESCE(EXCLUDED.headcount_as_of, companies.headcount_as_of),
                headcount_source_url = COALESCE(EXCLUDED.headcount_source_url, companies.headcount_source_url),
                profile_confidence = COALESCE(EXCLUDED.profile_confidence, companies.profile_confidence),
                profile_sources = CASE
                    WHEN EXCLUDED.profile_sources = '{}' THEN companies.profile_sources
                    ELSE EXCLUDED.profile_sources
                END,
                profile_verified_at = COALESCE(EXCLUDED.profile_verified_at, companies.profile_verified_at),
                -- Only allow status to be promoted/demoted by an explicit
                -- caller; a re-seed shouldn't downgrade a verified row.
                discovery_status = CASE
                    WHEN companies.discovery_status = 'verified'
                         AND EXCLUDED.discovery_status = 'auto_discovered_pending_review'
                    THEN companies.discovery_status
                    ELSE EXCLUDED.discovery_status
                END,
                discovery_source = COALESCE(EXCLUDED.discovery_source, companies.discovery_source)
            RETURNING id
            """,
            (
                name,
                name_normalised,
                website,
                country,
                city,
                lat,
                lon,
                sector_tags,
                stage,
                founded_year,
                summary,
                evidence_urls,
                founders,
                total_raised_usd,
                total_raised_currency_raw,
                total_raised_as_of,
                total_raised_source_url,
                valuation_usd,
                valuation_currency_raw,
                valuation_as_of,
                valuation_source_url,
                headcount_estimate,
                headcount_min,
                headcount_max,
                headcount_as_of,
                headcount_source_url,
                profile_confidence,
                profile_sources,
                profile_verified_at,
                discovery_status,
                discovery_source,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return str(row["id"])


def set_company_status(conn: psycopg.Connection, company_id: str, status: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE companies SET discovery_status = %s WHERE id = %s",
            (status, company_id),
        )


def get_company_by_name(
    conn: psycopg.Connection, name: str, country: str | None = None
) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM companies
            WHERE name_normalised = %s
              AND COALESCE(country, '') = COALESCE(%s, '')
            LIMIT 1
            """,
            (normalise_name(name), country),
        )
        return cur.fetchone()


def list_companies(
    conn: psycopg.Connection,
    *,
    statuses: Iterable[str] = ("verified",),
) -> list[dict[str, Any]]:
    statuses = list(statuses)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM companies
            WHERE discovery_status = ANY(%s)
            ORDER BY name
            """,
            (statuses,),
        )
        return list(cur.fetchall())


def companies_has_column(conn: psycopg.Connection, column_name: str) -> bool:
    """Return true when a companies column exists."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'companies'
                  AND column_name = %s
            ) AS exists
            """,
            (column_name,),
        )
        row = cur.fetchone()
        return bool(row and row["exists"])


def companies_has_enriched_at(conn: psycopg.Connection) -> bool:
    """Return true when the companies.enriched_at column exists."""
    return companies_has_column(conn, "enriched_at")


def list_companies_for_enrichment(
    conn: psycopg.Connection,
    *,
    max_age_years: int,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """List verified companies in enrichment priority order."""
    evidence_urls_select = (
        sql.SQL("evidence_urls")
        if companies_has_column(conn, "evidence_urls")
        else sql.SQL("'{}'::TEXT[] AS evidence_urls")
    )
    enriched_at_select = (
        sql.SQL("enriched_at")
        if companies_has_enriched_at(conn)
        else sql.SQL("NULL::TIMESTAMPTZ AS enriched_at")
    )
    limit_clause = sql.SQL("LIMIT %s") if limit is not None else sql.SQL("")
    params: list[Any] = [max_age_years]
    if limit is not None:
        params.append(limit)
    query = sql.SQL("""
        SELECT
            id, name, website, country, city, lat, lon, sector_tags, stage,
            founded_year, summary, {evidence_urls_select}, {enriched_at_select},
            founders, total_raised_usd, total_raised_currency_raw,
            total_raised_as_of, total_raised_source_url, valuation_usd,
            valuation_currency_raw, valuation_as_of, valuation_source_url,
            headcount_estimate, headcount_min, headcount_max, headcount_as_of,
            headcount_source_url, profile_confidence, profile_sources,
            profile_verified_at
        FROM companies
        WHERE discovery_status = 'verified'
          AND (
              founded_year >= EXTRACT(YEAR FROM NOW())::int - %s
              OR founded_year IS NULL
          )
        ORDER BY founded_year DESC NULLS LAST, name ASC
        {limit_clause}
        """).format(
        evidence_urls_select=evidence_urls_select,
        enriched_at_select=enriched_at_select,
        limit_clause=limit_clause,
    )
    with conn.cursor() as cur:
        cur.execute(query, params)
        return list(cur.fetchall())


def update_company_enrichment(
    conn: psycopg.Connection,
    company_id: str,
    *,
    updates: dict[str, Any],
    enriched_at: datetime,
) -> None:
    """Update enrichment-backed company fields and stamp enriched_at."""
    allowed_columns = {
        "website",
        "country",
        "city",
        "lat",
        "lon",
        "sector_tags",
        "stage",
        "founded_year",
        "summary",
        "evidence_urls",
        "founders",
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
        "profile_confidence",
        "profile_sources",
        "profile_verified_at",
    }
    unknown = set(updates) - allowed_columns
    if unknown:
        raise ValueError(f"unsupported company enrichment columns: {sorted(unknown)}")

    assignments = [sql.SQL("{} = %s").format(sql.Identifier(column)) for column in updates]
    assignments.append(sql.SQL("enriched_at = %s"))
    values = [*updates.values(), enriched_at, company_id]
    query = sql.SQL("UPDATE companies SET {} WHERE id = %s").format(sql.SQL(", ").join(assignments))
    with conn.cursor() as cur:
        cur.execute(query, values)


# ----- Funding events -------------------------------------------------------


def upsert_funding_event(
    conn: psycopg.Connection,
    *,
    company_id: str,
    announced_on: date | None,
    stage: str | None,
    amount_usd: float | None = None,
    currency_raw: str | None = None,
    lead_investor: str | None = None,
    investors: list[str] | None = None,
    source_url: str | None = None,
) -> str:
    investors = investors or []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM funding_events
            WHERE company_id = %s
              AND announced_on IS NOT DISTINCT FROM %s
              AND stage IS NOT DISTINCT FROM %s
            LIMIT 1
            """,
            (company_id, announced_on, stage),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE funding_events
                SET
                    amount_usd    = COALESCE(%s, amount_usd),
                    currency_raw  = COALESCE(%s, currency_raw),
                    lead_investor = COALESCE(%s, lead_investor),
                    investors     = CASE
                        WHEN %s::text[] = '{}'::text[] THEN investors
                        ELSE %s::text[]
                    END,
                    source_url    = COALESCE(%s, source_url)
                WHERE id = %s
                """,
                (
                    amount_usd,
                    currency_raw,
                    lead_investor,
                    investors,
                    investors,
                    source_url,
                    existing["id"],
                ),
            )
            return str(existing["id"])

        cur.execute(
            """
            INSERT INTO funding_events (
                company_id, announced_on, stage, amount_usd, currency_raw,
                lead_investor, investors, source_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (company_id, announced_on, stage)
            DO UPDATE SET
                amount_usd    = COALESCE(EXCLUDED.amount_usd, funding_events.amount_usd),
                currency_raw  = COALESCE(EXCLUDED.currency_raw, funding_events.currency_raw),
                lead_investor = COALESCE(EXCLUDED.lead_investor, funding_events.lead_investor),
                investors     = CASE
                    WHEN EXCLUDED.investors = '{}' THEN funding_events.investors
                    ELSE EXCLUDED.investors
                END,
                source_url    = COALESCE(EXCLUDED.source_url, funding_events.source_url)
            RETURNING id
            """,
            (
                company_id,
                announced_on,
                stage,
                amount_usd,
                currency_raw,
                lead_investor,
                investors,
                source_url,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return str(row["id"])


# ----- News items ------------------------------------------------------------


def upsert_news_item(
    conn: psycopg.Connection,
    *,
    source_slug: str,
    source_url: str,
    title: str,
    summary: str | None = None,
    published_at: datetime | None = None,
    kind: str = "other",
    company_ids: list[str] | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> str:
    """Insert (or no-op if URL already seen) a news item. Returns row UUID."""
    company_ids = company_ids or []
    url_hash = hash_url(source_url)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO news_items (
                source_slug, source_url, url_hash, title, summary,
                published_at, kind, company_ids, raw_payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url_hash) DO UPDATE SET
                summary     = COALESCE(EXCLUDED.summary, news_items.summary),
                kind        = EXCLUDED.kind,
                company_ids = CASE
                    WHEN EXCLUDED.company_ids = '{}' THEN news_items.company_ids
                    ELSE EXCLUDED.company_ids
                END
            RETURNING id
            """,
            (
                source_slug,
                source_url,
                url_hash,
                title,
                summary,
                published_at,
                kind,
                company_ids,
                Json(raw_payload) if raw_payload else None,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return str(row["id"])


# ----- Ingest events ---------------------------------------------------------


def insert_ingest_event(
    conn: psycopg.Connection,
    *,
    source_slug: str,
    kind: str,
    payload: dict[str, Any],
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    status: str = "ok",
    error: str | None = None,
    items_seen: int = 0,
    items_new: int = 0,
    cost_usd: float | None = None,
) -> str:
    """De-dups by `(source_slug, kind, payload_hash)`. Returns the row UUID."""
    payload_hash = compute_payload_hash(payload)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM ingest_events
            WHERE source_slug = %s AND kind = %s AND payload_hash = %s
            LIMIT 1
            """,
            (source_slug, kind, payload_hash),
        )
        existing = cur.fetchone()
        if existing:
            return str(existing["id"])
        cur.execute(
            """
            INSERT INTO ingest_events (
                source_slug, kind, payload_hash, window_start, window_end,
                status, error, items_seen, items_new, cost_usd, fetched_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                source_slug,
                kind,
                payload_hash,
                window_start,
                window_end,
                status,
                error,
                items_seen,
                items_new,
                cost_usd,
                datetime.now(UTC),
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return str(row["id"])
