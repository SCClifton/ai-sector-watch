"""Footer component shown on every dashboard page."""

from __future__ import annotations

from datetime import date

import streamlit as st


def render_footer() -> None:
    today = date.today().isoformat()
    st.markdown(
        '<div class="aisw-footer">'
        f"AI Sector Watch is a research project. Data is assembled from public "
        f"information and may contain errors or omissions. Last updated: {today}."
        "</div>",
        unsafe_allow_html=True,
    )
