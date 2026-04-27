"""Tests for the dashboard's read-side data source."""

from __future__ import annotations

from decimal import Decimal
from types import TracebackType
from typing import Any

import pytest

from ai_sector_watch.storage import supabase_db
from ai_sector_watch.storage.data_source import (
    SupabaseSource,
    YamlSource,
    get_data_source,
    safe_llm_spend_summary,
)


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.row: dict[str, Any] | None = None
        self.query: str | None = None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> None:
        self.query = query
        costs = [
            row["cost_usd"]
            for row in self.rows
            if row["kind"] == "weekly_run" and row["cost_usd"] is not None
        ]
        if not costs:
            self.row = {"run_count": 0, "total_usd": None, "average_usd": None}
            return
        total = sum(costs, Decimal("0"))
        self.row = {
            "run_count": len(costs),
            "total_usd": total,
            "average_usd": total / Decimal(len(costs)),
        }

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.cursor_instance = FakeCursor(rows)

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


@pytest.fixture
def ingest_event_rows() -> list[dict[str, Any]]:
    return [
        {"kind": "weekly_run", "cost_usd": Decimal("1.0000")},
        {"kind": "weekly_run", "cost_usd": Decimal("0.2345")},
        {"kind": "rss_fetch", "cost_usd": Decimal("9.0000")},
        {"kind": "weekly_run", "cost_usd": None},
    ]


def test_yaml_source_returns_companies_with_coords() -> None:
    source = YamlSource()
    companies = source.list_companies()
    assert len(companies) >= 50
    # Sample of structural assertions.
    sydney_co = next(c for c in companies if c.city == "Sydney")
    assert sydney_co.lat is not None and sydney_co.lon is not None
    assert sydney_co.country in {"AU", "NZ"}
    assert sydney_co.discovery_status == "verified"


def test_yaml_source_skips_non_verified_status() -> None:
    source = YamlSource()
    assert source.list_companies(statuses=("auto_discovered_pending_review",)) == []


def test_yaml_source_returns_no_news() -> None:
    source = YamlSource()
    assert source.recent_news() == []


def test_yaml_source_returns_no_llm_spend() -> None:
    source = YamlSource()
    assert source.llm_spend_summary() is None


def test_supabase_source_reads_llm_spend_summary(
    monkeypatch: pytest.MonkeyPatch,
    ingest_event_rows: list[dict[str, Any]],
) -> None:
    connection = FakeConnection(ingest_event_rows)

    def fake_connection() -> FakeConnection:
        return connection

    monkeypatch.setattr(supabase_db, "connection", fake_connection)

    summary = SupabaseSource().llm_spend_summary()

    assert summary is not None
    assert summary.run_count == 2
    assert summary.total_usd == Decimal("1.2345")
    assert summary.average_usd == Decimal("0.61725")
    assert connection.cursor_instance.query is not None
    assert "kind = 'weekly_run'" in connection.cursor_instance.query
    assert "INTERVAL '4 weeks'" in connection.cursor_instance.query


def test_supabase_source_returns_no_llm_spend_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_connection() -> FakeConnection:
        return FakeConnection([])

    monkeypatch.setattr(supabase_db, "connection", fake_connection)

    assert SupabaseSource().llm_spend_summary() is None


def test_safe_llm_spend_summary_catches_backend_failure() -> None:
    class BoomSource:
        backend = "boom"

        def list_companies(self, *, statuses=("verified",)):
            return []

        def recent_news(self, *, limit=50):
            return []

        def llm_spend_summary(self):
            raise RuntimeError("database unavailable")

    summary, error = safe_llm_spend_summary(BoomSource())

    assert summary is None
    assert isinstance(error, RuntimeError)


def test_factory_returns_yaml_when_supabase_url_unset(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("AISW_FORCE_YAML", raising=False)
    source = get_data_source()
    assert isinstance(source, YamlSource)


def test_factory_returns_supabase_when_url_set(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example")
    monkeypatch.delenv("AISW_FORCE_YAML", raising=False)
    source = get_data_source()
    assert isinstance(source, SupabaseSource)


def test_force_yaml_env_overrides_supabase_url(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example")
    monkeypatch.setenv("AISW_FORCE_YAML", "1")
    source = get_data_source()
    assert isinstance(source, YamlSource)
