"""Footer component shown on every dashboard page."""

from __future__ import annotations

from datetime import date

import streamlit as st


def render_footer() -> None:
    today = date.today().isoformat()
    st.caption(
        f"AI Sector Watch is a research project. Data is auto-extracted from "
        f"public sources by an automated pipeline and may contain errors or "
        f"omissions. Last updated: {today}. Built by Sam Clifton."
    )
