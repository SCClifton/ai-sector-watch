"""Tests for the dashboard's read-side data source."""

from __future__ import annotations

from ai_sector_watch.storage.data_source import (
    SupabaseSource,
    YamlSource,
    get_data_source,
)


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
