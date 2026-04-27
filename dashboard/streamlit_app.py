"""Entry point for the AI Sector Watch Streamlit dashboard.

Run locally:
    op run --env-file=.env.local -- streamlit run dashboard/streamlit_app.py
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

st.set_page_config(
    page_title="AI Sector Watch",
    page_icon="🌏",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    source = get_data_source()
    companies = source.list_companies()

    st.title("AI Sector Watch")
    st.write(
        "Live ecosystem map of the Australian and New Zealand AI startup landscape, "
        "updated weekly by an automated agent pipeline."
    )

    if source.backend == "yaml":
        st.info(
            "Running against the local seed YAML (no SUPABASE_DB_URL set). "
            "Set up Supabase and re-run with `op run --env-file=.env.local -- "
            "streamlit run dashboard/streamlit_app.py` to see live data."
        )

    col1, col2, col3 = st.columns(3)
    col1.metric("Companies tracked", len(companies))
    col2.metric(
        "Australian companies",
        sum(1 for c in companies if c.country == "AU"),
    )
    col3.metric(
        "New Zealand companies",
        sum(1 for c in companies if c.country == "NZ"),
    )

    st.divider()

    st.subheader("How to use this dashboard")
    st.markdown(
        """
- **Map** — interactive folium map of ANZ AI companies with sector colour and click-through popups.
- **Companies** — filterable list of every verified company.
- **News** — chronological feed of relevant news items linked to companies.
- **Digest** — weekly markdown digests written by the pipeline.
- **Admin** — review queue for auto-discovered candidates (password-gated).

Use the sidebar to navigate.
        """
    )

    render_footer()


if __name__ == "__main__":
    main()
else:
    main()
