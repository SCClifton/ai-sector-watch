"""Cached read accessors for the dashboard.

`@st.cache_resource` keeps a single ``DataSource`` per Streamlit process so
the Supabase connection pool is reused across reruns. ``@st.cache_data``
memoises read results so navigating between pages and tweaking filters does
not re-run identical SQL within the TTL window.

Mutation paths (admin Promote / Reject) must call ``load_companies.clear()``
after writing so the public dashboard reflects the change on next render.
"""

from __future__ import annotations

import streamlit as st

from ai_sector_watch.storage.data_source import (
    Company,
    DataSource,
    NewsItem,
    get_data_source,
)

_DEFAULT_TTL_SECONDS = 600


@st.cache_resource(show_spinner=False)
def get_source() -> DataSource:
    """Return the process-singleton data source backend."""
    return get_data_source()


@st.cache_data(ttl=_DEFAULT_TTL_SECONDS, show_spinner=False)
def load_companies(statuses: tuple[str, ...] = ("verified",)) -> list[Company]:
    """Return companies for the given statuses, cached for ``_DEFAULT_TTL_SECONDS``."""
    return get_source().list_companies(statuses=statuses)


@st.cache_data(ttl=_DEFAULT_TTL_SECONDS, show_spinner=False)
def load_news(limit: int = 100) -> list[NewsItem]:
    """Return the most recent news items, cached for ``_DEFAULT_TTL_SECONDS``."""
    return get_source().recent_news(limit=limit)
