#!/usr/bin/env python3
"""Dump verified companies to a local JSON file for offline inspection.

Used by the verification-prompt curation flow: an agent reads the dumped
JSON, decides groupings, and emits paste-ready prompts. Dump is read-only.

By default dumps every verified company. With `--since YYYY-MM-DD`, dumps
only the companies whose `profile_verified_at` is strictly older than the
given date OR null - useful for incremental re-verification cycles where
freshly-verified rows do not need to be re-asked.

Usage:
    op run --env-file=.env.local -- python scripts/dump_verified_companies.py
    op run --env-file=.env.local -- python scripts/dump_verified_companies.py --since 2026-01-30
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger("dump_verified_companies")
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "verification" / "companies_verified.json"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _row_verified_at(row: dict[str, Any]) -> datetime | None:
    value = row.get("profile_verified_at")
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def filter_since(rows: list[dict[str, Any]], cutoff: date) -> list[dict[str, Any]]:
    """Keep rows whose `profile_verified_at` is None or strictly older than `cutoff`.

    Cutoff is interpreted as midnight UTC on the given date.
    """
    cutoff_dt = datetime.combine(cutoff, datetime.min.time(), tzinfo=UTC)
    out: list[dict[str, Any]] = []
    for row in rows:
        verified_at = _row_verified_at(row)
        if verified_at is None or verified_at < cutoff_dt:
            out.append(row)
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        default=None,
        help=(
            "Only dump companies with profile_verified_at older than YYYY-MM-DD "
            "(or null). Default: dump all verified."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSON path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Read verified companies from Supabase, optionally filter, write JSON."""
    configure_logging()
    args = parse_args(argv)
    with supabase_db.connection() as conn:
        rows = supabase_db.list_companies(conn, statuses=("verified",))
    total = len(rows)
    if args.since is not None:
        rows = filter_since(rows, args.since)
        LOGGER.info(
            "filter --since %s: kept %d of %d (older than cutoff or never verified)",
            args.since.isoformat(),
            len(rows),
            total,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(rows, indent=2, default=_json_default, sort_keys=False),
        encoding="utf-8",
    )
    LOGGER.info("wrote %d verified companies to %s", len(rows), args.output)
    print(
        json.dumps(
            {
                "count": len(rows),
                "total_verified": total,
                "since": args.since.isoformat() if args.since else None,
                "path": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
