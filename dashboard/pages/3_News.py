"""News page — chronological feed of relevant news linked to companies."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from dashboard.components.data_loaders import (  # noqa: E402
    get_source,
    load_companies,
    load_news,
)
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

render_page_chrome(title="AI Sector Watch: News", page_icon="📰")


def main() -> None:
    st.title("News")
    st.caption(
        "Chronological feed of relevant funding, launches, hires, and "
        "partnerships from the past week's pipeline run."
    )

    source = get_source()
    news = load_news(limit=100)
    companies = {c.id: c for c in load_companies()}

    if source.backend == "yaml" or not news:
        st.info(
            "No news yet. The pipeline scans Australian and New Zealand AI "
            "coverage every Monday morning (Sydney time) and posts what it "
            "finds here."
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
