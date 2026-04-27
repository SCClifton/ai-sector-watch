#!/usr/bin/env python3
"""Run the weekly ingestion pipeline.

Usage:
    op run --account my.1password.com --env-file=.env.local -- python scripts/run_weekly_pipeline.py
    op run --account my.1password.com --env-file=.env.local -- python scripts/run_weekly_pipeline.py --dry-run
    op run --account my.1password.com --env-file=.env.local -- python scripts/run_weekly_pipeline.py --limit 5

Dry-run mode skips Supabase writes but still exercises source fetches and the
LLM extraction step (subject to the budget cap).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.pipeline.weekly import run_weekly_pipeline  # noqa: E402

LOGGER = logging.getLogger("run_weekly_pipeline")


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + extract but do not write to Supabase or the digest file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Items per source to process (default: 25)",
    )
    args = parser.parse_args()

    LOGGER.info("starting weekly pipeline (dry_run=%s)", args.dry_run)
    result = run_weekly_pipeline(
        items_per_source=args.limit,
        write_to_db=not args.dry_run,
    )

    summary = {
        "sources_attempted": result.sources_attempted,
        "sources_ok": result.sources_ok,
        "items_seen": result.items_seen,
        "items_new": result.items_new,
        "candidates_added": result.candidates_added,
        "cost_usd": round(result.cost_usd, 4),
        "digest_path": result.digest_path,
        "errors": result.errors,
    }
    print(json.dumps(summary, indent=2))
    return 0 if result.sources_ok or result.sources_attempted == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
