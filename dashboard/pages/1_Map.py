"""Map page — interactive folium map of ANZ AI companies + filters + table."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from dashboard.components.data_loaders import get_source, load_companies  # noqa: E402
from dashboard.components.filters import (  # noqa: E402
    apply_filters,
    companies_to_table_rows,
    derive_meta,
    render_sidebar,
)
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.map_view import build_map, split_geocoded  # noqa: E402
from dashboard.components.sector_legend import render_sector_legend  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

render_page_chrome(title="AI Sector Watch: Map", page_icon="🌏")


def main() -> None:
    st.title("Map")
    st.caption("Click a marker for company detail. Markers cluster at low zoom.")

    source = get_source()
    all_companies = load_companies()

    if source.backend == "yaml":
        st.info(
            "Showing seed data from `data/seed/companies.yaml`. Set `SUPABASE_DB_URL` "
            "to read from the live index."
        )

    meta = derive_meta(all_companies)
    state = render_sidebar(meta, default_countries=("AU", "NZ"), key_prefix="map_filters")
    render_sector_legend()
    companies = apply_filters(all_companies, state)
    on_map, off_map = split_geocoded(companies)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Companies on map", len(on_map))
    metric_cols[1].metric("Companies in view", len(companies))
    metric_cols[2].metric("Total tracked", len(all_companies))
    metric_cols[3].metric("Awaiting geocoding", len(off_map))

    fmap = build_map(on_map)
    st_folium(fmap, width=None, height=560, returned_objects=[])

    st.subheader("Companies in view")
    rows = companies_to_table_rows(companies)
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                "Website": st.column_config.LinkColumn("Website"),
            },
        )
    else:
        st.info("No companies match these filters. Clear one in the sidebar to widen the view.")

    if off_map:
        with st.expander(f"Companies without map coordinates ({len(off_map)})"):
            for c in off_map:
                st.write(f"- **{c.name}** in {c.city or 'unknown city'}, {c.country or '?'}")

    render_footer()


main()
