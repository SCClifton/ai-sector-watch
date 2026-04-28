#!/usr/bin/env python3
"""Audit live company profile data and prepare reviewed update artifacts.

This script is read-only against Supabase. It can optionally run the existing
Firecrawl enrichment path to collect public-source facts, then writes three
operator artifacts: Markdown summary, CSV findings, and proposed update JSON.

Usage:
    op run --account my.1password.com --env-file=.env.local -- python scripts/audit_company_profiles.py --limit 5 --dry-run
    op run --account my.1password.com --env-file=.env.local -- python scripts/audit_company_profiles.py --enrich --limit 5
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

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.extraction.claude_client import BudgetExceeded, ClaudeClient  # noqa: E402
from ai_sector_watch.extraction.firecrawl_client import (  # noqa: E402
    DEFAULT_CREDITS_PER_ENRICH,
    FirecrawlBudgetExceeded,
    FirecrawlClient,
    firecrawl_enrich,
)
from ai_sector_watch.extraction.schema import CompanyFacts  # noqa: E402
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger("audit_company_profiles")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "data-audits"
ALL_STATUSES = ("verified", "auto_discovered_pending_review", "rejected")
COMPARABLE_FACT_FIELDS = (
    "founded_year",
    "summary",
    "city",
    "country",
    "founders",
    "total_raised_usd",
    "total_raised_currency_raw",
    "total_raised_as_of",
    "total_raised_source_url",
    "valuation_usd",
    "valuation_currency_raw",
    "valuation_as_of",
    "valuation_source_url",
    "headcount_estimate",
    "headcount_min",
    "headcount_max",
    "headcount_as_of",
    "headcount_source_url",
)
MAX_REASONABLE_HEADCOUNT = 10_000


@dataclass
class AuditFinding:
    """One field-level audit finding."""

    row_id: str
    name: str
    current_status: str
    field: str
    current_value: str
    recommended_value: str
    finding: str
    confidence: str
    official_evidence_url: str
    independent_evidence_url: str
    notes: str
    recommended_action: str


@dataclass
class ProposedCompanyUpdate:
    """Reviewed-update payload for one company row."""

    id: str
    name: str
    discovery_status: str
    updates: dict[str, Any] = field(default_factory=dict)
    evidence_urls: list[str] = field(default_factory=list)


@dataclass
class AuditArtifacts:
    """Paths emitted by the audit run."""

    markdown_path: Path
    csv_path: Path
    json_path: Path


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list | tuple | set):
        return len(value) == 0
    return False


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")


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


def _normalise(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def _fact_to_updates(company: dict[str, Any], facts: CompanyFacts) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    headcount_estimate = facts.headcount_estimate
    headcount_min = facts.headcount_min
    headcount_max = facts.headcount_max
    if headcount_estimate is not None and headcount_estimate > MAX_REASONABLE_HEADCOUNT:
        headcount_estimate = None
    if headcount_min is not None and headcount_min > MAX_REASONABLE_HEADCOUNT:
        headcount_min = None
    if headcount_max is not None and headcount_max > MAX_REASONABLE_HEADCOUNT:
        headcount_max = None
    fact_values = {
        "founded_year": facts.founded_year,
        "summary": facts.description,
        "city": facts.city,
        "country": facts.country,
        "founders": facts.founders,
        "total_raised_usd": facts.total_raised_usd,
        "total_raised_currency_raw": facts.total_raised_currency_raw,
        "total_raised_as_of": facts.total_raised_as_of,
        "total_raised_source_url": facts.total_raised_source_url,
        "valuation_usd": facts.valuation_usd,
        "valuation_currency_raw": facts.valuation_currency_raw,
        "valuation_as_of": facts.valuation_as_of,
        "valuation_source_url": facts.valuation_source_url,
        "headcount_estimate": headcount_estimate,
        "headcount_min": headcount_min,
        "headcount_max": headcount_max,
        "headcount_as_of": facts.headcount_as_of,
        "headcount_source_url": facts.headcount_source_url,
    }
    for field_name, incoming in fact_values.items():
        if _is_empty(incoming):
            continue
        current = company.get(field_name)
        if _is_empty(current) or _normalise(current) != _normalise(incoming):
            updates[field_name] = incoming
    if facts.evidence_urls:
        updates["profile_sources"] = facts.evidence_urls
    if facts.confidence:
        updates["profile_confidence"] = facts.confidence
    if updates:
        updates["profile_verified_at"] = datetime.now(UTC)
    return updates


def _findings_for_update(
    company: dict[str, Any],
    facts: CompanyFacts,
    updates: dict[str, Any],
) -> list[AuditFinding]:
    evidence_urls = facts.evidence_urls
    official_url = evidence_urls[0] if evidence_urls else ""
    independent_url = evidence_urls[1] if len(evidence_urls) > 1 else ""
    findings: list[AuditFinding] = []
    for field_name in COMPARABLE_FACT_FIELDS:
        if field_name not in updates:
            continue
        findings.append(
            AuditFinding(
                row_id=str(company["id"]),
                name=str(company["name"]),
                current_status=str(company["discovery_status"]),
                field=field_name,
                current_value=_display(company.get(field_name)),
                recommended_value=_display(updates[field_name]),
                finding="public evidence suggests updating this field",
                confidence=f"{facts.confidence:.2f}",
                official_evidence_url=official_url,
                independent_evidence_url=independent_url,
                notes="Review before applying to live Supabase.",
                recommended_action="update_field",
            )
        )
    if not findings:
        findings.append(
            AuditFinding(
                row_id=str(company["id"]),
                name=str(company["name"]),
                current_status=str(company["discovery_status"]),
                field="profile",
                current_value="",
                recommended_value="",
                finding="no public-source difference detected",
                confidence=f"{facts.confidence:.2f}",
                official_evidence_url=official_url,
                independent_evidence_url=independent_url,
                notes="Keep row unchanged unless manual review finds an issue.",
                recommended_action="no_change",
            )
        )
    return findings


def _collaboration_notes(companies: list[dict[str, Any]]) -> list[str]:
    verified = [c for c in companies if c.get("discovery_status") == "verified"]
    infra = [c for c in verified if "ai_infrastructure" in (c.get("sector_tags") or [])]
    health = [c for c in verified if "vertical_healthcare" in (c.get("sector_tags") or [])]
    robotics = [
        c
        for c in verified
        if {"robotics_industrial", "robotics_autonomous_vehicles"}.intersection(
            c.get("sector_tags") or []
        )
    ]
    defence = [c for c in verified if "defence_and_dual_use" in (c.get("sector_tags") or [])]
    notes: list[str] = []
    if infra and health:
        notes.append(
            "Healthcare AI companies may need infrastructure partners for retrieval, observability, "
            "or secure deployment."
        )
    if robotics and defence:
        notes.append(
            "Robotics and defence companies have adjacent autonomy, navigation, and deployment needs."
        )
    if infra:
        notes.append(
            "AI infrastructure companies can support vertical companies with evaluation, search, "
            "data activation, and agent orchestration."
        )
    return notes


def _load_companies(
    *, statuses: tuple[str, ...], limit: int | None, offset: int
) -> list[dict[str, Any]]:
    with supabase_db.connection() as conn:
        rows = supabase_db.list_companies(conn, statuses=statuses)
    rows = rows[offset:]
    return rows[:limit] if limit is not None else rows


def _write_artifacts(
    *,
    output_dir: Path,
    run_date: date,
    artifact_suffix: str | None,
    companies: list[dict[str, Any]],
    findings: list[AuditFinding],
    proposed_updates: list[ProposedCompanyUpdate],
    dry_run: bool,
    enrich: bool,
    credits_used: int,
    llm_calls: int,
) -> AuditArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{artifact_suffix}" if artifact_suffix else ""
    stem = f"{run_date.isoformat()}-company-accuracy{suffix}"
    markdown_path = output_dir / f"{stem}.md"
    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = list(
            asdict(AuditFinding("", "", "", "", "", "", "", "", "", "", "", "")).keys()
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

    status_counts = {
        status: sum(1 for company in companies if company.get("discovery_status") == status)
        for status in ALL_STATUSES
    }
    lines = [
        f"# Company Accuracy Audit: {run_date.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Companies reviewed: {len(companies)}",
        f"- Verified: {status_counts['verified']}",
        f"- Pending review: {status_counts['auto_discovered_pending_review']}",
        f"- Rejected: {status_counts['rejected']}",
        f"- Findings: {len(findings)}",
        f"- Proposed company updates: {len(proposed_updates)}",
        f"- Firecrawl credits used: {credits_used}",
        f"- LLM calls: {llm_calls}",
        f"- Enrichment enabled: {enrich}",
        f"- Dry run: {dry_run}",
        "",
        "## Method",
        "",
        "Rows were read from live Supabase across all company statuses. When enrichment is enabled, "
        "the audit uses the existing Firecrawl multi-source path and Claude structured extraction. "
        "The JSON file is a proposed update set for review and is not applied by this script.",
        "",
        "## Collaboration Opportunities",
        "",
    ]
    notes = _collaboration_notes(companies)
    lines.extend(f"- {note}" for note in notes or ["No broad collaboration themes detected."])
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
    return AuditArtifacts(markdown_path=markdown_path, csv_path=csv_path, json_path=json_path)


def run_audit(
    *,
    limit: int | None,
    offset: int,
    dry_run: bool,
    enrich: bool,
    output_dir: Path,
    run_date: date,
    artifact_suffix: str | None,
) -> AuditArtifacts:
    """Run the read-only company audit and write artifacts."""
    companies = _load_companies(statuses=ALL_STATUSES, limit=limit, offset=offset)
    findings: list[AuditFinding] = []
    proposed_updates: list[ProposedCompanyUpdate] = []
    firecrawl_client = FirecrawlClient()
    llm_client = ClaudeClient()

    for index, company in enumerate(companies, start=1):
        name = str(company["name"])
        LOGGER.info("[%d/%d] auditing %s", index, len(companies), name)
        if dry_run or not enrich:
            findings.append(
                AuditFinding(
                    row_id=str(company["id"]),
                    name=name,
                    current_status=str(company["discovery_status"]),
                    field="profile",
                    current_value="",
                    recommended_value="",
                    finding="not enriched in this run",
                    confidence="0.00",
                    official_evidence_url=str(company.get("website") or ""),
                    independent_evidence_url="",
                    notes="Run with --enrich to collect public-source facts.",
                    recommended_action="manual_review",
                )
            )
            continue
        try:
            facts = firecrawl_enrich(
                firecrawl_client,
                llm_client,
                str(company.get("website") or ""),
                name=name,
            )
        except (BudgetExceeded, FirecrawlBudgetExceeded) as exc:
            LOGGER.warning("budget exhausted while auditing %s: %s", name, exc)
            break
        updates = _fact_to_updates(company, facts)
        findings.extend(_findings_for_update(company, facts, updates))
        if updates:
            proposed_updates.append(
                ProposedCompanyUpdate(
                    id=str(company["id"]),
                    name=name,
                    discovery_status=str(company["discovery_status"]),
                    updates=updates,
                    evidence_urls=facts.evidence_urls,
                )
            )

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
    estimated_credits = (args.limit or 0) * DEFAULT_CREDITS_PER_ENRICH
    if args.enrich and args.limit is None:
        LOGGER.error("--enrich requires --limit for operator cost control")
        return 2
    if args.enrich:
        LOGGER.info("estimated Firecrawl credits for this run: %d", estimated_credits)
    artifacts = run_audit(
        limit=args.limit,
        offset=args.offset,
        dry_run=args.dry_run,
        enrich=args.enrich,
        output_dir=args.output_dir,
        run_date=args.run_date,
        artifact_suffix=args.artifact_suffix,
    )
    print(json.dumps({k: str(v) for k, v in asdict(artifacts).items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
