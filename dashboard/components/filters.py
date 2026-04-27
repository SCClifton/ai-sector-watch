"""Sidebar filter controls and the pure-Python filter function they drive."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import streamlit as st

from ai_sector_watch.discovery.taxonomy import SECTORS, STAGES, get_sector
from ai_sector_watch.storage.data_source import Company

_SECTOR_LABEL_BY_TAG = {s.tag: s.label for s in SECTORS}


@dataclass(frozen=True)
class FilterState:
    """Snapshot of every filter control's current value."""

    sectors: tuple[str, ...] = ()
    stages: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    founded_min: int | None = None
    founded_max: int | None = None
    name_query: str = ""

    @property
    def is_active(self) -> bool:
        return any(
            (
                self.sectors,
                self.stages,
                self.countries,
                self.founded_min is not None,
                self.founded_max is not None,
                self.name_query.strip(),
            )
        )


@dataclass(frozen=True)
class FilterMeta:
    """Bounds and option lists derived from the loaded company set."""

    countries: tuple[str, ...] = ()
    founded_min: int = 2000
    founded_max: int = field(default_factory=lambda: date.today().year)


def derive_meta(companies: list[Company]) -> FilterMeta:
    countries = sorted({c.country for c in companies if c.country})
    years = [c.founded_year for c in companies if c.founded_year]
    if years:
        return FilterMeta(
            countries=tuple(countries),
            founded_min=min(years),
            founded_max=max(years),
        )
    return FilterMeta(countries=tuple(countries))


def render_sidebar(meta: FilterMeta, *, default_countries: tuple[str, ...]) -> FilterState:
    """Render the filter widgets in the sidebar, return a FilterState."""
    with st.sidebar:
        st.header("Filters")

        sector_tags = [s.tag for s in SECTORS]
        sectors = st.multiselect(
            "Sector",
            options=sector_tags,
            default=[],
            format_func=lambda t: _SECTOR_LABEL_BY_TAG.get(t, t),
            help="Pick one or more sectors. Empty = all sectors.",
        )

        stages = st.multiselect(
            "Stage",
            options=list(STAGES),
            default=[],
            help="Empty = all stages.",
        )

        valid_defaults = [c for c in default_countries if c in meta.countries]
        countries = st.multiselect(
            "Country",
            options=list(meta.countries),
            default=valid_defaults,
            help="Default: ANZ. Clear to include everywhere.",
        )

        founded_min, founded_max = meta.founded_min, meta.founded_max
        if founded_min == founded_max:
            founded_min, founded_max = founded_min - 1, founded_max
        year_range = st.slider(
            "Founded year",
            min_value=int(founded_min),
            max_value=int(founded_max),
            value=(int(founded_min), int(founded_max)),
            step=1,
        )

        name_query = st.text_input("Search name", value="", placeholder="e.g. Marqo")

        st.caption(
            "Filters apply to the map and the table below it. " "Reset by clearing each control."
        )

    return FilterState(
        sectors=tuple(sectors),
        stages=tuple(stages),
        countries=tuple(countries),
        founded_min=year_range[0],
        founded_max=year_range[1],
        name_query=name_query,
    )


def apply_filters(companies: list[Company], state: FilterState) -> list[Company]:
    """Pure function: return the subset of `companies` matching `state`."""
    out = companies
    if state.sectors:
        wanted = set(state.sectors)
        out = [c for c in out if wanted.intersection(c.sector_tags)]
    if state.stages:
        wanted = set(state.stages)
        out = [c for c in out if c.stage in wanted]
    if state.countries:
        wanted = set(state.countries)
        out = [c for c in out if c.country in wanted]
    if state.founded_min is not None:
        out = [c for c in out if c.founded_year is None or c.founded_year >= state.founded_min]
    if state.founded_max is not None:
        out = [c for c in out if c.founded_year is None or c.founded_year <= state.founded_max]
    q = state.name_query.strip().lower()
    if q:
        out = [c for c in out if q in c.name.lower()]
    return out


def companies_to_table_rows(companies: list[Company]) -> list[dict]:
    """Convert Company list -> list of dicts ready for st.dataframe."""
    rows = []
    for c in companies:
        rows.append(
            {
                "Name": c.name,
                "Country": c.country or "",
                "City": c.city or "",
                "Stage": c.stage or "",
                "Founded": c.founded_year or "",
                "Sectors": ", ".join(
                    (get_sector(t).label if get_sector(t) else t) for t in c.sector_tags
                ),
                "Website": c.website or "",
            }
        )
    return rows
