#!/usr/bin/env python3
"""Discover Cut Through report pages and linked PDFs.

The script is read-only. It scrapes the public Cut Through insights index,
filters to report cards, and emits structured report metadata that can be
handed to `scripts/extract_cut_through_report.py`.

Usage:
    op run --account my.1password.com --env-file=.env.local -- python scripts/discover_cut_through_reports.py --quarter 1 --year 2026
    python scripts/discover_cut_through_reports.py --http-fallback --output docs/data-audits/cut-through-reports.json
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402

LOGGER = logging.getLogger("discover_cut_through_reports")

INSIGHTS_URL = "https://www.cutthrough.com/insights"
USER_AGENT = "AI-Sector-Watch/0.1 (+https://aimap.cliftonfamily.co)"
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "local" / "cut_through_cache"
MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<text>.*?)</a>", re.I | re.S
)
MARKDOWN_LINK_RE = re.compile(r"\[(?P<text>[^\]]+)\]\((?P<href>[^)]+)\)")
MARKDOWN_CARD_LINK_RE = re.compile(
    r"\[!\[[^\]]+\]\([^)]+\)(?P<text>.*?)\]\((?P<href>https?://[^)]+)\)", re.S
)
DATE_RE = re.compile(
    r"\b(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(?P<day>\d{1,2}),\s+(?P<year>\d{4})\b"
)
QUARTERLY_TITLE_RE = re.compile(
    r"\bCut Through Quarterly\s+(?P<quarter>[1-4])Q\s+(?P<year>\d{4})\b", re.I
)
DRIVE_FILE_RE = re.compile(r"/file/(?:u/\d+/)?d/(?P<id>[^/]+)/")


@dataclass(frozen=True)
class CutThroughReport:
    """One report discovered from the Cut Through insights index."""

    title: str
    publication_date: str | None
    report_url: str
    pdf_url: str | None
    pdf_download_url: str | None
    quarter: int | None
    year: int | None
    summary: str | None


class FirecrawlInsightsScraper:
    """Budget-capped Firecrawl scraper for the Cut Through insights index."""

    def __init__(self, *, budget_credits: int | None = None, cache_dir: Path | None = None) -> None:
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
        """Lazy import and auth so tests can use parse helpers without Firecrawl."""
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

    def scrape_markdown(self, url: str) -> str:
        """Scrape the insights page with Firecrawl and return markdown."""
        cache_key = _hash("cut-through-insights-v1", url)
        cache_path = self.cache_dir / f"{cache_key}.md"
        if cache_path.exists():
            self.cache_hits += 1
            return cache_path.read_text(encoding="utf-8")
        self._ensure_budget(1)
        document = self.firecrawl.scrape(url, formats=["markdown"], only_main_content=False)
        markdown = _read_attr_or_key(document, "markdown")
        if not markdown:
            raise RuntimeError("firecrawl returned no insights markdown payload")
        self.calls += 1
        self.credits_used += 1
        cache_path.write_text(str(markdown), encoding="utf-8")
        return str(markdown)

    def _ensure_budget(self, estimated_credits: int) -> None:
        if self.credits_used + estimated_credits > self.budget_credits:
            raise RuntimeError(
                f"would exceed {self.budget_credits}-credit Firecrawl cap "
                f"(used {self.credits_used}, next call costs {estimated_credits})"
            )


def _hash(*parts: str) -> str:
    import hashlib

    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _read_attr_or_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = text.replace("\\", " ").replace("**", " ")
    return " ".join(html.unescape(text).split())


def google_drive_download_url(url: str | None) -> str | None:
    """Convert a Google Drive file URL to a direct download URL."""
    if not url:
        return None
    parsed = urlparse(url)
    if "drive.google.com" not in parsed.netloc:
        return url
    match = DRIVE_FILE_RE.search(parsed.path)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group('id')}"
    file_id = parse_qs(parsed.query).get("id", [None])[0]
    if file_id:
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url


def _parse_date(text: str) -> date | None:
    match = DATE_RE.search(text)
    if not match:
        return None
    return date(
        int(match.group("year")),
        MONTHS[match.group("month")],
        int(match.group("day")),
    )


def _parse_quarter(text: str) -> tuple[int | None, int | None]:
    match = QUARTERLY_TITLE_RE.search(text)
    if not match:
        return None, None
    return int(match.group("quarter")), int(match.group("year"))


def _parse_report_title(text: str) -> str | None:
    match = QUARTERLY_TITLE_RE.search(text)
    if match:
        return match.group(0)
    return None


def _parse_summary(text: str, title: str) -> str | None:
    summary = text
    parsed_date = DATE_RE.search(summary)
    if parsed_date:
        summary = summary[parsed_date.end() :]
    summary = summary.replace(title, "", 1).strip(" .")
    return summary or None


def discover_reports(
    *,
    insights_url: str = INSIGHTS_URL,
    quarterly_only: bool = True,
    quarter: int | None = None,
    year: int | None = None,
    limit: int | None = None,
    use_firecrawl: bool = True,
    scraper: FirecrawlInsightsScraper | None = None,
) -> list[CutThroughReport]:
    """Discover Cut Through reports from the public insights index."""
    if use_firecrawl:
        scraper = scraper or FirecrawlInsightsScraper()
        body = scraper.scrape_markdown(insights_url)
    else:
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=30, headers=headers, follow_redirects=True) as client:
            response = client.get(insights_url)
            response.raise_for_status()
        body = response.text
    return parse_reports_from_html(
        body,
        base_url=insights_url,
        quarterly_only=quarterly_only,
        quarter=quarter,
        year=year,
        limit=limit,
    )


def parse_reports_from_html(
    body: str,
    *,
    base_url: str = INSIGHTS_URL,
    quarterly_only: bool = True,
    quarter: int | None = None,
    year: int | None = None,
    limit: int | None = None,
) -> list[CutThroughReport]:
    """Parse report metadata from a Cut Through insights HTML document."""
    reports_by_url: dict[str, dict[str, Any]] = {}
    last_report_url: str | None = None

    anchors = [
        (html.unescape(match.group("href")), _strip_tags(match.group("text")))
        for match in ANCHOR_RE.finditer(body)
    ]
    anchors.extend(
        (html.unescape(match.group("href")), _strip_tags(match.group("text")))
        for match in MARKDOWN_CARD_LINK_RE.finditer(body)
    )
    anchors.extend(
        (html.unescape(match.group("href")), _strip_tags(match.group("text")))
        for match in MARKDOWN_LINK_RE.finditer(body)
    )

    for href, text in anchors:
        url = urljoin(base_url, href)
        parsed = urlparse(url)
        is_report_page = parsed.netloc.endswith("cutthrough.com") and parsed.path.startswith(
            "/insights/"
        )
        is_drive_link = parsed.netloc.endswith("drive.google.com")
        title = _parse_report_title(text)

        if is_report_page and title:
            publication_date = _parse_date(text)
            report_quarter, report_year = _parse_quarter(title)
            reports_by_url.setdefault(
                url,
                {
                    "title": title,
                    "publication_date": publication_date.isoformat() if publication_date else None,
                    "report_url": url,
                    "pdf_url": None,
                    "quarter": report_quarter,
                    "year": report_year,
                    "summary": _parse_summary(text, title),
                },
            )
            last_report_url = url
            continue

        if is_drive_link and last_report_url and last_report_url in reports_by_url:
            report = reports_by_url[last_report_url]
            if report["pdf_url"] is None:
                report["pdf_url"] = url

    reports = [
        CutThroughReport(
            title=str(item["title"]),
            publication_date=item["publication_date"],
            report_url=str(item["report_url"]),
            pdf_url=item["pdf_url"],
            pdf_download_url=google_drive_download_url(item["pdf_url"]),
            quarter=item["quarter"],
            year=item["year"],
            summary=item["summary"],
        )
        for item in reports_by_url.values()
    ]
    if quarterly_only:
        reports = [
            report for report in reports if report.title.lower().startswith("cut through quarterly")
        ]
    if quarter is not None:
        reports = [report for report in reports if report.quarter == quarter]
    if year is not None:
        reports = [report for report in reports if report.year == year]
    reports.sort(key=lambda report: report.publication_date or "", reverse=True)
    return reports[:limit] if limit is not None else reports


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--insights-url", default=INSIGHTS_URL)
    parser.add_argument("--all", action="store_true", help="Include non-quarterly report cards")
    parser.add_argument("--quarter", type=int, choices=(1, 2, 3, 4))
    parser.add_argument("--year", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    parser.add_argument(
        "--http-fallback",
        action="store_true",
        help="Fetch /insights directly with httpx instead of Firecrawl.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    reports = discover_reports(
        insights_url=args.insights_url,
        quarterly_only=not args.all,
        quarter=args.quarter,
        year=args.year,
        limit=args.limit,
        use_firecrawl=not args.http_fallback,
    )
    payload = {"reports": [asdict(report) for report in reports]}
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        LOGGER.info("wrote %d reports to %s", len(reports), args.output)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
