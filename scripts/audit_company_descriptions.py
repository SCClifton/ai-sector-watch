#!/usr/bin/env python3
"""Audit verified company summaries used by the public app.

This script is read-only against Supabase. With enrichment enabled, it uses
the existing Firecrawl markdown path plus Claude structured extraction to
review public-facing company summaries. It writes review artifacts only:
CSV findings, JSON proposed updates, and a Markdown summary.

Usage:
    op run --env-file=.env.local -- python scripts/audit_company_descriptions.py --limit 5 --dry-run
    op run --env-file=.env.local -- python scripts/audit_company_descriptions.py --enrich --limit 5
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
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

LOGGER = logging.getLogger("audit_company_descriptions")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "data-audits"
HIGH_CONFIDENCE_THRESHOLD = 0.75
SUMMARY_SIMILARITY_THRESHOLD = 0.90
MAX_SUMMARY_WORDS = 80

ACTION_CONFIRMED = "confirmed"
ACTION_NEEDS_UPDATE = "needs_update"
ACTION_MISSING_SUMMARY = "missing_summary"
ACTION_MANUAL_REVIEW = "manual_review"
ACTION_POSSIBLE_REJECTION = "possible_rejection"

DESCRIPTION_SYSTEM_PROMPT = (
    "Review the public summary for this company from supplied source excerpts. "
    "Use only what the excerpts explicitly state. Return structured JSON matching the schema."
)

DESCRIPTION_USER_TEMPLATE = """\
Company: {name}
Current public summary: {current_summary}
Sector tags: {sector_tags}
Website: {website}

Write or confirm a public-facing company summary.

Rules:
- proposed_summary must be under 80 words, active voice, and contain no em dashes.
- Explain what the company does, who it serves, and why AI is core.
- Do not overstate AI usage if AI appears to be only a feature or is unclear.
- If evidence is weak, conflicting, noisy, or the company appears out of scope, leave proposed_summary null and explain why.
- is_ai_company is true only when the excerpts support AI as a core product or service.
- is_anz_relevant is true only when the excerpts support Australia or New Zealand headquarters, founding, or a meaningful operating base.
- Evidence URLs must come from the supplied source excerpts only.

Source excerpts:
{sources}
"""

_DASH_PATTERN = re.compile(r"\s*[—–]\s*")
_WORD_PATTERN = re.compile(r"\b[\w']+\b")
_NORMALISE_PATTERN = re.compile(r"[^a-z0-9 ]+")


class CompanyDescriptionFacts(BaseModel):
    """Structured public summary evidence from public sources."""

    proposed_summary: str | None = Field(
        None,
        description="Concise public-facing summary supported by the source excerpts.",
    )
    is_ai_company: bool | None = Field(
        None,
        description="Whether sources support AI as a core product or service.",
    )
    is_anz_relevant: bool | None = Field(
        None,
        description="Whether sources support Australia or New Zealand relevance.",
    )
    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence that the summary and scope signals are source supported.",
    )
    evidence_urls: list[str] = Field(
        default_factory=list,
        description="URLs from the supplied excerpts that support the summary.",
    )
    evidence_notes: str | None = Field(
        None,
        description="Short note explaining the summary evidence.",
    )
    conflict_reason: str | None = Field(
        None,
        description="Why evidence is uncertain or conflicting, if applicable.",
    )
    scope_concern: str | None = Field(
        None,
        description="Why the company may not belong on the map, if applicable.",
    )

    @field_validator("proposed_summary")
    @classmethod
    def _clean_proposed_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _clean_summary(value)
        return cleaned or None

    @classmethod
    def empty(cls) -> CompanyDescriptionFacts:
        """Return an empty low-confidence description result."""
        return cls(confidence=0.0)


@dataclass
class DescriptionAuditFinding:
    """One company-level summary audit finding."""

    company_id: str
    name: str
    current_summary: str
    proposed_summary: str
    action: str
    confidence: str
    evidence_urls: str
    notes: str


@dataclass
class ProposedDescriptionUpdate:
    """Reviewed summary update payload for one company row."""

    id: str
    name: str
    discovery_status: str
    action: str
    confidence: float
    updates: dict[str, Any] = field(default_factory=dict)
    evidence_urls: list[str] = field(default_factory=list)


@dataclass
class DescriptionAuditArtifacts:
    """Paths emitted by the description audit run."""

    markdown_path: Path
    csv_path: Path
    json_path: Path


class DescriptionAuditBudgetExceeded(RuntimeError):
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


def _clean_summary(value: str | None) -> str:
    if not value:
        return ""
    return _DASH_PATTERN.sub(" - ", " ".join(value.split())).strip()


def _word_count(value: str) -> int:
    return len(_WORD_PATTERN.findall(value))


def _summary_is_public_ready(value: str) -> bool:
    summary = value.strip()
    return (
        bool(summary)
        and "—" not in summary
        and "–" not in summary
        and _word_count(summary) <= MAX_SUMMARY_WORDS
    )


def _canonical_summary(value: str) -> str:
    lowered = " ".join(value.lower().split())
    cleaned = _NORMALISE_PATTERN.sub(" ", lowered)
    return " ".join(cleaned.split())


def _summary_similarity(left: str, right: str) -> float:
    left_key = _canonical_summary(left)
    right_key = _canonical_summary(right)
    if not left_key or not right_key:
        return 0.0
    return SequenceMatcher(None, left_key, right_key).ratio()


def _description_sources(documents: list[MarkdownDocument]) -> str:
    chunks: list[str] = []
    for index, doc in enumerate(documents, start=1):
        title = f"\nTitle: {doc.title}" if doc.title else ""
        markdown = doc.markdown[:MAX_MARKDOWN_CHARS_PER_SOURCE]
        chunks.append(f"[{index}] URL: {doc.url}{title}\nMarkdown:\n{markdown}")
    return "\n\n".join(chunks)


def _supported_evidence_urls(
    facts: CompanyDescriptionFacts,
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


def extract_description_facts(
    client: FirecrawlClient,
    llm_client: ClaudeClient,
    website: str | None,
    *,
    name: str,
    current_summary: str | None,
    sector_tags: list[str],
) -> CompanyDescriptionFacts:
    """Extract public summary evidence for one company."""
    if not website or not website.strip():
        return CompanyDescriptionFacts.empty()

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
        return CompanyDescriptionFacts.empty()

    response = llm_client.structured_call(
        system=DESCRIPTION_SYSTEM_PROMPT,
        prompt=DESCRIPTION_USER_TEMPLATE.format(
            name=name,
            current_summary=_display(current_summary),
            sector_tags=", ".join(sector_tags),
            website=root_url,
            sources=_description_sources(documents),
        ),
        schema_cls=CompanyDescriptionFacts,
        max_tokens=768,
    )
    parsed = response.parsed
    facts = (
        parsed
        if isinstance(parsed, CompanyDescriptionFacts)
        else CompanyDescriptionFacts.model_validate(parsed.model_dump())
    )
    return facts.model_copy(update={"evidence_urls": _supported_evidence_urls(facts, documents)})


def build_description_audit(
    company: dict[str, Any],
    facts: CompanyDescriptionFacts,
    *,
    enriched: bool,
) -> tuple[DescriptionAuditFinding, ProposedDescriptionUpdate | None]:
    """Compare current public summary with extracted evidence."""
    name = str(company["name"])
    current_summary = " ".join(str(company.get("summary") or "").split())
    proposed_summary = _clean_summary(facts.proposed_summary)
    has_current = bool(current_summary)
    has_proposed = bool(proposed_summary)
    high_confidence = facts.confidence >= HIGH_CONFIDENCE_THRESHOLD
    has_evidence = bool(facts.evidence_urls)

    notes: list[str] = []
    action = ACTION_MANUAL_REVIEW
    updates: dict[str, Any] = {}

    if facts.scope_concern:
        notes.append(facts.scope_concern)
    if facts.conflict_reason:
        notes.append(facts.conflict_reason)
    if facts.evidence_notes:
        notes.append(facts.evidence_notes)

    if not enriched:
        action = ACTION_MANUAL_REVIEW
        notes.append("Run with --enrich to collect public-source evidence.")
    elif high_confidence and (facts.is_ai_company is False or facts.is_anz_relevant is False):
        action = ACTION_POSSIBLE_REJECTION
        notes.append("Public evidence suggests this row may be out of scope.")
    elif not has_proposed or not has_evidence:
        action = ACTION_MANUAL_REVIEW
        notes.append("Evidence did not support a confident replacement summary.")
    elif not high_confidence:
        action = ACTION_MANUAL_REVIEW
        notes.append("Evidence confidence is below the replacement threshold.")
    elif not has_current:
        action = ACTION_MISSING_SUMMARY
    elif (
        _summary_is_public_ready(current_summary)
        and _summary_similarity(current_summary, proposed_summary) >= SUMMARY_SIMILARITY_THRESHOLD
    ):
        action = ACTION_CONFIRMED
    else:
        action = ACTION_NEEDS_UPDATE

    if action in {ACTION_NEEDS_UPDATE, ACTION_MISSING_SUMMARY}:
        updates["summary"] = proposed_summary
        updates["profile_sources"] = facts.evidence_urls
        updates["profile_confidence"] = facts.confidence
        updates["profile_verified_at"] = datetime.now(UTC)

    finding = DescriptionAuditFinding(
        company_id=str(company["id"]),
        name=name,
        current_summary=current_summary,
        proposed_summary=proposed_summary,
        action=action,
        confidence=f"{facts.confidence:.2f}",
        evidence_urls=", ".join(facts.evidence_urls),
        notes=" ".join(notes).strip(),
    )
    proposed_update = None
    if updates:
        proposed_update = ProposedDescriptionUpdate(
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
    findings: list[DescriptionAuditFinding],
    proposed_updates: list[ProposedDescriptionUpdate],
    dry_run: bool,
    enrich: bool,
    credits_used: int,
    llm_calls: int,
    llm_cost_usd: float,
) -> DescriptionAuditArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{artifact_suffix}" if artifact_suffix else ""
    stem = f"{run_date.isoformat()}-company-description-audit{suffix}"
    markdown_path = output_dir / f"{stem}.md"
    csv_path = output_dir / f"{stem}.csv"
    json_path = output_dir / f"{stem}.json"

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fieldnames = list(asdict(DescriptionAuditFinding("", "", "", "", "", "", "", "")).keys())
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
            ACTION_MISSING_SUMMARY,
            ACTION_MANUAL_REVIEW,
            ACTION_POSSIBLE_REJECTION,
        )
    }
    high_confidence_replacements = [
        finding
        for finding in findings
        if finding.action in {ACTION_NEEDS_UPDATE, ACTION_MISSING_SUMMARY}
        and float(finding.confidence or "0") >= HIGH_CONFIDENCE_THRESHOLD
    ]
    manual_review = [finding for finding in findings if finding.action == ACTION_MANUAL_REVIEW]
    possible_rejections = [
        finding for finding in findings if finding.action == ACTION_POSSIBLE_REJECTION
    ]

    lines = [
        f"# Company Description Audit: {run_date.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Companies reviewed: {len(companies)}",
        f"- Confirmed: {action_counts[ACTION_CONFIRMED]}",
        f"- Needs update: {action_counts[ACTION_NEEDS_UPDATE]}",
        f"- Missing summary: {action_counts[ACTION_MISSING_SUMMARY]}",
        f"- Manual review: {action_counts[ACTION_MANUAL_REVIEW]}",
        f"- Possible rejection: {action_counts[ACTION_POSSIBLE_REJECTION]}",
        f"- Proposed company updates: {len(proposed_updates)}",
        f"- Firecrawl credits used: {credits_used}",
        f"- LLM calls: {llm_calls}",
        f"- Estimated LLM cost USD: {llm_cost_usd:.4f}",
        f"- Enrichment enabled: {enrich}",
        f"- Dry run: {dry_run}",
        "",
        "## High-Confidence Replacements",
        "",
    ]
    lines.extend(
        f"- {finding.name}: {finding.action}, {finding.proposed_summary}"
        for finding in high_confidence_replacements[:25]
    )
    if not high_confidence_replacements:
        lines.append("- None.")
    lines.extend(["", "## Manual Review Rows", ""])
    lines.extend(
        f"- {finding.name}: {finding.notes or 'No confident source-backed replacement.'}"
        for finding in manual_review[:25]
    )
    if not manual_review:
        lines.append("- None.")
    lines.extend(["", "## Out-of-Scope Concerns", ""])
    lines.extend(
        f"- {finding.name}: {finding.notes or 'Review map eligibility.'}"
        for finding in possible_rejections[:25]
    )
    if not possible_rejections:
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
    return DescriptionAuditArtifacts(
        markdown_path=markdown_path,
        csv_path=csv_path,
        json_path=json_path,
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
) -> DescriptionAuditArtifacts:
    """Run the read-only company description audit and write artifacts."""
    companies = _load_companies(limit=limit, offset=offset)
    findings: list[DescriptionAuditFinding] = []
    proposed_updates: list[ProposedDescriptionUpdate] = []
    firecrawl_client: FirecrawlClient | None = None
    llm_client: ClaudeClient | None = None
    if enrich and not dry_run:
        cache_root = output_dir / ".cache" / "company-descriptions"
        firecrawl_client = FirecrawlClient(cache_dir=cache_root / "firecrawl")
        llm_client = ClaudeClient(cache_dir=cache_root / "claude")

    for index, company in enumerate(companies, start=1):
        name = str(company["name"])
        LOGGER.info("[%d/%d] auditing summary for %s", index, len(companies), name)
        if dry_run or not enrich:
            facts = CompanyDescriptionFacts.empty()
            finding, proposed_update = build_description_audit(company, facts, enriched=False)
            findings.append(finding)
            if proposed_update is not None:
                proposed_updates.append(proposed_update)
            continue
        try:
            if firecrawl_client is None or llm_client is None:
                raise RuntimeError("enrichment clients were not initialised")
            facts = extract_description_facts(
                firecrawl_client,
                llm_client,
                str(company.get("website") or ""),
                name=name,
                current_summary=str(company.get("summary") or ""),
                sector_tags=[str(tag) for tag in company.get("sector_tags") or []],
            )
        except (BudgetExceeded, FirecrawlBudgetExceeded) as exc:
            raise DescriptionAuditBudgetExceeded(
                f"budget exhausted while auditing {name}; audit artifacts would be incomplete"
            ) from exc
        finding, proposed_update = build_description_audit(company, facts, enriched=True)
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
        credits_used=firecrawl_client.stats.credits_used if firecrawl_client else 0,
        llm_calls=llm_client.stats.calls if llm_client else 0,
        llm_cost_usd=llm_client.stats.cost_usd if llm_client else 0.0,
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
    except DescriptionAuditBudgetExceeded as exc:
        LOGGER.error("%s", exc)
        return 1
    print(json.dumps({k: str(v) for k, v in asdict(artifacts).items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
