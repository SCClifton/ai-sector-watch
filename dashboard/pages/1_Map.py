"""Map page — interactive folium map of ANZ AI companies."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.storage.data_source import get_data_source  # noqa: E402
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.map_view import build_map, split_geocoded  # noqa: E402

st.set_page_config(
    page_title="AI Sector Watch — Map",
    page_icon="🌏",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    st.title("Map")
    st.caption("Click a marker for company detail. Markers cluster at low zoom.")

    source = get_data_source()
    companies = source.list_companies()
    on_map, off_map = split_geocoded(companies)

    if source.backend == "yaml":
        st.info(
            "Showing seed data from data/seed/companies.yaml (no SUPABASE_DB_URL). "
            "Live data appears once the pipeline runs."
        )

    metric_cols = st.columns(3)
    metric_cols[0].metric("Companies on map", len(on_map))
    metric_cols[1].metric("Companies tracked", len(companies))
    metric_cols[2].metric("Awaiting geocoding", len(off_map))

    fmap = build_map(on_map)
    st_folium(fmap, width=None, height=620, returned_objects=[])

    if off_map:
        with st.expander(f"Companies without map coordinates ({len(off_map)})"):
            for c in off_map:
                st.write(f"- **{c.name}** — {c.city or 'unknown city'}, {c.country or '?'}")

    render_footer()


main()
