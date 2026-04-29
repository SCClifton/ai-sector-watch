"""About page for methodology, scope, and project provenance."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

ARCHITECTURE_PATH = REPO_ROOT / "dashboard" / "static" / "architecture.svg"
GITHUB_REPO_URL = "https://github.com/SCClifton/ai-sector-watch"
ISSUES_URL = f"{GITHUB_REPO_URL}/issues"


def _render_architecture() -> None:
    """Render the pipeline diagram, falling back to ASCII if the SVG is unavailable."""
    if ARCHITECTURE_PATH.exists():
        st.image(str(ARCHITECTURE_PATH), use_container_width=True)
        return

    st.code(
        """
                           GitHub Actions cron
                                   |
                                   v
public signals --> weekly_pipeline.py
                   1. review candidate activity
                   2. validate ANZ relevance
                   3. classify candidate records
                   4. send new records to review
                   5. publish verified records
                                   |
                                   v
                            Supabase Postgres
                                   |
                                  read
                                   v
                          public dashboard
        """,
        language="text",
    )


def main() -> None:
    """Render the public methodology page."""
    render_page_chrome(title="AI Sector Watch: About", page_icon="🌏")

    st.title("About")
    st.caption("Methodology, scope, data quality, and source code.")

    st.header("What this is")
    st.write(
        "AI Sector Watch is a public map of the Australian and New Zealand AI startup "
        "landscape. It combines a verified company index with a weekly review workflow "
        "for new activity."
    )

    st.header("What's tracked")
    tracked_cols = st.columns(3)
    tracked_cols[0].metric("Scope", "AU + NZ")
    tracked_cols[1].metric("Sectors", "21")
    tracked_cols[2].metric("Cadence", "Weekly")
    st.write(
        "The index tracks AI-native and AI-enabled companies across a fixed sector "
        "taxonomy. Candidate records are checked before they appear publicly."
    )

    st.header("How discovery works")
    st.write(
        "A scheduled pipeline reviews public signals, extracts candidate company mentions, "
        "validates ANZ relevance, classifies records against the sector taxonomy, and sends "
        "new candidates to a private review queue. The public dashboard reads only verified "
        "companies."
    )
    _render_architecture()

    st.header("Data quality and disclaimers")
    st.write(
        "The data is assembled from public information and reviewed before "
        "publication. It can still contain errors, omissions, stale links, or imperfect "
        "sector tags. For corrections, open an issue in the project tracker."
    )
    st.link_button("Report a correction", ISSUES_URL)

    st.header("Project")
    st.write(
        "AI Sector Watch is an independent open research and engineering project. The "
        "repository contains the public source code, schema, taxonomy, and public-safe "
        "operating notes."
    )
    link_cols = st.columns([1, 3])
    link_cols[0].link_button("GitHub repository", GITHUB_REPO_URL, type="primary")

    render_footer()


main()
