"""Static checks confirming the research brief still runs from weekly.yml."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_research_brief_is_folded_into_weekly_pipeline() -> None:
    workflow = (ROOT / ".github/workflows/weekly.yml").read_text()

    assert 'cron: "0 18 * * 0"' in workflow
    assert "run_research_brief.py" in workflow
    assert "TZ=Australia/Sydney date +%F" in workflow
    assert "--timezone Australia/Sydney" in workflow
    assert "--write-db" in workflow
    assert "--no-json" in workflow
    assert "--hours 168" in workflow


def test_research_workflow_file_is_removed() -> None:
    assert not (ROOT / ".github/workflows/research.yml").exists()
