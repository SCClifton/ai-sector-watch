#!/usr/bin/env python3
"""Audit verified company HQ locations used by the public map.

This script is read-only against Supabase. With enrichment enabled, it uses
the existing Firecrawl markdown path plus Claude structured extraction to
verify the HQ city and country that drive map marker placement. It writes
review artifacts only: CSV findings, JSON proposed updates, and a Markdown
summary.

Usage:
    op run --env-file=.env.local -- python scripts/audit_company_locations.py --limit 5 --dry-run
    op run --env-file=.env.local -- python scripts/audit_company_locations.py --enrich --limit 5
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.discovery.geocoder import geocode_city, normalise_city  # noqa: E402
from ai_sector_watch.extraction.claude_client import BudgetExceeded, ClaudeClient  # noqa: E402
from ai_sector_watch.extraction.firecrawl_client import (  # noqa: E402
    DEFAULT_CREDITS_PER_ENRICH,
    MAX_EXTRA_COMPANY_PAGES_FOR_ENRICH,
    MAX_MARKDOWN_CHARS_PER_SOURCE,
    MAX_NEWS_RESULTS_FOR_ENRICH,
    FirecrawlBudgetExceeded,
    FirecrawlClient,
    MarkdownDocument,
    _dedupe_urls,
    _normalise_url,
)
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger("audit_company_locations")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "data-audits"
HIGH_CONFIDENCE_THRESHOLD = 0.75
COORD_TOLERANCE = 0.000001

LOCATION_SYSTEM_PROMPT = (
    "Extract the company's headquarters location from the supplied source excerpts. "
    "Use only what the excerpts explicitly state. Prefer the operating HQ or company "
    "headquarters over registered offices, mailing addresses, office lists, employee "
    "locations, or founder locations. Return only structured JSON matching the schema."
)

LOCATION_USER_TEMPLATE = """\
Company: {name}

Find the headquarters city and country for this company.

Rules:
- hq_city is the city of the operating headquarters, not a registered office unless the source says that is also the headquarters.
- hq_country is an ISO-like country code such as AU, NZ, US, GB, CA.
- If sources conflict, use null for uncertain fields and explain the conflict.
- Evidence URLs must come from the supplied source excerpts only.

Source excerpts:
{sources}
"""

ACTION_CONFIRMED = "confirmed"
ACTION_MANUAL_REVIEW = "manual_review"
ACTION_MISSING_LOCATION = "missing_location"
ACTION_NEEDS_UPDATE = "needs_update"
ACTION_UNSUPPORTED_CITY = "unsupported_city"


class CompanyLocationFacts(BaseModel):
    """Structured HQ location evidence from public sources."""

    hq_city: str | None = Field(None, description="Operating headquarters city if stated.")
    hq_country: str | None = Field(
        None,
        description="Operating headquarters country code, for example AU, NZ, US, GB, CA.",
    )
    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence that the HQ city and country are supported by the excerpts.",
    )
    evidence_urls: list[str] = Field(
        default_factory=list,
        description="URLs from the supplied excerpts that support the extracted location.",
    )
    evidence_notes: str | None = Field(
        None,
        description="Short note explaining the source evidence.",
    )
    conflict_reason: str | None = Field(
        None,
        description="Why the location is uncertain or conflicting, if applicable.",
    )

    @classmethod
    def empty(cls) -> CompanyLocationFacts:
        """Return an empty low-confidence location result."""
        return cls(confidence=0.0)


@dataclass
class LocationAuditFinding:
    """One company-level HQ location audit finding."""

    row_id: str
    name: str
    website: str
    current_city: str
    current_country: str
    current_lat: str
    current_lon: str
    recommended_city: str
    recommended_country: str
    proposed_lat: str
    proposed_lon: str
    action: str
    confidence: str
    evidence_urls: str
    evidence_notes: str
    conflict_reason: str


@dataclass
class ProposedLocationUpdate:
    """Reviewed location update payload for one company row."""

    id: str
    name: str
    discovery_status: str
    action: str
    confidence: float
    updates: dict[str, Any] = field(default_factory=dict)
    evidence_urls: list[str] = field(default_factory=list)


@dataclass
class LocationAuditArtifacts:
    """Paths emitted by the location audit run."""

    markdown_path: Path
    csv_path: Path
    json_path: Path


class LocationAuditBudgetExceeded(RuntimeError):
    """Raised when live enrichment cannot finish within configured budgets."""


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return ", ".join(str(v) for v in value)
    return str(value)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list | tuple | set):
        return len(value) == 0
    return False


def _normalise_country(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    key = " ".join(value.strip().upper().replace(".", "").split())
    aliases = {
        "AU": "AU",
        "AUS": "AU",
        "AUSTRALIA": "AU",
        "NZ": "NZ",
        "NZL": "NZ",
        "NEW ZEALAND": "NZ",
        "AOTEAROA NEW ZEALAND": "NZ",
        "US": "US",
        "USA": "US",
        "UNITED STATES": "US",
        "UNITED STATES OF AMERICA": "US",
        "GB": "GB",
        "UK": "GB",
        "UNITED KINGDOM": "GB",
    }
    return aliases.get(key, key)


def _coords_match(
    *,
    current_lat: Any,
    current_lon: Any,
    proposed_lat: float | None,
    proposed_lon: float | None,
) -> bool:
    if proposed_lat is None or proposed_lon is None:
        return False
    if current_lat is None or current_lon is None:
        return False
    try:
        lat = float(current_lat)
        lon = float(current_lon)
    except (TypeError, ValueError):
        return False
    return abs(lat - proposed_lat) <= COORD_TOLERANCE and abs(lon - proposed_lon) <= COORD_TOLERANCE


def _location_sources(documents: list[MarkdownDocument]) -> str:
    chunks: list[str] = []
    for index, doc in enumerate(documents, start=1):
        title = f"\nTitle: {doc.title}" if doc.title else ""
        markdown = doc.markdown[:MAX_MARKDOWN_CHARS_PER_SOURCE]
        chunks.append(f"[{index}] URL: {doc.url}{title}\nMarkdown:\n{markdown}")
    return "\n\n".join(chunks)


def _supported_evidence_urls(
    facts: CompanyLocationFacts,
    documents: list[MarkdownDocument],
) -> list[str]:
    available_ordered = _dedupe_urls(
        [_normalise_url(doc.url) for doc in documents if doc.markdown.strip()]
    )
    available = set(available_ordered)
    selected = [
        _normalise_url(url) for url in facts.evidence_urls if _normalise_url(url) in available
    ]
    return _dedupe_urls(selected or available_ordered)


def extract_location_facts(
    client: FirecrawlClient,
    llm_client: ClaudeClient,
    website: str | None,
    *,
    name: str,
) -> CompanyLocationFacts:
    """Extract HQ city/country evidence for one company."""
    if not website or not website.strip():
        return CompanyLocationFacts.empty()

    root_url = _normalise_url(website)
    client._ensure_budget(DEFAULT_CREDITS_PER_ENRICH)

    homepage = client._safe_scrape_markdown(root_url)
    try:
        company_pages = client._find_company_pages_unmetered(root_url)[
            :MAX_EXTRA_COMPANY_PAGES_FOR_ENRICH
        ]
    except Exception as exc:  # noqa: BLE001
        client.stats.failures.append(f"{root_url}: map: {type(exc).__name__}: {exc}")
        LOGGER.warning("firecrawl map failed for %s: %s", root_url, exc)
        company_pages = []

    documents: list[MarkdownDocument] = [homepage] if homepage is not None else []
    for page_url in company_pages:
        doc = client._safe_scrape_markdown(page_url)
        if doc is not None:
            documents.append(doc)

    try:
        documents.extend(
            client._fetch_company_news_unmetered(name=name, limit=MAX_NEWS_RESULTS_FOR_ENRICH)
        )
    except Exception as exc:  # noqa: BLE001
        client.stats.failures.append(f"{name}: search: {type(exc).__name__}: {exc}")
        LOGGER.warning("firecrawl search failed for %s: %s", name, exc)

    client._record_firecrawl_spend(credits=DEFAULT_CREDITS_PER_ENRICH)

    if not documents:
        return CompanyLocationFacts.empty()

    response = llm_client.structured_call(
        system=LOCATION_SYSTEM_PROMPT,
        prompt=LOCATION_USER_TEMPLATE.format(
            name=name,
            sources=_location_sources(documents),
        ),
        schema_cls=CompanyLocationFacts,
        max_tokens=512,
    )
    parsed = response.parsed
    facts = (
        parsed
        if isinstance(parsed, CompanyLocationFacts)
        else CompanyLocationFacts.model_validate(parsed.model_dump())
    )
    city = normalise_city(facts.hq_city)
    country = _normalise_country(facts.hq_country)
    return facts.model_copy(
        update={
            "hq_city": city,
            "hq_country": country,
            "evidence_urls": _supported_evidence_urls(facts, documents),
        }
    )


def build_location_audit(
    company: dict[str, Any],
    facts: CompanyLocationFacts,
    *,
    enriched: bool,
) -> tuple[LocationAuditFinding, ProposedLocationUpdate | None]:
    """Compare current map location with extracted HQ evidence."""
    name = str(company["name"])
    current_city = normalise_city(str(company.get("city") or "")) if company.get("city") else None
    current_country = _normalise_country(str(company.get("country") or ""))
    recommended_city = normalise_city(facts.hq_city)
    recommended_country = _normalise_country(facts.hq_country)
    has_current_location = not (
        _is_empty(current_city)
        or _is_empty(current_country)
        or _is_empty(company.get("lat"))
        or _is_empty(company.get("lon"))
    )
    has_recommendation = not _is_empty(recommended_city) and not _is_empty(recommended_country)
    high_confidence = facts.confidence >= HIGH_CONFIDENCE_THRESHOLD
    proposed_geo = geocode_city(recommended_city, jitter_seed=name) if recommended_city else None
    proposed_lat = proposed_geo.lat if proposed_geo else None
    proposed_lon = proposed_geo.lon if proposed_geo else None

    action = ACTION_MANUAL_REVIEW
    updates: dict[str, Any] = {}

    if not enriched or not has_recommendation:
        action = ACTION_MISSING_LOCATION if not has_current_location else ACTION_MANUAL_REVIEW
    elif proposed_geo is None:
        action = ACTION_UNSUPPORTED_CITY
    elif not has_current_location:
        action = ACTION_MISSING_LOCATION
    else:
        city_matches = current_city == recommended_city
        country_matches = current_country == recommended_country
        coords_match = _coords_match(
            current_lat=company.get("lat"),
            current_lon=company.get("lon"),
            proposed_lat=proposed_lat,
            proposed_lon=proposed_lon,
        )
        if city_matches and country_matches and coords_match:
            action = ACTION_CONFIRMED
        elif high_confidence:
            action = ACTION_NEEDS_UPDATE
        else:
            action = ACTION_MANUAL_REVIEW

    if action in {ACTION_MISSING_LOCATION, ACTION_NEEDS_UPDATE} and high_confidence:
        if recommended_city:
            updates["city"] = recommended_city
        if recommended_country:
            updates["country"] = recommended_country
        if proposed_geo is not None:
            updates["lat"] = proposed_geo.lat
            updates["lon"] = proposed_geo.lon
        if facts.evidence_urls:
            updates["profile_sources"] = facts.evidence_urls
        if facts.confidence:
            updates["profile_confidence"] = facts.confidence

    finding = LocationAuditFinding(
        row_id=str(company["id"]),
        name=name,
        website=_display(company.get("website")),
        current_city=_display(current_city),
        current_country=_display(current_country),
        current_lat=_display(company.get("lat")),
        current_lon=_display(company.get("lon")),
        recommended_city=_display(recommended_city),
        recommended_country=_display(recommended_country),
        proposed_lat=_display(proposed_lat),
        proposed_lon=_display(proposed_lon),
        action=action,
        confidence=f"{facts.confidence:.2f}",
        evidence_urls=", ".join(facts.evidence_urls),
        evidence_notes=_display(facts.evidence_notes),
        conflict_reason=_display(facts.conflict_reason),
    )
    proposed_update = None
    if updates:
        proposed_update = ProposedLocationUpdate(
            id=str(company["id"]),
            name=name,
            discovery_status=str(company.get("discovery_status") or ""),
            action=action,
            confidence=facts.confidence,
            updates=updates,
            evidence_urls=facts.evidence_urls,
        )
    return finding, proposed_update


def _load_companies(*, limit: int | None, offset: int) -> list[dict[str, Any]]:
    with supabase_db.connection() as conn:
        rows = supabase_db.list_companies(conn, statuses=("verified",))
    rows = rows[offset:]
    return rows[:limit] if limit is not None else rows


def _write_artifacts(
    *,
    output_dir: Path,
    run_date: date,
    artifact_suffix: str | None,
    companies: list[dict[str, Any]],
    findings: list[LocationAuditFinding],
    proposed_updates: list[ProposedLocationUpdate],
    dry_run: bool,
    enrich: bool,
    credits_used: int,
    llm_calls: int,
) -> LocationAuditArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{artifact_suffix}" if artifact_suffix else ""
    stem = f"{run_date.isoformat()}-company-location-audit{suffix}"
    markdown_path = output_dir / f"{stem}.md"
    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = list(
            asdict(
                LocationAuditFinding(
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                )
            ).keys()
        )
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for finding in findings:
            writer.writerow(asdict(finding))

    payload = {
        "generated_at": datetime.now(UTC),
        "dry_run": dry_run,
        "enrich": enrich,
        "company_count": len(companies),
        "proposed_update_count": len(proposed_updates),
        "companies": [asdict(update) for update in proposed_updates],
    }
    json_path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")

    action_counts = {
        action: sum(1 for finding in findings if finding.action == action)
        for action in (
            ACTION_CONFIRMED,
            ACTION_NEEDS_UPDATE,
            ACTION_MISSING_LOCATION,
            ACTION_UNSUPPORTED_CITY,
            ACTION_MANUAL_REVIEW,
        )
    }
    high_confidence_mismatches = [
        finding
        for finding in findings
        if finding.action == ACTION_NEEDS_UPDATE
        and float(finding.confidence or "0") >= HIGH_CONFIDENCE_THRESHOLD
    ]
    missing = [finding for finding in findings if finding.action == ACTION_MISSING_LOCATION]
    unsupported = [finding for finding in findings if finding.action == ACTION_UNSUPPORTED_CITY]

    lines = [
        f"# Company Location Audit: {run_date.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Companies reviewed: {len(companies)}",
        f"- Confirmed: {action_counts[ACTION_CONFIRMED]}",
        f"- Needs update: {action_counts[ACTION_NEEDS_UPDATE]}",
        f"- Missing location: {action_counts[ACTION_MISSING_LOCATION]}",
        f"- Unsupported city: {action_counts[ACTION_UNSUPPORTED_CITY]}",
        f"- Manual review: {action_counts[ACTION_MANUAL_REVIEW]}",
        f"- Proposed company updates: {len(proposed_updates)}",
        f"- Firecrawl credits used: {credits_used}",
        f"- LLM calls: {llm_calls}",
        f"- Enrichment enabled: {enrich}",
        f"- Dry run: {dry_run}",
        "",
        "## High-confidence Mismatches",
        "",
    ]
    lines.extend(
        f"- {finding.name}: {finding.current_city}, {finding.current_country} -> "
        f"{finding.recommended_city}, {finding.recommended_country}"
        for finding in high_confidence_mismatches[:25]
    )
    if not high_confidence_mismatches:
        lines.append("- None.")
    lines.extend(["", "## Missing or Unsupported", ""])
    for finding in [*missing, *unsupported][:25]:
        lines.append(f"- {finding.name}: {finding.action}")
    if not missing and not unsupported:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- CSV findings: `{csv_path.name}`",
            f"- Proposed updates: `{json_path.name}`",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return LocationAuditArtifacts(
        markdown_path=markdown_path, csv_path=csv_path, json_path=json_path
    )


def run_audit(
    *,
    limit: int | None,
    offset: int,
    dry_run: bool,
    enrich: bool,
    output_dir: Path,
    run_date: date,
    artifact_suffix: str | None,
) -> LocationAuditArtifacts:
    """Run the read-only company location audit and write artifacts."""
    companies = _load_companies(limit=limit, offset=offset)
    findings: list[LocationAuditFinding] = []
    proposed_updates: list[ProposedLocationUpdate] = []
    firecrawl_client = FirecrawlClient()
    llm_client = ClaudeClient()

    for index, company in enumerate(companies, start=1):
        name = str(company["name"])
        LOGGER.info("[%d/%d] auditing location for %s", index, len(companies), name)
        if dry_run or not enrich:
            facts = CompanyLocationFacts.empty()
            finding, proposed_update = build_location_audit(company, facts, enriched=False)
            findings.append(finding)
            if proposed_update is not None:
                proposed_updates.append(proposed_update)
            continue
        try:
            facts = extract_location_facts(
                firecrawl_client,
                llm_client,
                str(company.get("website") or ""),
                name=name,
            )
        except (BudgetExceeded, FirecrawlBudgetExceeded) as exc:
            raise LocationAuditBudgetExceeded(
                f"budget exhausted while auditing {name}; audit artifacts would be incomplete"
            ) from exc
        finding, proposed_update = build_location_audit(company, facts, enriched=True)
        findings.append(finding)
        if proposed_update is not None:
            proposed_updates.append(proposed_update)

    return _write_artifacts(
        output_dir=output_dir,
        run_date=run_date,
        artifact_suffix=artifact_suffix,
        companies=companies,
        findings=findings,
        proposed_updates=proposed_updates,
        dry_run=dry_run,
        enrich=enrich,
        credits_used=firecrawl_client.stats.credits_used,
        llm_calls=llm_client.stats.calls,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--enrich", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--artifact-suffix",
        default=None,
        help="Optional suffix for batch artifacts, for example batch-02.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    configure_logging()
    args = parse_args(argv)
    if args.limit is not None and args.limit < 1:
        LOGGER.error("--limit must be positive")
        return 2
    if args.offset < 0:
        LOGGER.error("--offset must be zero or greater")
        return 2
    if args.enrich and args.dry_run:
        LOGGER.error("--enrich and --dry-run cannot be combined")
        return 2
    if args.enrich and args.limit is None:
        LOGGER.error("--enrich requires --limit for operator cost control")
        return 2
    if args.enrich:
        LOGGER.info(
            "estimated Firecrawl credits for this run: %d",
            args.limit * DEFAULT_CREDITS_PER_ENRICH,
        )
    try:
        artifacts = run_audit(
            limit=args.limit,
            offset=args.offset,
            dry_run=args.dry_run,
            enrich=args.enrich,
            output_dir=args.output_dir,
            run_date=args.run_date,
            artifact_suffix=args.artifact_suffix,
        )
    except LocationAuditBudgetExceeded as exc:
        LOGGER.error("%s", exc)
        return 1
    print(json.dumps({k: str(v) for k, v in asdict(artifacts).items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
