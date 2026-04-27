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

from ai_sector_watch.storage.data_source import get_data_source  # noqa: E402
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

render_page_chrome(title="AI Sector Watch", page_icon="🌏")


def main() -> None:
    source = get_data_source()
    companies = source.list_companies()

    st.title("AI Sector Watch")
    st.write(
        "Live ecosystem map of the Australian and New Zealand AI startup landscape, "
        "updated weekly by an automated agent pipeline."
    )

    if source.backend == "yaml":
        st.info("Reading from the local seed YAML. Set `SUPABASE_DB_URL` to switch to live data.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Tracked", len(companies))
    col2.metric(
        "Australia",
        sum(1 for c in companies if c.country == "AU"),
    )
    col3.metric(
        "New Zealand",
        sum(1 for c in companies if c.country == "NZ"),
    )

    st.divider()

    st.subheader("Public index")
    st.write(
        "The public dashboard shows verified companies only. Auto-discovered candidates "
        "wait in the admin review queue before they appear on the map or company list."
    )
    action_cols = st.columns([1, 1, 1, 2])
    action_cols[0].link_button("Map", "/Map", type="primary")
    action_cols[1].link_button("Companies", "/Companies")
    action_cols[2].link_button("News", "/News")

    render_footer()


if __name__ == "__main__":
    main()
else:
    main()
