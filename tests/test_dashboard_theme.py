"""Tests for dashboard chrome helpers and deployment packaging."""

from __future__ import annotations

from pathlib import Path

from dashboard.components import theme
from dashboard.components.theme import _active_nav_label, _nav_items_with_active

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_active_nav_label_maps_page_titles() -> None:
    assert _active_nav_label("AI Sector Watch") == "Overview"
    assert _active_nav_label("AI Sector Watch: Map") == "Map"
    assert _active_nav_label("AI Sector Watch: Companies") == "Companies"


def test_sidebar_nav_marks_one_current_page() -> None:
    items = _nav_items_with_active(active_label="Map")

    assert sum(1 for _, _, is_active in items if is_active) == 1
    assert ("streamlit_app.py", "Overview", False) in items
    assert ("pages/1_Map.py", "Map", True) in items


def test_sidebar_nav_uses_streamlit_page_links(monkeypatch) -> None:
    calls: list[tuple[str, str, bool, bool]] = []
    markdown_calls: list[str] = []

    class Sidebar:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

    def page_link(page: str, *, label: str, disabled: bool, use_container_width: bool) -> None:
        calls.append((page, label, disabled, use_container_width))

    monkeypatch.setattr(theme.st, "sidebar", Sidebar())
    monkeypatch.setattr(
        theme.st, "markdown", lambda body, *args, **kwargs: markdown_calls.append(body)
    )
    monkeypatch.setattr(theme.st, "page_link", page_link)

    theme._render_sidebar_nav(title="AI Sector Watch: Map")

    assert calls[0] == ("streamlit_app.py", "Overview", False, True)
    assert ("pages/1_Map.py", "Map", True, True) in calls
    assert ("pages/90_Admin.py", "Admin", False, True) in calls
    assert any("Operations" in body for body in markdown_calls)
    assert all(not page.startswith("/") for page, _, _, _ in calls)


def test_sidebar_nav_separates_admin_from_public_pages() -> None:
    items = _nav_items_with_active(active_label="Admin")

    assert ("pages/90_Admin.py", "Admin", True) in items
    assert sum(1 for _, _, is_active in items if is_active) == 1


def test_docker_image_builds_next_js_standalone() -> None:
    """After Phase 3 (#68) the deployed container is the Next.js app under web/."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    deploy = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")

    # Multi-stage build copies only web/ into the container.
    assert "FROM node:20-slim" in dockerfile
    assert "COPY web/" in dockerfile
    assert 'CMD ["node", "server.js"]' in dockerfile
    # Workflow triggers on web/, not on the old Streamlit-era paths.
    assert '"web/**"' in deploy
    assert '".streamlit/**"' not in deploy


def test_docker_image_listens_on_websites_port() -> None:
    """The container PORT must match the App Service WEBSITES_PORT (#74)."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    # Azure App Service routes traffic to WEBSITES_PORT, which is currently
    # 8000 from the Streamlit era. Next.js standalone reads PORT and listens
    # on it. The two must agree or the reverse proxy times out.
    assert "PORT=8000" in dockerfile
    assert "EXPOSE 8000" in dockerfile
