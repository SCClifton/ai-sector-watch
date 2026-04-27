"""Companies page — filterable list view of every verified company."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.storage.data_source import get_data_source  # noqa: E402
from dashboard.components.filters import (  # noqa: E402
    apply_filters,
    companies_to_table_rows,
    derive_meta,
    render_sidebar,
)
from dashboard.components.footer import render_footer  # noqa: E402

st.set_page_config(
    page_title="AI Sector Watch: Companies",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    st.title("Companies")
    st.caption("Every verified company in the index, filterable from the sidebar.")

    source = get_data_source()
    all_companies = source.list_companies()

    if source.backend == "yaml":
        st.info(
            "Showing seed data from data/seed/companies.yaml (no SUPABASE_DB_URL set)."
        )

    meta = derive_meta(all_companies)
    state = render_sidebar(meta, default_countries=("AU", "NZ"))
    companies = apply_filters(all_companies, state)

    cols = st.columns(2)
    cols[0].metric("In view", len(companies))
    cols[1].metric("Total tracked", len(all_companies))

    rows = companies_to_table_rows(companies)
    if not rows:
        st.write("No companies match the current filters.")
        render_footer()
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Website": st.column_config.LinkColumn("Website"),
        },
    )

    st.subheader("Detail view")
    options = [c.name for c in companies]
    selected_name = st.selectbox(
        "Pick a company",
        options=options,
        index=0 if options else None,
    )
    if selected_name:
        company = next(c for c in companies if c.name == selected_name)
        with st.container(border=True):
            header = company.name
            if company.website:
                header = f"[{company.name}]({company.website})"
            st.markdown(f"### {header}")
            st.caption(f"{company.city or 'unknown city'}, {company.country or '?'}")
            meta_bits = []
            if company.stage:
                meta_bits.append(f"**Stage:** {company.stage}")
            if company.founded_year:
                meta_bits.append(f"**Founded:** {company.founded_year}")
            if company.discovery_source:
                meta_bits.append(f"**Source:** {company.discovery_source}")
            if meta_bits:
                st.write(" | ".join(meta_bits))
            if company.sector_tags:
                st.write("**Sectors:** " + ", ".join(company.sector_tags))
            if company.summary:
                st.write(company.summary)

    render_footer()


main()
