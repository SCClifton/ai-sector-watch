"""Static checks for the Research page wiring.

The web package has lint and build checks but no JS test runner. These tests
cover repo-level wiring that can regress silently.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_header_nav_includes_research_between_news_and_about() -> None:
    source = (ROOT / "web/src/components/Header.tsx").read_text()
    news_index = source.index('{ href: "/news", label: "News" }')
    research_index = source.index('{ href: "/research", label: "Research" }')
    about_index = source.index('{ href: "/about", label: "About" }')

    assert news_index < research_index < about_index


def test_research_page_has_empty_state_and_api_route() -> None:
    component = (ROOT / "web/src/components/research/ResearchContent.tsx").read_text()
    route = (ROOT / "web/src/app/api/research/route.ts").read_text()

    assert "No research runs yet" in component
    assert "Daily research briefs will appear here" in component
    assert "/api/research?limit=30" in component
    assert "listResearchRuns" in route
