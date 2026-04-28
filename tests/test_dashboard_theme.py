"""Tests for dashboard chrome helpers and deployment packaging."""

from __future__ import annotations

from pathlib import Path

from dashboard.components.theme import _active_nav_label, _sidebar_nav_html

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_active_nav_label_maps_page_titles() -> None:
    assert _active_nav_label("AI Sector Watch") == "Overview"
    assert _active_nav_label("AI Sector Watch: Map") == "Map"
    assert _active_nav_label("AI Sector Watch: Companies") == "Companies"


def test_sidebar_nav_marks_one_current_page() -> None:
    html = _sidebar_nav_html(active_label="Map")

    assert html.count('aria-current="page"') == 1
    assert 'href="/"' in html
    assert 'href="/Map"' in html
    assert "aisw-sidebar-nav__link--active" in html


def test_sidebar_nav_separates_admin_from_public_pages() -> None:
    html = _sidebar_nav_html(active_label="Admin")

    assert "Operations" in html
    assert 'href="/Admin"' in html
    assert "aisw-sidebar-nav__link--operations" in html
    assert html.count('aria-current="page"') == 1


def test_docker_image_includes_streamlit_config() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    deploy = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")

    assert "COPY .streamlit ./.streamlit" in dockerfile
    assert '".streamlit/**"' in deploy
