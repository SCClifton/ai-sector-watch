"""Entry point for the AI Sector Watch Streamlit dashboard.

Run locally:
    op run --account my.1password.com --env-file=.env.local -- streamlit run dashboard/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from dashboard.components.data_loaders import get_source, load_companies  # noqa: E402
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

render_page_chrome(title="AI Sector Watch", page_icon="🌏")

_INTRO_DISMISSED_KEY = "aisw_intro_dismissed"


def _render_intro_hint() -> None:
    """Render a one-time welcome banner the user can dismiss.

    Uses ``st.container(key=...)`` so the styling lives in
    ``dashboard/static/styles.css`` against the matching ``.st-key-`` selector.
    """
    if st.session_state.get(_INTRO_DISMISSED_KEY):
        return
    with st.container(key="aisw_intro_hint"):
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
    col1.metric("Tracked companies", f"{len(companies):,}")
    col2.metric("Australia", f"{au_count:,}")
    col3.metric("New Zealand", f"{nz_count:,}")

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
