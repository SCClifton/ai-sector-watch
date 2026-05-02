"""Static checks for the research brief workflow."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_research_workflow_runs_tuesday_and_friday_with_scheduled_window() -> None:
    workflow = (ROOT / ".github/workflows/research.yml").read_text()

    assert 'cron: "0 0 * * 2,5"' in workflow
    assert "TZ=Australia/Sydney date +%F" in workflow
    assert "--scheduled-window" in workflow
    assert "--timezone Australia/Sydney" in workflow
    assert "--write-db" in workflow
    assert "--no-json" in workflow
