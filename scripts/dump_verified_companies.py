#!/usr/bin/env python3
"""Dump every verified company to a local JSON file for offline inspection.

Used by the verification-prompt curation flow: an agent reads the dumped
JSON, decides groupings, and emits paste-ready prompts. Dump is read-only.

Usage:
    op run --env-file=.env.local -- python scripts/dump_verified_companies.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime
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


def main() -> int:
    """Read all verified companies from Supabase, write to DEFAULT_OUTPUT_PATH."""
    configure_logging()
    with supabase_db.connection() as conn:
        rows = supabase_db.list_companies(conn, statuses=("verified",))
    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_PATH.write_text(
        json.dumps(rows, indent=2, default=_json_default, sort_keys=False),
        encoding="utf-8",
    )
    LOGGER.info("wrote %d verified companies to %s", len(rows), DEFAULT_OUTPUT_PATH)
    print(json.dumps({"count": len(rows), "path": str(DEFAULT_OUTPUT_PATH)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
