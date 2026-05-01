"""Tests for the company location audit script."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import audit_company_locations as audit_locations  # noqa: E402

from ai_sector_watch.extraction.claude_client import BudgetExceeded  # noqa: E402
from ai_sector_watch.extraction.firecrawl_client import DEFAULT_CREDITS_PER_ENRICH  # noqa: E402


class FakeFirecrawlClient:
    """FirecrawlClient stand-in with only the fields the audit reads."""

    def __init__(self) -> None:
        self.stats = SimpleNamespace(credits_used=0)


class FakeClaudeClient:
    """ClaudeClient stand-in with only the fields the audit reads."""

    def __init__(self) -> None:
        self.stats = SimpleNamespace(calls=0)


def _company(**overrides):
    base = {
        "id": "company-1",
        "name": "Example AI",
        "website": "https://example.ai",
        "discovery_status": "verified",
        "city": "Sydney",
        "country": "AU",
        "lat": None,
        "lon": None,
    }
    geo = audit_locations.geocode_city("Sydney", jitter_seed="Example AI")
    assert geo is not None
    base["lat"] = geo.lat
    base["lon"] = geo.lon
    base.update(overrides)
    return base


def _facts(**overrides):
    base = {
        "hq_city": "Sydney",
        "hq_country": "AU",
        "confidence": 0.9,
        "evidence_urls": ["https://example.ai/about"],
        "evidence_notes": "About page lists Sydney headquarters.",
    }
    base.update(overrides)
    return audit_locations.CompanyLocationFacts(**base)


def test_confirmed_location_when_city_country_and_coords_match() -> None:
    finding, update = audit_locations.build_location_audit(
        _company(),
        _facts(),
        enriched=True,
    )

    assert finding.action == audit_locations.ACTION_CONFIRMED
    assert update is None


def test_high_confidence_city_mismatch_proposes_geocoded_update() -> None:
    finding, update = audit_locations.build_location_audit(
        _company(city="Melbourne"),
        _facts(hq_city="Sydney"),
        enriched=True,
    )

    assert finding.action == audit_locations.ACTION_NEEDS_UPDATE
    assert update is not None
    assert update.updates["city"] == "Sydney"
    assert update.updates["country"] == "AU"
    assert (
        update.updates["lat"]
        == audit_locations.geocode_city("Sydney", jitter_seed="Example AI").lat
    )
    assert update.updates["profile_sources"] == ["https://example.ai/about"]


def test_high_confidence_country_mismatch_proposes_update() -> None:
    finding, update = audit_locations.build_location_audit(
        _company(country="NZ"),
        _facts(hq_country="AU"),
        enriched=True,
    )

    assert finding.action == audit_locations.ACTION_NEEDS_UPDATE
    assert update is not None
    assert update.updates["country"] == "AU"


def test_missing_current_location_proposes_update_when_supported() -> None:
    finding, update = audit_locations.build_location_audit(
        _company(city="", country="", lat=None, lon=None),
        _facts(hq_city="Melbourne", hq_country="AU"),
        enriched=True,
    )

    assert finding.action == audit_locations.ACTION_MISSING_LOCATION
    assert update is not None
    assert update.updates["city"] == "Melbourne"
    assert update.updates["lat"] is not None
    assert update.updates["lon"] is not None


def test_unsupported_extracted_city_requires_review_without_update() -> None:
    finding, update = audit_locations.build_location_audit(
        _company(city="Sydney"),
        _facts(hq_city="Byron Bay", hq_country="AU"),
        enriched=True,
    )

    assert finding.action == audit_locations.ACTION_UNSUPPORTED_CITY
    assert update is None
    assert finding.recommended_city == "Byron Bay"


def test_low_confidence_mismatch_requires_manual_review() -> None:
    finding, update = audit_locations.build_location_audit(
        _company(city="Melbourne"),
        _facts(hq_city="Sydney", confidence=0.4),
        enriched=True,
    )

    assert finding.action == audit_locations.ACTION_MANUAL_REVIEW
    assert update is None


def test_artifact_generation_shape(tmp_path: Path) -> None:
    company = _company()
    finding, update = audit_locations.build_location_audit(company, _facts(), enriched=True)

    artifacts = audit_locations._write_artifacts(
        output_dir=tmp_path,
        run_date=audit_locations.date(2026, 5, 1),
        artifact_suffix="test",
        companies=[company],
        findings=[finding],
        proposed_updates=[] if update is None else [update],
        dry_run=False,
        enrich=True,
        credits_used=DEFAULT_CREDITS_PER_ENRICH,
        llm_calls=1,
    )

    assert artifacts.csv_path.exists()
    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert payload["company_count"] == 1
    assert "companies" in payload
    markdown = artifacts.markdown_path.read_text(encoding="utf-8")
    assert "Confirmed: 1" in markdown
    assert "Firecrawl credits used: 8" in markdown


def test_enriched_audit_fails_when_budget_exhaustion_truncates_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        audit_locations,
        "_load_companies",
        lambda *, limit, offset: [_company(name="Budget Target")],
    )
    monkeypatch.setattr(audit_locations, "FirecrawlClient", FakeFirecrawlClient)
    monkeypatch.setattr(audit_locations, "ClaudeClient", FakeClaudeClient)

    def fake_extract(client, llm_client, website: str, *, name: str):
        raise BudgetExceeded("test budget exhausted")

    monkeypatch.setattr(audit_locations, "extract_location_facts", fake_extract)

    with pytest.raises(audit_locations.LocationAuditBudgetExceeded):
        audit_locations.run_audit(
            limit=1,
            offset=0,
            dry_run=False,
            enrich=True,
            output_dir=tmp_path,
            run_date=audit_locations.date(2026, 5, 1),
            artifact_suffix=None,
        )

    assert list(tmp_path.iterdir()) == []


def test_main_rejects_enrich_without_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        audit_locations,
        "run_audit",
        lambda **kwargs: pytest.fail("run_audit should not be called"),
    )

    assert audit_locations.main(["--enrich"]) == 2
