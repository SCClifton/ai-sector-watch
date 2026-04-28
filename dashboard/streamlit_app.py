"""Entry point for the AI Sector Watch Streamlit dashboard.

Run locally:
    op run --account my.1password.com --env-file=.env.local -- streamlit run dashboard/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import streamlit_shadcn_ui as ui
from streamlit_extras.stylable_container import stylable_container

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from dashboard.components.data_loaders import get_source, load_companies  # noqa: E402
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

render_page_chrome(title="AI Sector Watch", page_icon="🌏")

_INTRO_DISMISSED_KEY = "aisw_intro_dismissed"


def _render_intro_hint() -> None:
    """Render a one-time welcome banner the user can dismiss."""
    if st.session_state.get(_INTRO_DISMISSED_KEY):
        return
    with stylable_container(
        key="aisw_intro_hint",
        css_styles="""
        {
          background: rgba(244, 183, 64, 0.10);
          border: 1px solid rgba(244, 183, 64, 0.42);
          border-radius: 8px;
          padding: 14px 18px;
          margin-bottom: 1.25rem;
        }
        """,
    ):
        cols = st.columns([20, 1])
        with cols[0]:
            st.markdown(
                "**Welcome.** Use the sidebar to jump between pages, or pick a path "
                "below. Click any marker on the map for the full company profile, "
                "and use the filters in the sidebar to narrow by sector, stage, or city."
            )
        with cols[1]:
            if st.button("✕", key="aisw_intro_dismiss", help="Dismiss this hint"):
                st.session_state[_INTRO_DISMISSED_KEY] = True
                st.rerun()


def main() -> None:
    source = get_source()
    companies = load_companies()

    st.title("AI Sector Watch")
    st.write(
        "Live ecosystem map of the Australian and New Zealand AI startup landscape, "
        "updated weekly by an automated agent pipeline."
    )

    _render_intro_hint()

    if source.backend == "yaml":
        st.info("Reading from the local seed YAML. Set `SUPABASE_DB_URL` to switch to live data.")

    au_count = sum(1 for c in companies if c.country == "AU")
    nz_count = sum(1 for c in companies if c.country == "NZ")
    col1, col2, col3 = st.columns(3)
    with col1:
        ui.metric_card(
            title="Tracked companies",
            content=f"{len(companies):,}",
            description="Verified across the index",
            key="aisw_metric_tracked",
        )
    with col2:
        ui.metric_card(
            title="Australia",
            content=f"{au_count:,}",
            description="Sydney, Melbourne, Brisbane, and beyond",
            key="aisw_metric_au",
        )
    with col3:
        ui.metric_card(
            title="New Zealand",
            content=f"{nz_count:,}",
            description="Auckland, Wellington, Christchurch",
            key="aisw_metric_nz",
        )

    st.divider()

    st.subheader("Public index")
    st.write(
        "The public dashboard shows verified companies only. Auto-discovered candidates "
        "wait in the admin review queue before they appear on the map or company list."
    )
    action_cols = st.columns([1, 1, 1, 2])
    if action_cols[0].button(
        "Open the map",
        type="primary",
        use_container_width=True,
        icon=":material/map:",
    ):
        st.switch_page("pages/1_Map.py")
    if action_cols[1].button(
        "Browse companies",
        use_container_width=True,
        icon=":material/business:",
    ):
        st.switch_page("pages/2_Companies.py")
    if action_cols[2].button(
        "Read the news feed",
        use_container_width=True,
        icon=":material/article:",
    ):
        st.switch_page("pages/3_News.py")

    render_footer()


if __name__ == "__main__":
    main()
else:
    main()
