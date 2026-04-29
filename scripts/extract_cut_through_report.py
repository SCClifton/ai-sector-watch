#!/usr/bin/env python3
"""Extract reviewed Cut Through import artifacts from report PDFs.

This script discovers selected Cut Through Quarterly reports, parses linked
PDFs through Firecrawl, and asks Claude for candidate funding rows and company
candidates. It never writes to Supabase.

Usage:
    op run --account my.1password.com --env-file=.env.local -- python scripts/extract_cut_through_report.py --quarter 1 --year 2026 --limit-reports 1 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from discover_cut_through_reports import (  # noqa: E402
    CutThroughReport,
    discover_reports,
    google_drive_download_url,
)

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.extraction.claude_client import BudgetExceeded, ClaudeClient  # noqa: E402

LOGGER = logging.getLogger("extract_cut_through_report")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "data-audits"
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "local" / "cut_through_cache"
SCHEMA_VERSION = "cut_through_import.v1"
VALID_STAGES = {"pre_seed", "seed", "series_a", "series_b_plus", "mature"}
MAX_REPORTS_PER_RUN = 2

EXTRACTION_SYSTEM = (
    "You extract structured Australian startup funding facts from Cut Through report text. "
    "Use only the supplied report markdown. Do not infer missing currencies. Do not assume "
    "USD from a bare dollar sign. If the report says $, A$, AUD, or does not name USD, put "
    "the original amount text in currency_raw and leave amount_usd null. Only set amount_usd "
    "when the text explicitly says USD, US$, or another unambiguous USD marker. When a row "
    "only gives a quarter, use the quarter-end date supplied in the prompt. Return only rows "
    "that are relevant to AI-first or AI-enabled companies, or rows where AI relevance needs "
    "manual review."
)


class ExtractedFundingRow(BaseModel):
    """Funding row extracted from a Cut Through report."""

    company_name: str
    country: str | None = Field(None, description="AU, NZ, or null when unstated.")
    is_ai_related: bool = False
    announced_on: date | None = None
    date_precision: Literal["exact", "month", "quarter", "unknown"] = "unknown"
    stage: str | None = Field(None, description="pre_seed, seed, series_a, series_b_plus, mature")
    amount_usd: Decimal | None = Field(None, ge=0)
    currency_raw: str | None = None
    lead_investor: str | None = None
    investors: list[str] = Field(default_factory=list)
    source_quote: str | None = None
    page_number: int | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    notes: str | None = None


class ExtractedCompanyCandidate(BaseModel):
    """Company candidate extracted from a Cut Through report."""

    company_name: str
    country: str | None = Field(None, description="AU, NZ, or null when unstated.")
    website: str | None = None
    city: str | None = None
    sector_tags: list[str] = Field(default_factory=list)
    stage: str | None = Field(None, description="pre_seed, seed, series_a, series_b_plus, mature")
    founded_year: int | None = Field(None, ge=1900, le=2100)
    summary: str | None = None
    source_quote: str | None = None
    page_number: int | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    notes: str | None = None


class CutThroughReportExtraction(BaseModel):
    """Top-level Claude extraction shape for one report."""

    funding_events: list[ExtractedFundingRow] = Field(default_factory=list)
    company_candidates: list[ExtractedCompanyCandidate] = Field(default_factory=list)


@dataclass(frozen=True)
class ScrapedPdf:
    """Markdown returned from Firecrawl for one report PDF."""

    url: str
    markdown: str
    title: str | None
    credits_used: int
    cached: bool


@dataclass(frozen=True)
class ExtractArtifacts:
    """Paths emitted by a Cut Through extraction run."""

    markdown_path: Path
    csv_path: Path
    json_path: Path


class FirecrawlPdfScraper:
    """Budget-capped Firecrawl PDF-to-markdown scraper."""

    def __init__(
        self,
        *,
        budget_credits: int | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.budget_credits = budget_credits or int(
            os.environ.get("FIRECRAWL_BUDGET_CREDITS_PER_RUN", "20")
        )
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.credits_used = 0
        self.calls = 0
        self.cache_hits = 0
        self._client = None

    @property
    def firecrawl(self):
        """Lazy import and auth so tests can monkeypatch dispatch."""
        if self._client is None:
            from firecrawl import Firecrawl

            api_key = os.environ.get("FIRECRAWL_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "FIRECRAWL_API_KEY not set; run via op run --account my.1password.com "
                    "--env-file=.env.local -- ..."
                )
            self._client = Firecrawl(api_key=api_key)
        return self._client

    def scrape_pdf(
        self,
        *,
        url: str,
        parser_mode: str,
        max_pages: int,
    ) -> ScrapedPdf:
        """Scrape one PDF URL through Firecrawl and return markdown."""
        cache_key = _hash("cut-through-pdf-v1", url, parser_mode, str(max_pages))
        cached = self._read_cache(cache_key)
        if cached is not None:
            self.cache_hits += 1
            return ScrapedPdf(
                url=url,
                markdown=str(cached["markdown"]),
                title=cached.get("title"),
                credits_used=0,
                cached=True,
            )
        self._ensure_budget(1)
        document = self._dispatch_scrape(url=url, parser_mode=parser_mode, max_pages=max_pages)
        self.calls += 1
        self.credits_used += 1
        self._write_cache(cache_key, asdict(document))
        return document

    def _dispatch_scrape(self, *, url: str, parser_mode: str, max_pages: int) -> ScrapedPdf:
        """Call Firecrawl /scrape with the PDF parser enabled."""
        try:
            from firecrawl.v2.types import PDFParser

            parsers: list[Any] = [PDFParser(type="pdf", mode=parser_mode, max_pages=max_pages)]
        except Exception:  # noqa: BLE001
            parsers = [{"type": "pdf", "mode": parser_mode, "maxPages": max_pages}]
        document = self.firecrawl.scrape(
            url,
            formats=["markdown"],
            parsers=parsers,
            only_main_content=False,
        )
        markdown = _read_attr_or_key(document, "markdown")
        if not markdown:
            raise RuntimeError("firecrawl returned no markdown payload")
        metadata = _read_attr_or_key(document, "metadata") or {}
        title = _read_attr_or_key(metadata, "title")
        return ScrapedPdf(
            url=url,
            markdown=str(markdown),
            title=str(title) if title else None,
            credits_used=1,
            cached=False,
        )

    def _ensure_budget(self, estimated_credits: int) -> None:
        if self.credits_used + estimated_credits > self.budget_credits:
            raise RuntimeError(
                f"would exceed {self.budget_credits}-credit Firecrawl cap "
                f"(used {self.credits_used}, next call costs {estimated_credits})"
            )

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            LOGGER.warning("failed to read Firecrawl cache %s: %s", path, exc)
            return None

    def _write_cache(self, key: str, payload: dict[str, Any]) -> None:
        path = self._cache_path(key)
        try:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except OSError as exc:
            LOGGER.warning("failed to write Firecrawl cache %s: %s", path, exc)


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _read_attr_or_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")


def _sanitise_text(value: str | None) -> str | None:
    """Replace user-facing dash punctuation with a plain hyphen."""
    if value is None:
        return None
    return value.replace("—", " - ").replace("–", " - ").replace("  -  ", " - ")


def _sanitise_payload(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitise_text(value)
    if isinstance(value, list):
        return [_sanitise_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitise_payload(item) for key, item in value.items()}
    return value


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


def _quarter_end(year: int, quarter: int) -> date:
    month_day = {
        1: (3, 31),
        2: (6, 30),
        3: (9, 30),
        4: (12, 31),
    }
    month, day = month_day[quarter]
    return date(year, month, day)


def _clean_stage(stage: str | None) -> str | None:
    if not stage:
        return None
    normalised = stage.lower().replace("-", " ").replace("_", " ").strip()
    normalised = " ".join(normalised.split())
    stage_map = {
        "angel": "pre_seed",
        "pre seed": "pre_seed",
        "preseed": "pre_seed",
        "seed": "seed",
        "series a": "series_a",
        "series b": "series_b_plus",
        "series b+": "series_b_plus",
        "series b plus": "series_b_plus",
        "series c": "series_b_plus",
        "series d": "series_b_plus",
        "series e": "series_b_plus",
        "growth": "series_b_plus",
        "late stage": "series_b_plus",
        "mature": "mature",
    }
    return stage_map.get(normalised)


def _currency_is_explicit_usd(currency_raw: str | None) -> bool:
    if not currency_raw:
        return False
    raw = currency_raw.upper().replace(" ", "")
    return "USD" in raw or "US$" in raw or raw.startswith("US$")


def _trim_markdown(markdown: str, max_chars: int) -> str:
    if len(markdown) <= max_chars:
        return markdown
    return markdown[:max_chars] + "\n\n[TRUNCATED]\n"


def _extraction_prompt(
    *,
    report: CutThroughReport,
    markdown: str,
    max_markdown_chars: int,
) -> str:
    quarter_end = (
        _quarter_end(report.year, report.quarter).isoformat()
        if report.year is not None and report.quarter is not None
        else "unknown"
    )
    return f"""Report metadata:
title: {report.title}
publication_date: {report.publication_date}
report_url: {report.report_url}
pdf_url: {report.pdf_url}
quarter: {report.quarter}
year: {report.year}
quarter_end_date: {quarter_end}

Extract:
1. Candidate funding events for AI-first or AI-enabled companies in Australia or New Zealand.
2. Company candidates that AI Sector Watch may need to add or update.
3. Founded years when the report explicitly states or clearly implies a company founding year.

Rules:
- Keep original report amount text in currency_raw.
- Set amount_usd only when the report explicitly names USD or US$.
- Do not convert AUD, A$, NZD, or bare $ amounts.
- Use quarter_end_date when only the quarter is available.
- Use stage values only from: pre_seed, seed, series_a, series_b_plus, mature.
- Set founded_year only when the report text supports it directly. Do not infer from funding stage.
- Include page_number and source_quote when available.
- Use concise notes for any ambiguity.

Report markdown:
{_trim_markdown(markdown, max_markdown_chars)}
"""


def extract_report(
    *,
    report: CutThroughReport,
    scraper: FirecrawlPdfScraper,
    llm_client: ClaudeClient,
    parser_mode: str,
    max_pages: int,
    max_markdown_chars: int,
) -> tuple[ScrapedPdf, CutThroughReportExtraction]:
    """Parse one report PDF and return structured candidate rows."""
    if not report.pdf_download_url and not report.pdf_url:
        raise ValueError(f"{report.title} has no PDF URL")
    pdf_url = report.pdf_download_url or report.pdf_url
    assert pdf_url is not None
    scraped = scraper.scrape_pdf(url=pdf_url, parser_mode=parser_mode, max_pages=max_pages)
    response = llm_client.structured_call(
        system=EXTRACTION_SYSTEM,
        prompt=_extraction_prompt(
            report=report,
            markdown=scraped.markdown,
            max_markdown_chars=max_markdown_chars,
        ),
        schema_cls=CutThroughReportExtraction,
        max_tokens=4096,
    )
    return scraped, response.parsed  # type: ignore[return-value]


def _normalise_funding_event(
    row: ExtractedFundingRow,
    *,
    report: CutThroughReport,
) -> dict[str, Any]:
    amount_usd = row.amount_usd
    notes = row.notes or ""
    if amount_usd is not None and not _currency_is_explicit_usd(row.currency_raw):
        amount_usd = None
        notes = (
            notes + " " if notes else ""
        ) + "amount_usd cleared because currency is not explicit USD"
    announced_on = row.announced_on
    if (
        announced_on is None
        and row.date_precision in {"quarter", "unknown"}
        and report.year is not None
        and report.quarter is not None
    ):
        announced_on = _quarter_end(report.year, report.quarter)
    return {
        "reviewed_action": "needs_review",
        "company_name": row.company_name.strip(),
        "country": row.country,
        "is_ai_related": row.is_ai_related,
        "announced_on": announced_on,
        "date_precision": row.date_precision,
        "stage": _clean_stage(row.stage),
        "amount_usd": amount_usd,
        "currency_raw": row.currency_raw,
        "lead_investor": _sanitise_text(row.lead_investor),
        "investors": [_sanitise_text(investor) or "" for investor in row.investors],
        "source_url": report.report_url,
        "provenance": {
            "report_title": report.title,
            "publication_date": report.publication_date,
            "report_url": report.report_url,
            "pdf_url": report.pdf_url,
            "pdf_download_url": report.pdf_download_url,
            "page_number": row.page_number,
            "source_quote": _sanitise_text(row.source_quote),
        },
        "confidence": row.confidence,
        "notes": _sanitise_text(notes) if notes else None,
    }


def _normalise_company_candidate(
    row: ExtractedCompanyCandidate,
    *,
    report: CutThroughReport,
) -> dict[str, Any]:
    evidence_urls = [url for url in [report.report_url, report.pdf_url] if url]
    return {
        "reviewed_action": "needs_review",
        "company_name": row.company_name.strip(),
        "country": row.country,
        "website": row.website,
        "city": row.city,
        "sector_tags": row.sector_tags,
        "stage": _clean_stage(row.stage),
        "founded_year": row.founded_year,
        "summary": _sanitise_text(row.summary),
        "evidence_urls": evidence_urls,
        "discovery_source": "cut_through_report",
        "provenance": {
            "report_title": report.title,
            "publication_date": report.publication_date,
            "report_url": report.report_url,
            "pdf_url": report.pdf_url,
            "pdf_download_url": report.pdf_download_url,
            "page_number": row.page_number,
            "source_quote": _sanitise_text(row.source_quote),
        },
        "confidence": row.confidence,
        "notes": _sanitise_text(row.notes),
    }


def _write_artifacts(
    *,
    output_dir: Path,
    run_date: date,
    artifact_suffix: str | None,
    dry_run: bool,
    reports: list[CutThroughReport],
    scraped_pdfs: list[ScrapedPdf],
    funding_events: list[dict[str, Any]],
    company_candidates: list[dict[str, Any]],
    scraper: FirecrawlPdfScraper,
    llm_client: ClaudeClient,
) -> ExtractArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{artifact_suffix}" if artifact_suffix else ""
    stem = f"{run_date.isoformat()}-cut-through-import{suffix}"
    markdown_path = output_dir / f"{stem}.md"
    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = [
            "row_type",
            "reviewed_action",
            "company_name",
            "country",
            "announced_on",
            "date_precision",
            "stage",
            "founded_year",
            "amount_usd",
            "currency_raw",
            "lead_investor",
            "investors",
            "report_title",
            "report_url",
            "pdf_url",
            "page_number",
            "confidence",
            "notes",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in funding_events:
            provenance = row["provenance"]
            writer.writerow(
                {
                    "row_type": "funding_event",
                    "reviewed_action": row["reviewed_action"],
                    "company_name": row["company_name"],
                    "country": _csv_value(row.get("country")),
                    "announced_on": _csv_value(row.get("announced_on")),
                    "date_precision": _csv_value(row.get("date_precision")),
                    "stage": _csv_value(row.get("stage")),
                    "founded_year": "",
                    "amount_usd": _csv_value(row.get("amount_usd")),
                    "currency_raw": _csv_value(row.get("currency_raw")),
                    "lead_investor": _csv_value(row.get("lead_investor")),
                    "investors": ", ".join(row.get("investors") or []),
                    "report_title": provenance["report_title"],
                    "report_url": provenance["report_url"],
                    "pdf_url": _csv_value(provenance.get("pdf_url")),
                    "page_number": _csv_value(provenance.get("page_number")),
                    "confidence": _csv_value(row.get("confidence")),
                    "notes": _csv_value(row.get("notes")),
                }
            )
        for row in company_candidates:
            provenance = row["provenance"]
            writer.writerow(
                {
                    "row_type": "company_candidate",
                    "reviewed_action": row["reviewed_action"],
                    "company_name": row["company_name"],
                    "country": _csv_value(row.get("country")),
                    "announced_on": "",
                    "date_precision": "",
                    "stage": _csv_value(row.get("stage")),
                    "founded_year": _csv_value(row.get("founded_year")),
                    "amount_usd": "",
                    "currency_raw": "",
                    "lead_investor": "",
                    "investors": "",
                    "report_title": provenance["report_title"],
                    "report_url": provenance["report_url"],
                    "pdf_url": _csv_value(provenance.get("pdf_url")),
                    "page_number": _csv_value(provenance.get("page_number")),
                    "confidence": _csv_value(row.get("confidence")),
                    "notes": _csv_value(row.get("notes")),
                }
            )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC),
        "dry_run": dry_run,
        "reports": [asdict(report) for report in reports],
        "scraped_pdfs": [asdict(scraped) for scraped in scraped_pdfs],
        "extraction": {
            "firecrawl_credits_used": scraper.credits_used,
            "firecrawl_calls": scraper.calls,
            "firecrawl_cache_hits": scraper.cache_hits,
            "llm_calls": llm_client.stats.calls,
            "llm_cache_hits": llm_client.stats.cache_hits,
            "llm_cost_usd": llm_client.stats.cost_usd,
        },
        "funding_events": funding_events,
        "company_candidates": company_candidates,
    }
    payload = _sanitise_payload(payload)
    json_path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")

    lines = [
        f"# Cut Through Import Review: {run_date.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Reports parsed: {len(reports)}",
        f"- Funding event candidates: {len(funding_events)}",
        f"- Company candidates: {len(company_candidates)}",
        f"- Firecrawl credits used: {scraper.credits_used}",
        f"- LLM calls: {llm_client.stats.calls}",
        f"- Dry run: {dry_run}",
        "",
        "## Review Instructions",
        "",
        "Set `reviewed_action` before applying. Use `upsert` for funding events, "
        "`insert_pending` for new company candidates, `update_verified_stage` for reviewed "
        "stage-only updates to existing verified companies, `update_verified_fields` for reviewed "
        "stage/founded-year updates to existing verified companies, and `skip` for rows that "
        "should not apply.",
        "",
        "## Reports",
        "",
    ]
    for report in reports:
        lines.append(f"- {report.title}: {report.report_url}")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- CSV review table: `{csv_path.name}`",
            f"- Reviewed JSON payload: `{json_path.name}`",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ExtractArtifacts(markdown_path=markdown_path, csv_path=csv_path, json_path=json_path)


def _report_from_args(args: argparse.Namespace) -> CutThroughReport:
    if not args.report_url:
        raise ValueError("--report-url is required when --no-discover is used")
    if not args.report_title:
        raise ValueError("--report-title is required when --no-discover is used")
    return CutThroughReport(
        title=args.report_title,
        publication_date=args.publication_date,
        report_url=args.report_url,
        pdf_url=args.pdf_url,
        pdf_download_url=google_drive_download_url(args.pdf_url),
        quarter=args.quarter,
        year=args.year,
        summary=None,
    )


def run_extract(
    *,
    quarter: int | None,
    year: int | None,
    limit_reports: int,
    no_discover: bool,
    report: CutThroughReport | None,
    output_dir: Path,
    run_date: date,
    artifact_suffix: str | None,
    dry_run: bool,
    parser_mode: str,
    max_pages: int,
    max_markdown_chars: int,
    scraper: FirecrawlPdfScraper | None = None,
    llm_client: ClaudeClient | None = None,
) -> ExtractArtifacts:
    """Run Cut Through extraction and write review artifacts."""
    if limit_reports < 1 or limit_reports > MAX_REPORTS_PER_RUN:
        raise ValueError(f"limit_reports must be between 1 and {MAX_REPORTS_PER_RUN}")
    selected_reports = (
        [report]
        if no_discover and report is not None
        else discover_reports(
            quarter=quarter,
            year=year,
            limit=limit_reports,
        )
    )
    if not selected_reports:
        raise ValueError("no matching Cut Through reports found")

    scraper = scraper or FirecrawlPdfScraper()
    llm_client = llm_client or ClaudeClient()
    scraped_pdfs: list[ScrapedPdf] = []
    funding_events: list[dict[str, Any]] = []
    company_candidates: list[dict[str, Any]] = []

    for selected in selected_reports:
        LOGGER.info("extracting %s", selected.title)
        try:
            scraped, extraction = extract_report(
                report=selected,
                scraper=scraper,
                llm_client=llm_client,
                parser_mode=parser_mode,
                max_pages=max_pages,
                max_markdown_chars=max_markdown_chars,
            )
        except BudgetExceeded as exc:
            raise RuntimeError(
                f"LLM budget exhausted while extracting {selected.title}: {exc}"
            ) from exc
        scraped_pdfs.append(scraped)
        funding_events.extend(
            _normalise_funding_event(row, report=selected) for row in extraction.funding_events
        )
        company_candidates.extend(
            _normalise_company_candidate(row, report=selected)
            for row in extraction.company_candidates
        )

    return _write_artifacts(
        output_dir=output_dir,
        run_date=run_date,
        artifact_suffix=artifact_suffix,
        dry_run=dry_run,
        reports=selected_reports,
        scraped_pdfs=scraped_pdfs,
        funding_events=funding_events,
        company_candidates=company_candidates,
        scraper=scraper,
        llm_client=llm_client,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quarter", type=int, choices=(1, 2, 3, 4))
    parser.add_argument("--year", type=int)
    parser.add_argument("--limit-reports", type=int, default=1)
    parser.add_argument("--no-discover", action="store_true")
    parser.add_argument("--report-url")
    parser.add_argument("--report-title")
    parser.add_argument("--publication-date")
    parser.add_argument("--pdf-url")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--artifact-suffix")
    parser.add_argument("--dry-run", action="store_true", help="Annotate artifacts as dry-run")
    parser.add_argument("--parser-mode", choices=("fast", "auto"), default="fast")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--max-markdown-chars", type=int, default=45_000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    if not args.no_discover and (args.quarter is None or args.year is None):
        LOGGER.error("--quarter and --year are required unless --no-discover is used")
        return 2
    if args.max_pages < 1:
        LOGGER.error("--max-pages must be positive")
        return 2
    report = _report_from_args(args) if args.no_discover else None
    try:
        artifacts = run_extract(
            quarter=args.quarter,
            year=args.year,
            limit_reports=args.limit_reports,
            no_discover=args.no_discover,
            report=report,
            output_dir=args.output_dir,
            run_date=args.run_date,
            artifact_suffix=args.artifact_suffix,
            dry_run=args.dry_run,
            parser_mode=args.parser_mode,
            max_pages=args.max_pages,
            max_markdown_chars=args.max_markdown_chars,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("%s", exc)
        return 1
    print(json.dumps({k: str(v) for k, v in asdict(artifacts).items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
