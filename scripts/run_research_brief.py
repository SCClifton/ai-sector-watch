"""Fetch primary research sources and write a daily public brief run."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ai_sector_watch.research.briefs import (  # noqa: E402
    build_research_brief_run,
    default_research_sources,
    research_run_to_dict,
    write_research_run_json,
)
from ai_sector_watch.sources.base import RawItem  # noqa: E402
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--date",
        type=_parse_date,
        default=datetime.now(UTC).date(),
        help="Run date as YYYY-MM-DD. Defaults to today in UTC.",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=36,
        help="Lookback window in hours ending at the end of the run date.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum items fetched per source.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "research_briefs",
        help="Directory for local JSON fallback files.",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Do not write a local JSON fallback file.",
    )
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Upsert the run into Supabase. Requires SUPABASE_DB_URL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the structured run and skip JSON and database writes.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    window_end = datetime.combine(args.date + timedelta(days=1), time.min, tzinfo=UTC)
    window_start = window_end - timedelta(hours=args.hours)
    raw_items, source_errors = fetch_research_items(limit=args.limit)
    run = build_research_brief_run(
        raw_items=raw_items,
        run_date=args.date,
        window_start=window_start,
        window_end=window_end,
        source_errors=source_errors,
    )

    if args.dry_run:
        print(json.dumps(research_run_to_dict(run), indent=2, sort_keys=True))
        return 0

    if not args.no_json:
        path = write_research_run_json(run, args.output_dir)
        LOGGER.info("wrote research brief JSON: %s", path)

    if args.write_db:
        with supabase_db.connection() as conn:
            supabase_db.apply_schema(conn)
            supabase_db.upsert_research_brief_run(
                conn,
                run_id=run.id,
                run_date=args.date,
                window_start=window_start,
                window_end=window_end,
                title=run.title,
                summary=run.summary,
                sections=research_run_to_dict(run)["sections"],
                sources=run.sources,
                cost_usd=run.cost_usd,
                model=run.model,
                status=run.status,
            )
            conn.commit()
        LOGGER.info("upserted research brief run: %s", run.run_date)

    return 0


def fetch_research_items(*, limit: int) -> tuple[list[RawItem], list[str]]:
    """Fetch all configured research sources, skipping failures."""
    items: list[RawItem] = []
    errors: list[str] = []
    for source in default_research_sources():
        try:
            fetched = source.fetch(limit=limit)
            items.extend(fetched)
            LOGGER.info("source %s ok: %d items", source.slug, len(fetched))
        except Exception as exc:  # noqa: BLE001
            message = f"source {source.slug} failed: {type(exc).__name__}: {exc}"
            LOGGER.warning(message)
            errors.append(message)
    return items, errors


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


if __name__ == "__main__":
    raise SystemExit(main())
