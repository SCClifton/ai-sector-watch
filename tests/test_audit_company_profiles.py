"""Tests for the company profile audit script."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import audit_company_profiles as audit_profiles  # noqa: E402

from ai_sector_watch.extraction.claude_client import BudgetExceeded  # noqa: E402


class FakeFirecrawlClient:
    """FirecrawlClient stand-in with only the fields the audit reads."""

    def __init__(self) -> None:
        self.stats = SimpleNamespace(credits_used=0)


class FakeClaudeClient:
    """ClaudeClient stand-in with only the fields the audit reads."""

    def __init__(self) -> None:
        self.stats = SimpleNamespace(calls=0)


def test_enriched_audit_fails_when_budget_exhaustion_truncates_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Budget exhaustion should not produce successful partial audit artifacts."""
    monkeypatch.setattr(
        audit_profiles,
        "_load_companies",
        lambda *, statuses, limit, offset: [
            {
                "id": "company-1",
                "name": "Budget Target",
                "website": "https://budget.example",
                "discovery_status": "verified",
                "sector_tags": [],
            }
        ],
    )
    monkeypatch.setattr(audit_profiles, "FirecrawlClient", FakeFirecrawlClient)
    monkeypatch.setattr(audit_profiles, "ClaudeClient", FakeClaudeClient)

    def fake_enrich(client, llm_client, website: str, *, name: str):
        raise BudgetExceeded("test budget exhausted")

    monkeypatch.setattr(audit_profiles, "firecrawl_enrich", fake_enrich)

    with pytest.raises(audit_profiles.AuditBudgetExceeded):
        audit_profiles.run_audit(
            limit=1,
            offset=0,
            dry_run=False,
            enrich=True,
            output_dir=tmp_path,
            run_date=audit_profiles.date(2026, 4, 28),
            artifact_suffix=None,
        )

    assert list(tmp_path.iterdir()) == []


def test_main_returns_nonzero_when_budget_exhaustion_truncates_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The CLI should fail cleanly when an enriched audit is incomplete."""
    monkeypatch.setattr(
        audit_profiles,
        "run_audit",
        lambda **kwargs: (_ for _ in ()).throw(audit_profiles.AuditBudgetExceeded("truncated")),
    )

    status = audit_profiles.main(
        [
            "--enrich",
            "--limit",
            "1",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert status == 1
