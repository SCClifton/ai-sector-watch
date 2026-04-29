#!/usr/bin/env python3
"""Apply reviewed company rejections to live Supabase.

Reads a flags JSON in the shape produced by `parse_verification_responses.py`,
filters to entries with `verdict = 'flag_for_rejection'`, and sets
`discovery_status = 'rejected'` for each via the existing
`supabase_db.set_company_status` helper. Dry-run by default.

Usage:
    python scripts/apply_company_rejections.py data/verification/flags_<ts>.json
    op run --env-file=.env.local -- python scripts/apply_company_rejections.py data/verification/flags_<ts>.json --apply
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

LOGGER = logging.getLogger("apply_company_rejections")

REJECTION_VERDICT = "flag_for_rejection"
ADMIN_SOURCE = "verification_rejection_apply"


@dataclass
class RejectSummary:
    """Operator-facing summary for a rejection apply run."""

    input_path: str
    apply: bool
    candidates_seen: int = 0
    rejected: int = 0
    skipped_non_rejection: int = 0
    errors: list[str] = field(default_factory=list)
    rejected_ids: list[str] = field(default_factory=list)


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
    return errors


def _op_env_is_resolved() -> bool:
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    return bool(db_url) and not db_url.startswith("op://")


def select_rejection_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the entries with verdict == flag_for_rejection."""
    return [c for c in payload["companies"] if c.get("verdict") == REJECTION_VERDICT]


def run_apply(*, input_path: Path, apply: bool) -> RejectSummary:
    """Validate and optionally apply rejections."""
    payload = _load_payload(input_path)
    summary = RejectSummary(input_path=str(input_path), apply=apply)
    validation_errors = _validate_payload(payload)
    if validation_errors:
        summary.errors.extend(validation_errors)
        return summary

    all_companies = payload["companies"]
    candidates = select_rejection_candidates(payload)
    summary.candidates_seen = len(candidates)
    summary.skipped_non_rejection = len(all_companies) - len(candidates)

    if apply and not _op_env_is_resolved():
        summary.errors.append(
            "live apply requires resolved SUPABASE_DB_URL; run via op run with .env.local"
        )
        return summary

    if not apply:
        summary.rejected_ids = [str(c["id"]) for c in candidates]
        return summary

    with supabase_db.connection() as conn:
        supabase_db.apply_schema(conn)
        for company in candidates:
            company_id = str(company["id"])
            supabase_db.set_company_status(conn, company_id, "rejected")
            supabase_db.insert_ingest_event(
                conn,
                source_slug=ADMIN_SOURCE,
                kind="rejection_apply",
                payload={
                    "company_id": company_id,
                    "name": company.get("name"),
                    "notes": company.get("notes"),
                    "evidence_urls": company.get("evidence_urls", []),
                    "applied_at": datetime.now(UTC).isoformat(),
                },
            )
            summary.rejected += 1
            summary.rejected_ids.append(company_id)
        conn.commit()
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_path", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Set discovery_status='rejected' for each candidate. Default is dry-run.",
    )
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
