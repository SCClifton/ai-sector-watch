"""Digest page — weekly markdown digests written by the pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import get_config  # noqa: E402
from dashboard.components.footer import render_footer  # noqa: E402

st.set_page_config(
    page_title="AI Sector Watch: Digest",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    st.title("Weekly digest")
    st.caption("Auto-generated summaries written by the weekly pipeline. " "Latest first.")

    digest_dir = get_config().digest_output_dir
    digest_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(digest_dir.glob("*.md"), reverse=True)

    if not files:
        st.info(
            "No digests yet. The weekly pipeline will write one each Monday morning "
            "(Sydney time). Trigger one manually with `op run --account my.1password.com --env-file=.env.local "
            "-- python scripts/run_weekly_pipeline.py`."
        )
        render_footer()
        return

    options = [f.stem for f in files]
    pick = st.selectbox("Digest", options=options, index=0)
    chosen = next(f for f in files if f.stem == pick)
    st.markdown(chosen.read_text(encoding="utf-8"))

    render_footer()


main()
