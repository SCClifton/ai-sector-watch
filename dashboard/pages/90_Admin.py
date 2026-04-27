"""Admin review queue.

Gated by ADMIN_PASSWORD env var. Read-only for visitors; only admins can
promote `auto_discovered_pending_review` rows to `verified` or mark them
`rejected`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import get_config  # noqa: E402
from ai_sector_watch.storage import supabase_db  # noqa: E402
from dashboard.components.footer import render_footer  # noqa: E402
from dashboard.components.theme import render_page_chrome  # noqa: E402

render_page_chrome(title="AI Sector Watch: Admin", page_icon="🔒")

SESSION_KEY = "admin_authed"


def _check_password() -> bool:
    """Render a password gate and return True iff the user is authed."""
    if st.session_state.get(SESSION_KEY):
        return True
    cfg = get_config()
    expected = cfg.admin_password
    if not expected:
        st.error("`ADMIN_PASSWORD` is not set. Sign-in is disabled.")
        return False
    with st.form("admin_login"):
        attempt = st.text_input("Admin password", type="password")
        ok = st.form_submit_button("Sign in")
    if ok:
        if attempt == expected:
            st.session_state[SESSION_KEY] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False


def main() -> None:
    st.title("Admin: review queue")
    st.caption(
        "Auto-discovered candidates wait here for verification before they "
        "appear on the public map."
    )

    if not _check_password():
        return

    if not get_config().supabase_db_url:
        st.warning(
            "`SUPABASE_DB_URL` is not set. The review queue stays empty until the "
            "pipeline writes to Supabase."
        )
        render_footer()
        return

    with supabase_db.connection() as conn:
        pending = supabase_db.list_companies(
            conn,
            statuses=("auto_discovered_pending_review",),
        )
        rejected = supabase_db.list_companies(conn, statuses=("rejected",))

    st.metric("Awaiting review", len(pending))
    st.write(f"Previously rejected: {len(rejected)}")

    if not pending:
        st.success(
            "Review queue is clear. Auto-discovered candidates land here after "
            "each pipeline run."
        )
        render_footer()
        return

    df = pd.DataFrame(
        [
            {
                "Name": c["name"],
                "Country": c.get("country") or "",
                "City": c.get("city") or "",
                "Stage": c.get("stage") or "",
                "Sectors": ", ".join(c.get("sector_tags") or []),
                "Source": c.get("discovery_source") or "",
                "Summary": c.get("summary") or "",
            }
            for c in pending
        ]
    )
    st.dataframe(df, hide_index=True, width="stretch")

    st.subheader("Decide")
    options = [c["name"] for c in pending]
    pick = st.selectbox("Pick a candidate", options=options)
    chosen = next(c for c in pending if c["name"] == pick)

    with st.container(border=True):
        st.markdown(f"### {chosen['name']}")
        st.caption(f"{chosen.get('city') or '?'}, {chosen.get('country') or '?'}")
        if chosen.get("summary"):
            st.write(chosen["summary"])
        if chosen.get("sector_tags"):
            st.write("**Sectors:** " + ", ".join(chosen["sector_tags"]))

        col1, col2 = st.columns(2)
        if col1.button("Promote to verified", type="primary"):
            with supabase_db.connection() as conn:
                supabase_db.set_company_status(conn, str(chosen["id"]), "verified")
                conn.commit()
            st.success(f"{chosen['name']} is now verified and will appear on the map.")
            st.rerun()
        if col2.button("Reject"):
            with supabase_db.connection() as conn:
                supabase_db.set_company_status(conn, str(chosen["id"]), "rejected")
                conn.commit()
            st.success(f"{chosen['name']} marked as rejected.")
            st.rerun()

    render_footer()


main()
