#!/usr/bin/env python3
"""Apply reviewed company profile updates to live Supabase.

The input is the JSON artifact emitted by `scripts/audit_company_profiles.py`.
By default this script validates and prints a dry-run summary. Live writes
require `--apply` and resolved 1Password environment values.

Usage:
    python scripts/apply_company_profile_updates.py docs/data-audits/2026-04-28-company-accuracy.json
    op run --account my.1password.com --env-file=.env.local -- python scripts/apply_company_profile_updates.py docs/data-audits/2026-04-28-company-accuracy.json --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger("apply_company_profile_updates")

ALLOWED_UPDATE_FIELDS = {
    "website",
    "country",
    "city",
    "lat",
    "lon",
    "sector_tags",
    "stage",
    "founded_year",
    "summary",
    "evidence_urls",
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
    "profile_confidence",
    "profile_sources",
    "profile_verified_at",
}


@dataclass
class ApplySummary:
    """Operator-facing summary for an apply run."""

    input_path: str
    apply: bool
    companies_seen: int = 0
    companies_updated: int = 0
    fields_updated: int = 0
    errors: list[str] = field(default_factory=list)


def _load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    companies = payload.get("companies")
    if not isinstance(companies, list):
        return ["payload must contain a companies list"]
    for index, company in enumerate(companies):
        if not isinstance(company, dict):
            errors.append(f"companies[{index}] must be an object")
            continue
        if not company.get("id"):
            errors.append(f"companies[{index}] missing id")
        updates = company.get("updates")
        if not isinstance(updates, dict):
            errors.append(f"companies[{index}] updates must be an object")
            continue
        unknown = set(updates) - ALLOWED_UPDATE_FIELDS
        if unknown:
            errors.append(f"companies[{index}] has unsupported fields: {sorted(unknown)}")
    return errors


def _op_env_is_resolved() -> bool:
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    return bool(db_url) and not db_url.startswith("op://")


def run_apply(*, input_path: Path, apply: bool) -> ApplySummary:
    """Validate and optionally apply reviewed company updates."""
    payload = _load_payload(input_path)
    summary = ApplySummary(input_path=str(input_path), apply=apply)
    validation_errors = _validate_payload(payload)
    if validation_errors:
        summary.errors.extend(validation_errors)
        return summary
    companies = payload["companies"]
    summary.companies_seen = len(companies)

    if apply and not _op_env_is_resolved():
        summary.errors.append(
            "live apply requires resolved SUPABASE_DB_URL; run via op run with .env.local"
        )
        return summary

    if not apply:
        for company in companies:
            summary.fields_updated += len(company["updates"])
        return summary

    with supabase_db.connection() as conn:
        supabase_db.apply_schema(conn)
        for company in companies:
            updates = dict(company["updates"])
            if updates and "profile_verified_at" not in updates:
                updates["profile_verified_at"] = datetime.now(UTC)
            if not updates:
                continue
            supabase_db.update_company_enrichment(
                conn,
                str(company["id"]),
                updates=updates,
                enriched_at=datetime.now(UTC),
            )
            summary.companies_updated += 1
            summary.fields_updated += len(updates)
        conn.commit()
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write reviewed updates to Supabase")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    summary = run_apply(input_path=args.input_path, apply=args.apply)
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    if summary.errors:
        for error in summary.errors:
            LOGGER.error(error)
        return 1
    if not args.apply:
        LOGGER.info("dry run only; rerun with --apply after review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
