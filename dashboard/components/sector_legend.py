"""Sector colour legend for the dashboard map page."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st

from ai_sector_watch.discovery.taxonomy import SECTOR_GROUPS, SECTORS, hex_for_group


@dataclass(frozen=True)
class SectorLegendRow:
    """One colour group row in the map legend."""

    group: str
    label: str
    colour: str
    examples: tuple[str, ...]


def sector_legend_rows(*, max_examples: int = 3) -> tuple[SectorLegendRow, ...]:
    """Build legend rows from the canonical sector taxonomy."""
    rows: list[SectorLegendRow] = []
    for group in SECTOR_GROUPS:
        examples = tuple(s.label for s in SECTORS if s.group == group)[:max_examples]
        rows.append(
            SectorLegendRow(
                group=group,
                label=_group_label(group),
                colour=hex_for_group(group),
                examples=examples,
            )
        )
    return tuple(rows)


def render_sector_legend(*, expanded: bool = True) -> None:
    """Render the sector colour legend in the Streamlit sidebar."""
    with st.sidebar.expander("Sector colours", expanded=expanded):
        st.caption("Marker colour uses the first sector listed for each company.")
        for row in sector_legend_rows():
            st.markdown(_legend_row_html(row), unsafe_allow_html=True)


def _group_label(group: str) -> str:
    """Convert a taxonomy group key into compact display text."""
    return group.replace("_", " ").title()


def _legend_row_html(row: SectorLegendRow) -> str:
    """Render one HTML legend row."""
    examples = ", ".join(escape(example) for example in row.examples)
    return (
        '<div style="display:flex;gap:0.5rem;align-items:flex-start;margin:0.25rem 0;">'
        f'<span style="background:{escape(row.colour)};'
        "border:1px solid var(--aisw-border-strong);"
        "border-radius:50%;display:inline-block;flex:0 0 0.75rem;"
        'height:0.75rem;margin-top:0.25rem;width:0.75rem;"></span>'
        "<span>"
        f"<strong>{escape(row.label)}</strong><br>"
        '<span style="color:var(--aisw-text-muted);font-size:0.8125rem;">'
        f"{examples}</span>"
        "</span>"
        "</div>"
    )
