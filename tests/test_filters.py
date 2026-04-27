"""Tests for the filter pure-functions (no Streamlit runtime required)."""

from __future__ import annotations

from ai_sector_watch.storage.data_source import Company, YamlSource
from dashboard.components.filters import (
    FilterState,
    apply_filters,
    companies_to_table_rows,
    derive_meta,
)


def _make(**overrides) -> Company:
    base = dict(
        id="x",
        name="Test Co",
        country="AU",
        city="Sydney",
        lat=-33.87,
        lon=151.21,
        website="https://example.com",
        sector_tags=["foundation_models"],
        stage="seed",
        founded_year=2024,
        summary=None,
        discovery_status="verified",
        discovery_source="seed",
    )
    base.update(overrides)
    return Company(**base)


def test_apply_filters_no_state_returns_input() -> None:
    cs = [_make(name="A"), _make(name="B")]
    assert apply_filters(cs, FilterState()) == cs


def test_apply_filters_sector() -> None:
    cs = [
        _make(name="FM", sector_tags=["foundation_models"]),
        _make(name="Vec", sector_tags=["vector_search_and_retrieval"]),
    ]
    out = apply_filters(cs, FilterState(sectors=("foundation_models",)))
    assert [c.name for c in out] == ["FM"]


def test_apply_filters_stage() -> None:
    cs = [_make(name="S", stage="seed"), _make(name="A", stage="series_a")]
    out = apply_filters(cs, FilterState(stages=("series_a",)))
    assert [c.name for c in out] == ["A"]


def test_apply_filters_country() -> None:
    cs = [_make(name="AU", country="AU"), _make(name="NZ", country="NZ")]
    out = apply_filters(cs, FilterState(countries=("NZ",)))
    assert [c.name for c in out] == ["NZ"]


def test_apply_filters_founded_year_range_keeps_unknowns() -> None:
    """Companies with no founded_year should pass the year filter (no info != fail)."""
    cs = [
        _make(name="2010", founded_year=2010),
        _make(name="2024", founded_year=2024),
        _make(name="None", founded_year=None),
    ]
    out = apply_filters(cs, FilterState(founded_min=2020, founded_max=2024))
    assert {c.name for c in out} == {"2024", "None"}


def test_apply_filters_name_query_case_insensitive_and_partial() -> None:
    cs = [_make(name="Marqo"), _make(name="Relevance AI")]
    out = apply_filters(cs, FilterState(name_query="MARQ"))
    assert [c.name for c in out] == ["Marqo"]


def test_apply_filters_combines_predicates() -> None:
    cs = [
        _make(name="A", country="AU", stage="seed"),
        _make(name="B", country="AU", stage="series_a"),
        _make(name="C", country="NZ", stage="seed"),
    ]
    out = apply_filters(cs, FilterState(countries=("AU",), stages=("seed",)))
    assert [c.name for c in out] == ["A"]


def test_filter_state_is_active_detects_any_set_field() -> None:
    assert not FilterState().is_active
    assert FilterState(sectors=("foundation_models",)).is_active
    assert FilterState(name_query="x").is_active
    assert FilterState(name_query="   ").is_active is False  # whitespace-only is empty


def test_derive_meta_returns_country_set_and_year_bounds() -> None:
    cs = [
        _make(name="A", country="AU", founded_year=2018),
        _make(name="B", country="NZ", founded_year=2024),
    ]
    meta = derive_meta(cs)
    assert meta.countries == ("AU", "NZ")
    assert meta.founded_min == 2018
    assert meta.founded_max == 2024


def test_companies_to_table_rows_renders_sector_labels() -> None:
    rows = companies_to_table_rows([_make(sector_tags=["foundation_models"])])
    assert rows[0]["Sectors"] == "Foundation models"
    assert rows[0]["Name"] == "Test Co"


def test_full_pipeline_against_yaml_source() -> None:
    source = YamlSource()
    companies = source.list_companies()
    nz_only = apply_filters(companies, FilterState(countries=("NZ",)))
    assert all(c.country == "NZ" for c in nz_only)
    assert len(nz_only) >= 1
