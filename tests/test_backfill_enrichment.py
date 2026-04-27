"""Tests for the operator-run enrichment backfill script."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import backfill_enrichment as backfill  # noqa: E402

from ai_sector_watch.extraction.firecrawl_client import DEFAULT_CREDITS_PER_ENRICH  # noqa: E402
from ai_sector_watch.extraction.schema import CompanyFacts  # noqa: E402


class FakeConn:
    """Minimal connection stub for backfill tests."""

    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class FakeFirecrawlClient:
    """FirecrawlClient stand-in with only the fields the script reads."""

    def __init__(self) -> None:
        self.budget_credits = 200
        self.stats = SimpleNamespace(credits_used=0, calls=0)


class FakeClaudeClient:
    """ClaudeClient stand-in with only the fields the script reads."""

    def __init__(self) -> None:
        self.stats = SimpleNamespace(calls=0)


def _company(
    name: str,
    *,
    founded_year: int | None,
    enriched_at: datetime | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"id-{name}",
        "name": name,
        "website": f"https://{name.lower().replace(' ', '')}.example",
        "country": "AU",
        "city": "Sydney",
        "lat": -33.86,
        "lon": 151.2,
        "sector_tags": ["agents"],
        "stage": "seed",
        "founded_year": founded_year,
        "summary": summary,
        "evidence_urls": [],
        "enriched_at": enriched_at,
    }


def test_sort_company_rows_orders_recent_first_and_null_last() -> None:
    rows = [
        _company("No Year", founded_year=None),
        _company("Older", founded_year=2017),
        _company("Newest B", founded_year=2026),
        _company("Newest A", founded_year=2026),
        _company("Middle", founded_year=2020),
    ]

    sorted_rows = backfill.sort_company_rows(rows)

    assert [row["name"] for row in sorted_rows] == [
        "Newest A",
        "Newest B",
        "Middle",
        "Older",
        "No Year",
    ]


def test_build_update_payload_fills_empty_fields_and_keeps_curated_fields() -> None:
    company = _company("Curated", founded_year=None, summary="Human-written summary")
    company["city"] = ""
    company["lat"] = None
    company["lon"] = None
    facts = CompanyFacts(
        founded_year=2021,
        description="Model summary",
        city="Melbourne",
        country="NZ",
        evidence_urls=["https://source.example"],
        confidence=1.0,
    )

    updates = backfill.build_update_payload(company, facts, force_overwrite=False)

    assert updates["founded_year"] == 2021
    assert updates["city"] == "Melbourne"
    assert updates["evidence_urls"] == ["https://source.example"]
    assert updates["lat"] != company["lat"]
    assert updates["lon"] != company["lon"]
    assert "summary" not in updates
    assert "country" not in updates


def test_build_update_payload_force_overwrite_replaces_curated_fields() -> None:
    company = _company("Curated", founded_year=2019, summary="Human-written summary")
    facts = CompanyFacts(
        founded_year=2023,
        description="Model summary",
        city="Melbourne",
        country="NZ",
        evidence_urls=["https://source.example"],
        confidence=1.0,
    )

    updates = backfill.build_update_payload(company, facts, force_overwrite=True)

    assert updates["founded_year"] == 2023
    assert updates["summary"] == "Model summary"
    assert updates["city"] == "Melbourne"
    assert updates["country"] == "NZ"


def test_dry_run_limit_only_processes_limited_company_count(monkeypatch) -> None:
    fake_conn = FakeConn()
    rows = [_company(f"Company {idx}", founded_year=2026 - idx) for idx in range(8)]

    @contextmanager
    def fake_connection():
        yield fake_conn

    monkeypatch.setattr(backfill.supabase_db, "connection", fake_connection)
    monkeypatch.setattr(
        backfill.supabase_db,
        "list_companies_for_enrichment",
        lambda conn, *, max_age_years, limit: rows,
    )
    monkeypatch.setattr(backfill, "FirecrawlClient", FakeFirecrawlClient)
    monkeypatch.setattr(backfill, "ClaudeClient", FakeClaudeClient)

    summary = backfill.run_backfill(
        limit=5,
        max_age_years=10,
        skip_if_newer_than_days=30,
        dry_run=True,
        force_overwrite=False,
    )

    assert summary.total_processed == 5
    assert summary.total_updated == 0
    assert summary.credits_used == 0
    assert fake_conn.commits == 0


def test_recently_enriched_rows_are_skipped(monkeypatch) -> None:
    fake_conn = FakeConn()
    now = datetime.now(UTC)
    rows = [
        _company("Fresh", founded_year=2024, enriched_at=now - timedelta(days=2)),
        _company("Stale", founded_year=2023, enriched_at=now - timedelta(days=60)),
    ]
    captured: list[dict[str, Any]] = []

    @contextmanager
    def fake_connection():
        yield fake_conn

    monkeypatch.setattr(backfill.supabase_db, "connection", fake_connection)
    monkeypatch.setattr(backfill.supabase_db, "apply_schema", lambda conn: None)
    monkeypatch.setattr(
        backfill.supabase_db,
        "list_companies_for_enrichment",
        lambda conn, *, max_age_years, limit: rows,
    )

    def fake_update(conn, company_id, *, updates, enriched_at):
        captured.append({"company_id": company_id, "updates": updates, "enriched_at": enriched_at})

    monkeypatch.setattr(backfill.supabase_db, "update_company_enrichment", fake_update)
    monkeypatch.setattr(backfill, "FirecrawlClient", FakeFirecrawlClient)
    monkeypatch.setattr(backfill, "ClaudeClient", FakeClaudeClient)

    def fake_enrich(client, llm_client, website, *, name):
        client.stats.credits_used += DEFAULT_CREDITS_PER_ENRICH
        client.stats.calls += 1
        llm_client.stats.calls += 1
        return CompanyFacts(description="Enriched", evidence_urls=["https://source.example"])

    monkeypatch.setattr(backfill, "firecrawl_enrich", fake_enrich)

    summary = backfill.run_backfill(
        limit=None,
        max_age_years=10,
        skip_if_newer_than_days=30,
        dry_run=False,
        force_overwrite=False,
    )

    assert summary.total_skipped_recent == 1
    assert summary.total_processed == 1
    assert summary.total_updated == 1
    assert captured[0]["company_id"] == "id-Stale"


def test_mocked_enrichment_updates_empty_fields(monkeypatch) -> None:
    fake_conn = FakeConn()
    rows = [_company("Target", founded_year=None, summary=None)]
    captured: list[dict[str, Any]] = []

    @contextmanager
    def fake_connection():
        yield fake_conn

    monkeypatch.setattr(backfill.supabase_db, "connection", fake_connection)
    monkeypatch.setattr(backfill.supabase_db, "apply_schema", lambda conn: None)
    monkeypatch.setattr(
        backfill.supabase_db,
        "list_companies_for_enrichment",
        lambda conn, *, max_age_years, limit: rows,
    )

    def fake_update(conn, company_id, *, updates, enriched_at):
        captured.append({"company_id": company_id, "updates": updates, "enriched_at": enriched_at})

    monkeypatch.setattr(backfill.supabase_db, "update_company_enrichment", fake_update)
    monkeypatch.setattr(backfill, "FirecrawlClient", FakeFirecrawlClient)
    monkeypatch.setattr(backfill, "ClaudeClient", FakeClaudeClient)

    def fake_enrich(client, llm_client, website, *, name):
        client.stats.credits_used += DEFAULT_CREDITS_PER_ENRICH
        client.stats.calls += 1
        llm_client.stats.calls += 1
        return CompanyFacts(
            founded_year=2022,
            description="Target builds AI tools.",
            city="Sydney",
            country="AU",
            evidence_urls=["https://target.example/about"],
            confidence=1.0,
        )

    monkeypatch.setattr(backfill, "firecrawl_enrich", fake_enrich)

    summary = backfill.run_backfill(
        limit=5,
        max_age_years=10,
        skip_if_newer_than_days=30,
        dry_run=False,
        force_overwrite=False,
    )

    assert summary.total_processed == 1
    assert summary.total_updated == 1
    assert summary.credits_used == DEFAULT_CREDITS_PER_ENRICH
    assert summary.llm_calls == 1
    assert fake_conn.commits == 1
    assert captured[0]["company_id"] == "id-Target"
    assert captured[0]["updates"]["founded_year"] == 2022
    assert captured[0]["updates"]["summary"] == "Target builds AI tools."
    assert captured[0]["updates"]["evidence_urls"] == ["https://target.example/about"]
    assert captured[0]["enriched_at"].tzinfo is not None
