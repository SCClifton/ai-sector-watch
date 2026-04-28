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
    title_cols = st.columns([5, 1])
    with title_cols[0]:
        st.title("News")
        st.caption(
            "Chronological feed of relevant funding, launches, hires, and "
            "partnerships from the past week's pipeline run."
        )
    with title_cols[1], st.popover("Where do these come from", use_container_width=True):
        st.markdown(
            "Items are auto-extracted from a curated set of ANZ AI sources "
            "every Monday morning (Sydney time), then linked to the "
            "companies they mention.\n\n"
            "**Headlines** open the original story in a new tab. "
            "**Mentions** lists the companies the pipeline matched against "
            "the index. The full source list lives in `docs/sources.md`."
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
