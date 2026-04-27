"""Page chrome helper: theme + CSS injection + meta tags + brand wordmark.

Every dashboard page calls :func:`render_page_chrome` at the top instead of
``st.set_page_config`` directly. That keeps theme tokens, CSS, favicon, OG
meta tags and the brand wordmark in one place.

See ``docs/design-system.md`` for the design tokens themselves.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_STATIC_DIR: Path = Path(__file__).resolve().parents[1] / "static"
_STYLES_PATH: Path = _STATIC_DIR / "styles.css"
_FAVICON_PATH: Path = _STATIC_DIR / "favicon.png"

_PUBLIC_SITE_URL: str = "https://aimap.cliftonfamily.co"
_OG_IMAGE_URL: str = f"{_PUBLIC_SITE_URL}/app/static/og-image.png"
_DESCRIPTION: str = (
    "Live ecosystem map of the Australian and New Zealand AI startup landscape, "
    "updated weekly by an automated agent pipeline."
)
_NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("pages/0_About.py", "About"),
    ("pages/1_Map.py", "Map"),
    ("pages/2_Companies.py", "Companies"),
    ("pages/3_News.py", "News"),
    ("pages/4_Digest.py", "Digest"),
    ("pages/90_Admin.py", "Admin"),
)


def _inject_styles() -> None:
    """Inject ``styles.css`` for the current page render."""
    if _STYLES_PATH.exists():
        css = _STYLES_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _inject_meta_tags(*, title: str) -> None:
    """Hoist OG and Twitter meta tags into the parent document head.

    Streamlit pages render in an iframe, so a plain ``st.markdown`` injection
    only reaches the body. Most social crawlers want them in ``<head>``. We
    hoist them via a tiny script in a zero-height components.html block.
    """
    tags: list[tuple[str, str, str]] = [
        ("name", "description", _DESCRIPTION),
        ("property", "og:type", "website"),
        ("property", "og:site_name", "AI Sector Watch"),
        ("property", "og:title", title),
        ("property", "og:description", _DESCRIPTION),
        ("property", "og:url", _PUBLIC_SITE_URL),
        ("property", "og:image", _OG_IMAGE_URL),
        ("property", "og:image:width", "1200"),
        ("property", "og:image:height", "630"),
        ("name", "twitter:card", "summary_large_image"),
        ("name", "twitter:title", title),
        ("name", "twitter:description", _DESCRIPTION),
        ("name", "twitter:image", _OG_IMAGE_URL),
    ]
    payload = json.dumps(tags)
    script = f"""
    <script>
    (function() {{
      try {{
        var head = window.parent.document.head;
        if (!head) return;
        var tags = {payload};
        tags.forEach(function(t) {{
          var attr = t[0], name = t[1], content = t[2];
          var sel = 'meta[' + attr + '="' + name + '"]';
          var el = head.querySelector(sel);
          if (!el) {{
            el = window.parent.document.createElement('meta');
            el.setAttribute(attr, name);
            head.appendChild(el);
          }}
          el.setAttribute('content', content);
        }});
      }} catch (e) {{ /* cross-origin or sandboxed; nothing to do */ }}
    }})();
    </script>
    """
    components.html(script, height=0)

    body_meta = "\n".join(
        f'<meta {attr}="{name}" content="{content}">' for attr, name, content in tags
    )
    st.markdown(body_meta, unsafe_allow_html=True)


def _render_wordmark() -> None:
    """Render the AI Sector Watch wordmark at the top of every page."""
    st.markdown(
        '<div class="aisw-wordmark">'
        '<span class="aisw-wordmark__title">AI <em>Sector</em> Watch</span>'
        '<span class="aisw-wordmark__tag">ANZ AI ecosystem</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_sidebar_nav() -> None:
    """Render the dashboard navigation in the intended order."""
    with st.sidebar:
        for page_path, label in _NAV_ITEMS:
            st.page_link(page_path, label=label)


def render_page_chrome(*, title: str, page_icon: str = "🌏") -> None:
    """Configure Streamlit page chrome for the current page.

    Call this once at the top of every dashboard entry point in place of
    ``st.set_page_config``. Sets the page config, injects the design-system
    CSS, hoists OG and Twitter meta tags, and renders the brand wordmark.

    Args:
        title: The browser tab title and OG title for this page.
        page_icon: Fallback emoji used when the favicon PNG is unavailable.
    """
    icon: str | Path = _FAVICON_PATH if _FAVICON_PATH.exists() else page_icon
    st.set_page_config(
        page_title=title,
        page_icon=str(icon) if isinstance(icon, Path) else icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()
    _inject_meta_tags(title=title)
    _render_sidebar_nav()
    _render_wordmark()
