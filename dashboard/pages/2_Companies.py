"""Companies page  -  filterable list view of every verified company."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.storage.data_source import Company  # noqa: E402
from dashboard.components.data_loaders import get_source, load_companies  # noqa: E402
from dashboard.components.filters import (  # noqa: E402
    apply_filters,
    companies_to_table_rows,
    derive_meta,
    render_sidebar,
)
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

render_page_chrome(title="AI Sector Watch: Companies", page_icon="🏢")


def _render_company_detail(company: Company) -> None:
    """Render a single company's detail card."""
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
        if meta_bits:
            st.write(" | ".join(meta_bits))
        if company.sector_tags:
            st.write("**Sectors:** " + ", ".join(company.sector_tags))
        profile_bits = []
        if company.founders:
            profile_bits.append(("Founders", ", ".join(company.founders)))
        total_raised = _format_usd(company.total_raised_usd)
        if total_raised:
            profile_bits.append(("Total raised", total_raised))
        valuation = _format_usd(company.valuation_usd)
        if valuation:
            profile_bits.append(("Valuation", valuation))
        headcount = _format_headcount(company)
        if headcount:
            profile_bits.append(("Headcount", headcount))
        if company.profile_verified_at:
            profile_bits.append(
                ("Profile verified", company.profile_verified_at.date().isoformat())
            )
        for label, value in profile_bits:
            st.write(f"**{label}:** {value}")
        if company.summary:
            st.write(company.summary)


def main() -> None:
    title_cols = st.columns([5, 1])
    with title_cols[0]:
        st.title("Companies")
        st.caption("Every verified company in the index, filterable from the sidebar.")
    with title_cols[1], st.popover("How to use this directory", use_container_width=True):
        st.markdown(
            "**The table** lists every verified ANZ AI company with the data "
            "the pipeline has gathered. Sortable by any column.\n\n"
            "**Pick a company** from the dropdown below the table to see "
            "the full profile: founders, total raised, valuation, "
            "headcount, and summary.\n\n"
            "**Sidebar filters** narrow what is shown. Use Reset to clear them."
        )

    source = get_source()
    all_companies = load_companies()

    if source.backend == "yaml":
        st.info(
            "Showing seed data from `data/seed/companies.yaml`. Set `SUPABASE_DB_URL` "
            "to read from the live index."
        )

    meta = derive_meta(all_companies)
    state = render_sidebar(meta, default_countries=("AU", "NZ"), key_prefix="company_filters")
    companies = apply_filters(all_companies, state)

    cols = st.columns(2)
    cols[0].metric("In view", len(companies))
    cols[1].metric("Total tracked", len(all_companies))

    rows = companies_to_table_rows(companies)
    if not rows:
        st.info("No companies match these filters. Clear one in the sidebar to widen the view.")
        render_footer()
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Country": st.column_config.TextColumn("Country", width="small"),
            "City": st.column_config.TextColumn("City", width="small"),
            "Stage": st.column_config.TextColumn("Stage", width="small"),
            "Founded": st.column_config.NumberColumn("Founded", width="small", format="%d"),
            "Sectors": st.column_config.TextColumn("Sectors", width="large"),
            "Website": st.column_config.LinkColumn(
                "Website", width="medium", display_text=r"https?://([^/]+).*"
            ),
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
        _render_company_detail(company)

    render_footer()


def _format_usd(amount: Decimal | None) -> str:
    """Return a compact USD amount for details."""
    if amount is None:
        return ""
    if amount >= Decimal("1000000000"):
        billions = amount / Decimal("1000000000")
        value = f"{billions:.1f}".rstrip("0").rstrip(".")
        return f"US${value}B"
    if amount >= Decimal("1000000"):
        millions = amount / Decimal("1000000")
        value = f"{millions:.1f}".rstrip("0").rstrip(".")
        return f"US${value}M"
    if amount >= Decimal("1000"):
        thousands = amount / Decimal("1000")
        value = f"{thousands:.1f}".rstrip("0").rstrip(".")
        return f"US${value}K"
    return f"US${amount:,.0f}"


def _format_headcount(company) -> str:
    """Return a compact headcount string."""
    if company.headcount_estimate is not None:
        return str(company.headcount_estimate)
    if company.headcount_min is not None and company.headcount_max is not None:
        return f"{company.headcount_min}-{company.headcount_max}"
    if company.headcount_min is not None:
        return f"{company.headcount_min}+"
    if company.headcount_max is not None:
        return f"up to {company.headcount_max}"
    return ""


main()
