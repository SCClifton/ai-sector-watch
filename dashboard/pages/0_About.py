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
LINKEDIN_URL = "https://www.linkedin.com/in/samclifton"


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
RSS / arXiv / HF papers --> weekly_pipeline.py
                              1. fetch every source
                              2. LLM extracts company mentions
                              3. validate + classify candidates
                              4. geocode against ANZ city table
                              5. upsert pending + news + digest
                                   |
                                   v
                            Supabase Postgres
                                   |
                                  read
                                   v
                          Streamlit on Azure App Service
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
        "landscape. It combines a verified company index with a weekly agent pipeline "
        "that scans public sources for new activity."
    )

    st.header("What's tracked")
    tracked_cols = st.columns(3)
    tracked_cols[0].metric("Scope", "AU + NZ")
    tracked_cols[1].metric("Sectors", "21")
    tracked_cols[2].metric("Cadence", "Weekly")
    st.write(
        "The index tracks AI-native and AI-enabled companies across the fixed taxonomy "
        "documented in the repository. Inputs include startup news, RSS feeds, arXiv, "
        "Hugging Face papers, and related public signals."
    )

    st.header("How discovery works")
    st.write(
        "A scheduled GitHub Actions job fetches each source, then an LLM extracts company "
        "mentions from every item. New ANZ candidates are validated, classified against "
        "the sector taxonomy, geocoded with a static city table, and written to Supabase "
        "as pending review. The public dashboard reads only verified companies."
    )
    _render_architecture()

    st.header("Data quality and disclaimers")
    st.write(
        "The data is auto-extracted from public sources and manually reviewed before "
        "publication. It can still contain errors, omissions, stale links, or imperfect "
        "sector tags. For corrections, open an issue in the project tracker."
    )
    st.link_button("Report a correction", ISSUES_URL)

    st.header("Built by")
    st.write(
        "Built by Sam Clifton as an open research and engineering project. The repository "
        "is the primary record: source code, workflow files, schema, taxonomy, and operating "
        "notes are all public."
    )
    link_cols = st.columns([1, 1, 3])
    link_cols[0].link_button("GitHub repository", GITHUB_REPO_URL, type="primary")
    link_cols[1].link_button("LinkedIn", LINKEDIN_URL)

    render_footer()


main()
