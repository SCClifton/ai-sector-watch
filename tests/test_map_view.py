"""Tests for the map_view component."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import TracebackType

import folium
import pytest

from ai_sector_watch.storage.data_source import Company, FundingEvent, YamlSource
from dashboard.components import sector_legend
from dashboard.components.map_view import (
    _popup_html,
    build_map,
    split_geocoded,
)
from dashboard.components.sector_legend import sector_legend_rows


def _make_company(**overrides) -> Company:
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
        summary="A test company.",
        discovery_status="verified",
        discovery_source="seed",
    )
    base.update(overrides)
    return Company(**base)


def test_build_map_returns_folium_map() -> None:
    fmap = build_map([_make_company()])
    assert isinstance(fmap, folium.Map)


def test_build_map_handles_empty_input() -> None:
    fmap = build_map([])
    assert isinstance(fmap, folium.Map)


def test_split_geocoded_partitions_correctly() -> None:
    a = _make_company(name="A", lat=-33.87, lon=151.21)
    b = _make_company(name="B", lat=None, lon=None)
    on_map, off_map = split_geocoded([a, b])
    assert on_map == [a]
    assert off_map == [b]


def test_popup_html_includes_name_and_link_and_summary() -> None:
    html = _popup_html(_make_company())
    assert "Test Co" in html
    assert 'href="https://example.com"' in html
    assert "A test company." in html
    assert "Foundation models" in html  # human label, not the raw tag
    assert "—" not in html  # PRD section 16: no em dashes in user-facing copy


def test_popup_html_includes_latest_funding_event() -> None:
    html = _popup_html(
        _make_company(
            latest_funding_event=FundingEvent(
                id="funding-1",
                announced_on=date(2026, 4, 21),
                stage="seed",
                amount_usd=Decimal("5000000"),
                currency_raw="USD 5M",
                lead_investor="Blackbird",
                investors=["Blackbird"],
                source_url="https://example.com/funding",
            )
        )
    )
    assert "Latest funding:" in html
    assert "Seed, 2026-04-21, US$5M" in html
    assert "—" not in html


def test_popup_html_includes_profile_amounts_and_headcount() -> None:
    html = _popup_html(
        _make_company(
            total_raised_usd=Decimal("25000000"),
            valuation_usd=Decimal("1000000000"),
            headcount_estimate=42,
        )
    )

    assert "Total raised:" in html
    assert "US$25M" in html
    assert "Valuation:" in html
    assert "US$1B" in html
    assert "Headcount:" in html
    assert "42" in html
    assert "—" not in html


def test_popup_html_handles_missing_optional_fields() -> None:
    bare = _make_company(
        website=None,
        stage=None,
        founded_year=None,
        summary=None,
        sector_tags=[],
    )
    html = _popup_html(bare)
    assert "Test Co" in html
    assert "href=" not in html  # no link without website
    assert "Stage:" not in html
    assert "Founded:" not in html


def test_build_map_skips_companies_without_coords() -> None:
    """The map can't render markers without lat/lon; should silently skip them."""
    companies = [
        _make_company(name="Has Coords"),
        _make_company(name="No Coords", lat=None, lon=None),
    ]
    fmap = build_map(companies)
    # Round-trip via folium html and count markers via the tooltip text.
    html = fmap.get_root().render()
    assert "Has Coords" in html
    assert "No Coords" not in html


def test_yaml_source_companies_can_render_to_map() -> None:
    """Smoke check: every YAML company with coords builds without error."""
    source = YamlSource()
    companies = source.list_companies()
    on_map, _ = split_geocoded(companies)
    fmap = build_map(on_map)
    assert isinstance(fmap, folium.Map)
    # Sanity: at least some sample markers are present in the HTML.
    html = fmap.get_root().render()
    assert "Marqo" in html or "Canva" in html


class _FakeExpander:
    def __enter__(self) -> _FakeExpander:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class _FakeSidebar:
    def __init__(self) -> None:
        self.expanders: list[tuple[str, bool]] = []

    def expander(self, label: str, *, expanded: bool) -> _FakeExpander:
        self.expanders.append((label, expanded))
        return _FakeExpander()


class _FakeStreamlit:
    def __init__(self) -> None:
        self.sidebar = _FakeSidebar()
        self.captions: list[str] = []
        self.markdowns: list[str] = []

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def markdown(self, text: str, *, unsafe_allow_html: bool) -> None:
        assert unsafe_allow_html is True
        self.markdowns.append(text)


def test_sector_colour_legend_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(sector_legend, "st", fake_st)

    sector_legend.render_sector_legend()

    rows = sector_legend_rows()
    assert fake_st.sidebar.expanders == [("Sector colours", True)]
    assert fake_st.captions == ["Marker colour uses the first sector listed for each company."]
    assert len(fake_st.markdowns) == len(rows)
    assert rows[0].label in fake_st.markdowns[0]
    assert rows[0].colour in fake_st.markdowns[0]
