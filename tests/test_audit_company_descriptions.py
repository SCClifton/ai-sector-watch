"""Tests for the company description audit script."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import audit_company_descriptions as audit_descriptions  # noqa: E402

from ai_sector_watch.extraction.claude_client import BudgetExceeded  # noqa: E402
from ai_sector_watch.extraction.firecrawl_client import DEFAULT_CREDITS_PER_ENRICH  # noqa: E402


class FakeFirecrawlClient:
    """FirecrawlClient stand-in with only the fields the audit reads."""

    def __init__(self, **_kwargs) -> None:
        self.stats = SimpleNamespace(credits_used=0)


class FakeClaudeClient:
    """ClaudeClient stand-in with only the fields the audit reads."""

    def __init__(self, **_kwargs) -> None:
        self.stats = SimpleNamespace(calls=0, cost_usd=0.0)


def _company(**overrides):
    base = {
        "id": "company-1",
        "name": "Example AI",
        "website": "https://example.ai",
        "discovery_status": "verified",
        "summary": "Example AI builds computer vision tools for safety teams.",
        "sector_tags": ["vertical_industrial"],
    }
    base.update(overrides)
    return base


def _facts(**overrides):
    base = {
        "proposed_summary": (
            "Example AI builds computer vision software that helps safety teams detect "
            "workplace hazards from camera feeds."
        ),
        "is_ai_company": True,
        "is_anz_relevant": True,
        "confidence": 0.9,
        "evidence_urls": ["https://example.ai/about"],
        "evidence_notes": "About page describes the AI product and safety customers.",
    }
    base.update(overrides)
    return audit_descriptions.CompanyDescriptionFacts(**base)


def test_confirmed_summary_when_current_is_public_ready_and_similar() -> None:
    summary = (
        "Example AI builds computer vision software that helps safety teams detect "
        "workplace hazards from camera feeds."
    )

    finding, update = audit_descriptions.build_description_audit(
        _company(summary=summary),
        _facts(proposed_summary=summary),
        enriched=True,
    )

    assert finding.action == audit_descriptions.ACTION_CONFIRMED
    assert update is None


def test_missing_summary_proposes_supported_replacement() -> None:
    finding, update = audit_descriptions.build_description_audit(
        _company(summary=""),
        _facts(),
        enriched=True,
    )

    assert finding.action == audit_descriptions.ACTION_MISSING_SUMMARY
    assert update is not None
    assert update.updates["summary"] == finding.proposed_summary
    assert update.updates["profile_sources"] == ["https://example.ai/about"]
    assert update.updates["profile_confidence"] == 0.9


def test_em_dash_in_current_summary_forces_update() -> None:
    finding, update = audit_descriptions.build_description_audit(
        _company(summary="Example AI builds camera analytics — for safety teams."),
        _facts(),
        enriched=True,
    )

    assert finding.action == audit_descriptions.ACTION_NEEDS_UPDATE
    assert update is not None
    assert "—" not in update.updates["summary"]
    assert "–" not in update.updates["summary"]


def test_low_confidence_replacement_requires_manual_review() -> None:
    finding, update = audit_descriptions.build_description_audit(
        _company(summary="Example AI builds analytics."),
        _facts(confidence=0.4),
        enriched=True,
    )

    assert finding.action == audit_descriptions.ACTION_MANUAL_REVIEW
    assert update is None
    assert "below the replacement threshold" in finding.notes


def test_out_of_scope_signal_becomes_possible_rejection_without_update() -> None:
    finding, update = audit_descriptions.build_description_audit(
        _company(),
        _facts(is_ai_company=False, scope_concern="Sources describe a consulting firm."),
        enriched=True,
    )

    assert finding.action == audit_descriptions.ACTION_POSSIBLE_REJECTION
    assert update is None
    assert "consulting firm" in finding.notes


def test_no_evidence_for_proposed_summary_requires_manual_review() -> None:
    finding, update = audit_descriptions.build_description_audit(
        _company(),
        _facts(evidence_urls=[]),
        enriched=True,
    )

    assert finding.action == audit_descriptions.ACTION_MANUAL_REVIEW
    assert update is None
    assert "confident replacement" in finding.notes


def test_artifact_generation_shape(tmp_path: Path) -> None:
    company = _company(summary="")
    finding, update = audit_descriptions.build_description_audit(
        company,
        _facts(),
        enriched=True,
    )
    assert update is not None

    artifacts = audit_descriptions._write_artifacts(
        output_dir=tmp_path,
        run_date=audit_descriptions.date(2026, 5, 1),
        artifact_suffix="test",
        companies=[company],
        findings=[finding],
        proposed_updates=[update],
        dry_run=False,
        enrich=True,
        credits_used=DEFAULT_CREDITS_PER_ENRICH,
        llm_calls=1,
        llm_cost_usd=0.0123,
    )

    assert artifacts.csv_path.exists()
    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert payload["company_count"] == 1
    assert payload["companies"][0]["id"] == "company-1"
    assert payload["companies"][0]["updates"]["summary"] == finding.proposed_summary
    markdown = artifacts.markdown_path.read_text(encoding="utf-8")
    assert "Missing summary: 1" in markdown
    assert "High-Confidence Replacements" in markdown
    assert "Firecrawl credits used: 8" in markdown


def test_enriched_audit_fails_when_budget_exhaustion_truncates_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        audit_descriptions,
        "_load_companies",
        lambda *, limit, offset: [_company(name="Budget Target")],
    )
    monkeypatch.setattr(audit_descriptions, "FirecrawlClient", FakeFirecrawlClient)
    monkeypatch.setattr(audit_descriptions, "ClaudeClient", FakeClaudeClient)

    def fake_extract(client, llm_client, website: str, *, name: str, current_summary, sector_tags):
        raise BudgetExceeded("test budget exhausted")

    monkeypatch.setattr(audit_descriptions, "extract_description_facts", fake_extract)

    with pytest.raises(audit_descriptions.DescriptionAuditBudgetExceeded):
        audit_descriptions.run_audit(
            limit=1,
            offset=0,
            dry_run=False,
            enrich=True,
            output_dir=tmp_path,
            run_date=audit_descriptions.date(2026, 5, 1),
            artifact_suffix=None,
        )

    assert list(tmp_path.iterdir()) == []


def test_main_rejects_enrich_without_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        audit_descriptions,
        "run_audit",
        lambda **kwargs: pytest.fail("run_audit should not be called"),
    )

    assert audit_descriptions.main(["--enrich"]) == 2
