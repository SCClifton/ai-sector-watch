"""News page — chronological feed of relevant news linked to companies."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.storage.data_source import get_data_source  # noqa: E402
from dashboard.components.footer import render_footer  # noqa: E402

st.set_page_config(
    page_title="AI Sector Watch: News",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    st.title("News")
    st.caption(
        "Chronological feed of relevant funding, launches, hires, and "
        "partnerships from the past week's pipeline run."
    )

    source = get_data_source()
    news = source.recent_news(limit=100)
    companies = {c.id: c for c in source.list_companies()}

    if source.backend == "yaml" or not news:
        st.info(
            "No news yet. The weekly pipeline will populate this page once it runs. "
            "Run manually with: `op run --env-file=.env.local -- python "
            "scripts/run_weekly_pipeline.py`"
        )
        render_footer()
        return

    for item in news:
        with st.container(border=True):
            header = f"### [{item.title}]({item.source_url})"
            st.markdown(header)
            sub_bits = [item.kind]
            if item.published_at:
                sub_bits.append(item.published_at.date().isoformat())
            sub_bits.append(item.source_slug)
            st.caption(" | ".join(sub_bits))
            if item.summary:
                st.write(item.summary)
            mentioned = [companies[cid].name for cid in item.company_ids if cid in companies]
            if mentioned:
                st.write("**Mentions:** " + ", ".join(mentioned))

    render_footer()


main()
