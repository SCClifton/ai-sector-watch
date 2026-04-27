"""Digest page — weekly markdown digests written by the pipeline."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import get_config  # noqa: E402
from ai_sector_watch.storage.data_source import LlmSpendSummary, get_data_source  # noqa: E402
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

render_page_chrome(title="AI Sector Watch: Digest", page_icon="📝")


def _format_usd(value: Decimal) -> str:
    return f"${value:.2f}"


def _render_spend_metrics(summary: LlmSpendSummary | None) -> None:
    if summary is None:
        st.info("No spend recorded yet")
        return

    cols = st.columns(2)
    cols[0].metric("4-week spend", _format_usd(summary.total_usd))
    cols[1].metric("avg per run", _format_usd(summary.average_usd))


def main() -> None:
    st.title("Weekly digest")
    st.caption("Auto-generated summaries written by the weekly pipeline. Latest first.")

    source = get_data_source()
    _render_spend_metrics(source.llm_spend_summary())

    digest_dir = get_config().digest_output_dir
    digest_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(digest_dir.glob("*.md"), reverse=True)

    if not files:
        st.info(
            "No digests yet. The pipeline writes one each Monday morning "
            "(Sydney time): a short, sourced summary of the week's ANZ AI "
            "activity."
        )
        render_footer()
        return

    options = [f.stem for f in files]
    pick = st.selectbox("Digest", options=options, index=0)
    chosen = next(f for f in files if f.stem == pick)
    st.markdown(chosen.read_text(encoding="utf-8"))

    render_footer()


main()
