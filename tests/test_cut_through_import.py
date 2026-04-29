"""Tests for the Cut Through report import workflow."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import apply_cut_through_import as apply_import  # noqa: E402
import discover_cut_through_reports as discover_reports  # noqa: E402
import extract_cut_through_report as extract_report  # noqa: E402


class FakeConn:
    """Minimal connection stub for apply tests."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeScraper:
    """Firecrawl PDF scraper stand-in."""

    def __init__(self) -> None:
        self.credits_used = 0
        self.calls = 0
        self.cache_hits = 0

    def scrape_pdf(
        self, *, url: str, parser_mode: str, max_pages: int
    ) -> extract_report.ScrapedPdf:
        self.credits_used += 1
        self.calls += 1
        return extract_report.ScrapedPdf(
            url=url,
            markdown="Advanced Navigation raised US$110M. Bare Dollar Co raised $5M.",
            title="PDF",
            credits_used=1,
            cached=False,
        )


class FakeClaudeClient:
    """Claude client stand-in."""

    def __init__(self) -> None:
        self.stats = SimpleNamespace(calls=0, cache_hits=0, cost_usd=0.0)

    def structured_call(self, **kwargs: Any) -> SimpleNamespace:
        self.stats.calls += 1
        return SimpleNamespace(
            parsed=extract_report.CutThroughReportExtraction(
                funding_events=[
                    extract_report.ExtractedFundingRow(
                        company_name="Advanced Navigation",
                        country="AU",
                        is_ai_related=True,
                        date_precision="quarter",
                        stage="Series C",
                        amount_usd="110000000",
                        currency_raw="US$110M",
                        confidence=0.95,
                    ),
                    extract_report.ExtractedFundingRow(
                        company_name="Bare Dollar Co",
                        country="AU",
                        is_ai_related=True,
                        date_precision="quarter",
                        stage="Seed",
                        amount_usd="5000000",
                        currency_raw="$5M",
                        confidence=0.75,
                    ),
                ],
                company_candidates=[
                    extract_report.ExtractedCompanyCandidate(
                        company_name="Advanced Navigation",
                        country="AU",
                        stage="Series C",
                        founded_year=2012,
                        confidence=0.9,
                    )
                ],
            )
        )


def _review_payload() -> dict[str, Any]:
    return {
        "schema_version": apply_import.SCHEMA_VERSION,
        "funding_events": [
            {
                "reviewed_action": "upsert",
                "company_name": "New AI Co",
                "country": "AU",
                "announced_on": "2026-03-31",
                "date_precision": "quarter",
                "stage": "seed",
                "amount_usd": None,
                "currency_raw": "A$5M",
                "lead_investor": None,
                "investors": [],
                "source_url": "https://www.cutthrough.com/insights/cut-through-quarterly-1q-2026",
                "provenance": {},
                "confidence": 0.9,
                "notes": None,
            }
        ],
        "company_candidates": [
            {
                "reviewed_action": "insert_pending",
                "company_name": "New AI Co",
                "country": "AU",
                "website": None,
                "city": "Sydney",
                "sector_tags": ["agents"],
                "stage": "seed",
                "founded_year": 2024,
                "summary": "AI workflow company.",
                "evidence_urls": [
                    "https://www.cutthrough.com/insights/cut-through-quarterly-1q-2026"
                ],
                "discovery_source": "cut_through_report",
                "provenance": {},
                "confidence": 0.8,
                "notes": None,
            }
        ],
    }


def test_discovery_parses_quarterly_report_and_drive_download_url() -> None:
    body = """
    <a href="/insights/cut-through-quarterly-1q-2026">April 28, 2026 Cut Through Quarterly 1Q 2026 Australian venture capital funding report for 1Q 2026.</a>
    <a href="https://drive.google.com/file/d/abc123/view">April 28, 2026 Cut Through Quarterly 1Q 2026 Australian venture capital funding report for 1Q 2026.</a>
    """

    reports = discover_reports.parse_reports_from_html(body, quarter=1, year=2026)

    assert len(reports) == 1
    assert reports[0].title == "Cut Through Quarterly 1Q 2026"
    assert reports[0].publication_date == "2026-04-28"
    assert reports[0].pdf_download_url == "https://drive.google.com/uc?export=download&id=abc123"


def test_discovery_parses_firecrawl_markdown_card_links() -> None:
    body = r"""
    [![Cut Through Quarterly 1Q 2026](https://cdn.example/image.png)\\
    \\
    April 28, 2026\\
    \\
    **Cut Through Quarterly 1Q 2026** \\
    \\
    Australian venture capital funding report for 1Q 2026.](https://www.cutthrough.com/insights/cut-through-quarterly-1q-2026)

    [![Cut Through Quarterly 1Q 2026](https://cdn.example/image.png)\\
    \\
    April 28, 2026\\
    \\
    **Cut Through Quarterly 1Q 2026** \\
    \\
    Australian venture capital funding report for 1Q 2026.](https://drive.google.com/file/d/abc123/view)
    """

    reports = discover_reports.parse_reports_from_html(body, quarter=1, year=2026)

    assert len(reports) == 1
    assert reports[0].report_url.endswith("/cut-through-quarterly-1q-2026")
    assert reports[0].pdf_download_url == "https://drive.google.com/uc?export=download&id=abc123"


def test_discovery_converts_google_drive_user_file_url() -> None:
    url = "https://drive.google.com/file/u/1/d/abc123/view?usp=sharing"

    assert (
        discover_reports.google_drive_download_url(url)
        == "https://drive.google.com/uc?export=download&id=abc123"
    )


def test_extract_writes_artifacts_and_preserves_non_usd_raw_amounts(tmp_path: Path) -> None:
    report = discover_reports.CutThroughReport(
        title="Cut Through Quarterly 1Q 2026",
        publication_date="2026-04-28",
        report_url="https://www.cutthrough.com/insights/cut-through-quarterly-1q-2026",
        pdf_url="https://drive.google.com/file/d/abc123/view",
        pdf_download_url="https://drive.google.com/uc?export=download&id=abc123",
        quarter=1,
        year=2026,
        summary=None,
    )

    artifacts = extract_report.run_extract(
        quarter=None,
        year=None,
        limit_reports=1,
        no_discover=True,
        report=report,
        output_dir=tmp_path,
        run_date=date(2026, 4, 29),
        artifact_suffix=None,
        dry_run=True,
        parser_mode="fast",
        max_pages=5,
        max_markdown_chars=5000,
        scraper=FakeScraper(),
        llm_client=FakeClaudeClient(),
    )
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))

    assert payload["funding_events"][0]["announced_on"] == "2026-03-31"
    assert payload["funding_events"][0]["stage"] == "series_b_plus"
    assert payload["funding_events"][0]["amount_usd"] == "110000000"
    assert payload["funding_events"][1]["currency_raw"] == "$5M"
    assert payload["funding_events"][1]["amount_usd"] is None
    assert payload["company_candidates"][0]["reviewed_action"] == "needs_review"
    assert payload["company_candidates"][0]["founded_year"] == 2012
    assert artifacts.csv_path.exists()
    assert artifacts.markdown_path.exists()


def test_apply_validation_rejects_bare_dollar_amount_usd(tmp_path: Path) -> None:
    payload = _review_payload()
    payload["funding_events"][0]["amount_usd"] = "5000000"
    payload["funding_events"][0]["currency_raw"] = "$5M"
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    summary = apply_import.run_apply(input_path=path, apply=False)

    assert summary.errors
    assert "amount_usd is allowed only when currency_raw is explicit USD" in summary.errors[0]


def test_apply_dry_run_counts_reviewed_actions(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    payload = _review_payload()
    payload["company_candidates"].append(
        {
            "reviewed_action": "update_verified_fields",
            "company_name": "Verified AI Co",
            "country": "AU",
            "website": None,
            "city": None,
            "sector_tags": [],
            "stage": None,
            "founded_year": 2020,
            "summary": None,
            "evidence_urls": ["https://www.cutthrough.com/insights/cut-through-quarterly-1q-2026"],
            "discovery_source": "cut_through_report",
            "provenance": {},
            "confidence": 0.8,
            "notes": None,
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    summary = apply_import.run_apply(input_path=path, apply=False)

    assert summary.errors == []
    assert summary.funding_upserted == 1
    assert summary.companies_inserted_pending == 1
    assert summary.companies_stage_updated == 0
    assert summary.companies_verified_updated == 1


def test_apply_snapshots_before_writes(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(_review_payload()), encoding="utf-8")
    fake_conn = FakeConn()
    order: list[str] = []
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example")

    @contextmanager
    def fake_connection():
        yield fake_conn

    monkeypatch.setattr(apply_import.supabase_db, "connection", fake_connection)
    monkeypatch.setattr(apply_import, "_resolve_company", lambda conn, row: None)
    monkeypatch.setattr(
        apply_import,
        "_write_snapshot",
        lambda **kwargs: order.append("snapshot") or tmp_path / "snapshot.json",
    )
    monkeypatch.setattr(
        apply_import,
        "_insert_pending_company",
        lambda conn, row: order.append("insert_company") or "company-1",
    )
    monkeypatch.setattr(
        apply_import,
        "_upsert_funding_event",
        lambda conn, row, company_id: order.append("upsert_funding") or "funding-1",
    )

    summary = apply_import.run_apply(input_path=path, apply=True, snapshot_dir=tmp_path)

    assert summary.errors == []
    assert order == ["snapshot", "insert_company", "upsert_funding"]
    assert fake_conn.commits == 1


def test_apply_updates_verified_founded_year(tmp_path: Path, monkeypatch) -> None:
    payload = _review_payload()
    payload["funding_events"] = []
    payload["company_candidates"] = [
        {
            "reviewed_action": "update_verified_fields",
            "company_name": "Verified AI Co",
            "country": "AU",
            "website": None,
            "city": None,
            "sector_tags": [],
            "stage": "series_a",
            "founded_year": 2020,
            "summary": None,
            "evidence_urls": ["https://www.cutthrough.com/insights/cut-through-quarterly-1q-2026"],
            "discovery_source": "cut_through_report",
            "provenance": {},
            "confidence": 0.8,
            "notes": None,
        }
    ]
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    fake_conn = FakeConn()
    updates_seen: list[dict[str, Any]] = []
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example")

    @contextmanager
    def fake_connection():
        yield fake_conn

    monkeypatch.setattr(apply_import.supabase_db, "connection", fake_connection)
    monkeypatch.setattr(
        apply_import,
        "_resolve_company",
        lambda conn, row: {"id": "company-1", "discovery_status": "verified"},
    )
    monkeypatch.setattr(
        apply_import,
        "_write_snapshot",
        lambda **kwargs: tmp_path / "snapshot.json",
    )
    monkeypatch.setattr(
        apply_import.supabase_db,
        "update_company_enrichment",
        lambda conn, company_id, updates, enriched_at: updates_seen.append(updates),
    )

    summary = apply_import.run_apply(input_path=path, apply=True, snapshot_dir=tmp_path)

    assert summary.errors == []
    assert summary.companies_verified_updated == 1
    assert updates_seen[0]["stage"] == "series_a"
    assert updates_seen[0]["founded_year"] == 2020
    assert fake_conn.commits == 1


def test_apply_json_default_serialises_uuid() -> None:
    assert (
        apply_import._json_default(UUID("00000000-0000-0000-0000-000000000001"))
        == "00000000-0000-0000-0000-000000000001"
    )
