#!/usr/bin/env python3
"""Apply reviewed Cut Through import artifacts to live Supabase.

The input is the JSON artifact emitted by
`scripts/extract_cut_through_report.py`. Dry-run mode validates and summarizes.
Live writes require `--apply` and resolved secret-manager environment values.

Usage:
    python scripts/apply_cut_through_import.py docs/data-audits/2026-04-29-cut-through-import.json
    op run --env-file=.env.local -- python scripts/apply_cut_through_import.py docs/data-audits/2026-04-29-cut-through-import.json --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger("apply_cut_through_import")
SCHEMA_VERSION = "cut_through_import.v1"
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "docs" / "data-audits" / "snapshots"
VALID_STAGES = {"pre_seed", "seed", "series_a", "series_b_plus", "mature"}
FUNDING_ACTIONS = {"needs_review", "upsert", "skip"}
COMPANY_ACTIONS = {
    "needs_review",
    "insert_pending",
    "update_verified_stage",
    "update_verified_fields",
    "skip",
}
COMPANY_FIELDS = {
    "reviewed_action",
    "company_name",
    "country",
    "website",
    "city",
    "sector_tags",
    "stage",
    "founded_year",
    "summary",
    "evidence_urls",
    "discovery_source",
    "provenance",
    "confidence",
    "notes",
}
FUNDING_FIELDS = {
    "reviewed_action",
    "company_name",
    "country",
    "is_ai_related",
    "announced_on",
    "date_precision",
    "stage",
    "amount_usd",
    "currency_raw",
    "lead_investor",
    "investors",
    "source_url",
    "provenance",
    "confidence",
    "notes",
}


@dataclass
class ApplySummary:
    """Operator-facing summary for an apply run."""

    input_path: str
    apply: bool
    funding_seen: int = 0
    funding_upserted: int = 0
    companies_seen: int = 0
    companies_inserted_pending: int = 0
    companies_stage_updated: int = 0
    companies_verified_updated: int = 0
    snapshot_path: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedAction:
    """A reviewed row plus its resolved DB company, if any."""

    row: dict[str, Any]
    company: dict[str, Any] | None


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")


def _load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _currency_is_explicit_usd(currency_raw: str | None) -> bool:
    if not currency_raw:
        return False
    raw = currency_raw.upper().replace(" ", "")
    return "USD" in raw or "US$" in raw or raw.startswith("US$")


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"invalid date value {value!r}")


def _parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal value {value!r}") from exc


def _parse_founded_year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        founded_year = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid founded_year value {value!r}") from exc
    current_year = datetime.now(UTC).year
    if founded_year < 1900 or founded_year > current_year:
        raise ValueError(f"founded_year must be between 1900 and {current_year}")
    return founded_year


def _validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"payload schema_version must be {SCHEMA_VERSION}")
    funding_events = payload.get("funding_events")
    company_candidates = payload.get("company_candidates")
    if not isinstance(funding_events, list):
        errors.append("payload must contain a funding_events list")
        funding_events = []
    if not isinstance(company_candidates, list):
        errors.append("payload must contain a company_candidates list")
        company_candidates = []

    for index, row in enumerate(funding_events):
        if not isinstance(row, dict):
            errors.append(f"funding_events[{index}] must be an object")
            continue
        unknown = set(row) - FUNDING_FIELDS
        if unknown:
            errors.append(f"funding_events[{index}] has unsupported fields: {sorted(unknown)}")
        action = row.get("reviewed_action")
        if action not in FUNDING_ACTIONS:
            errors.append(
                f"funding_events[{index}] reviewed_action must be one of {sorted(FUNDING_ACTIONS)}"
            )
        if not row.get("company_name"):
            errors.append(f"funding_events[{index}] missing company_name")
        if row.get("stage") and row["stage"] not in VALID_STAGES:
            errors.append(f"funding_events[{index}] has invalid stage {row['stage']!r}")
        if row.get("source_url") and not _is_url(row["source_url"]):
            errors.append(f"funding_events[{index}] source_url must be a URL")
        if row.get("amount_usd") not in (None, "") and not _currency_is_explicit_usd(
            row.get("currency_raw")
        ):
            errors.append(
                f"funding_events[{index}] amount_usd is allowed only when currency_raw is explicit USD"
            )
        try:
            _parse_date(row.get("announced_on"))
            _parse_decimal(row.get("amount_usd"))
        except ValueError as exc:
            errors.append(f"funding_events[{index}] {exc}")

    for index, row in enumerate(company_candidates):
        if not isinstance(row, dict):
            errors.append(f"company_candidates[{index}] must be an object")
            continue
        unknown = set(row) - COMPANY_FIELDS
        if unknown:
            errors.append(f"company_candidates[{index}] has unsupported fields: {sorted(unknown)}")
        action = row.get("reviewed_action")
        if action not in COMPANY_ACTIONS:
            errors.append(
                f"company_candidates[{index}] reviewed_action must be one of {sorted(COMPANY_ACTIONS)}"
            )
        if not row.get("company_name"):
            errors.append(f"company_candidates[{index}] missing company_name")
        if row.get("stage") and row["stage"] not in VALID_STAGES:
            errors.append(f"company_candidates[{index}] has invalid stage {row['stage']!r}")
        try:
            _parse_founded_year(row.get("founded_year"))
        except ValueError as exc:
            errors.append(f"company_candidates[{index}] {exc}")
        evidence_urls = row.get("evidence_urls") or []
        if not isinstance(evidence_urls, list) or not all(_is_url(url) for url in evidence_urls):
            errors.append(f"company_candidates[{index}] evidence_urls must contain URLs only")
        if action == "insert_pending" and row.get("country") not in {"AU", "NZ"}:
            errors.append(f"company_candidates[{index}] insert_pending requires country AU or NZ")
        if action == "update_verified_stage" and not row.get("stage"):
            errors.append(f"company_candidates[{index}] update_verified_stage requires stage")
        if (
            action == "update_verified_fields"
            and not row.get("stage")
            and not row.get("founded_year")
        ):
            errors.append(
                f"company_candidates[{index}] update_verified_fields requires stage or founded_year"
            )
    return errors


def _op_env_is_resolved() -> bool:
    db_url = os.environ.get("SUPABASE_DB_URL", "")
    return bool(db_url) and not db_url.startswith("op://")


def _company_key(row: dict[str, Any]) -> tuple[str, str | None]:
    return str(row["company_name"]).strip(), row.get("country")


def _matching_insert_candidate(
    funding_row: dict[str, Any],
    company_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    target_name, target_country = _company_key(funding_row)
    for company in company_rows:
        if company.get("reviewed_action") != "insert_pending":
            continue
        name, country = _company_key(company)
        if supabase_db.normalise_name(name) == supabase_db.normalise_name(target_name) and (
            country or ""
        ) == (target_country or ""):
            return company
    return None


def _resolve_company(conn: Any, row: dict[str, Any]) -> dict[str, Any] | None:
    name, country = _company_key(row)
    return supabase_db.get_company_by_name(conn, name, country)


def _validate_against_db(
    conn: Any,
    *,
    funding_rows: list[dict[str, Any]],
    company_rows: list[dict[str, Any]],
) -> tuple[list[ResolvedAction], list[ResolvedAction], list[str]]:
    errors: list[str] = []
    resolved_companies: list[ResolvedAction] = []
    resolved_funding: list[ResolvedAction] = []

    for row in company_rows:
        if row.get("reviewed_action") not in {
            "insert_pending",
            "update_verified_stage",
            "update_verified_fields",
        }:
            continue
        company = _resolve_company(conn, row)
        resolved_companies.append(ResolvedAction(row=row, company=company))
        if row["reviewed_action"] == "insert_pending" and company is not None:
            errors.append(
                f"{row['company_name']}: insert_pending requested but company already exists"
            )
        if row["reviewed_action"] in {"update_verified_stage", "update_verified_fields"}:
            if company is None:
                errors.append(
                    f"{row['company_name']}: {row['reviewed_action']} has no matching company"
                )
            elif company.get("discovery_status") != "verified":
                errors.append(
                    f"{row['company_name']}: verified updates are allowed only for verified companies"
                )

    for row in funding_rows:
        if row.get("reviewed_action") != "upsert":
            continue
        company = _resolve_company(conn, row)
        if company is None and _matching_insert_candidate(row, company_rows) is None:
            errors.append(f"{row['company_name']}: funding upsert has no matching company")
        resolved_funding.append(ResolvedAction(row=row, company=company))
    return resolved_companies, resolved_funding, errors


def _funding_snapshot_rows(
    conn: Any, resolved_funding: list[ResolvedAction]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for action in resolved_funding:
            if action.company is None:
                continue
            cur.execute(
                """
                SELECT *
                FROM funding_events
                WHERE company_id = %s
                  AND announced_on IS NOT DISTINCT FROM %s
                  AND stage IS NOT DISTINCT FROM %s
                """,
                (
                    action.company["id"],
                    _parse_date(action.row.get("announced_on")),
                    action.row.get("stage"),
                ),
            )
            rows.extend(list(cur.fetchall()))
    return rows


def _write_snapshot(
    *,
    conn: Any,
    input_path: Path,
    snapshot_dir: Path,
    resolved_companies: list[ResolvedAction],
    resolved_funding: list[ResolvedAction],
) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = snapshot_dir / f"{timestamp}-cut-through-import-snapshot.json"
    company_rows = [
        action.company for action in resolved_companies if action.company is not None
    ] + [action.company for action in resolved_funding if action.company is not None]
    deduped_companies: dict[str, dict[str, Any]] = {
        str(company["id"]): company for company in company_rows
    }
    payload = {
        "generated_at": datetime.now(UTC),
        "input_path": str(input_path),
        "companies": list(deduped_companies.values()),
        "funding_events": _funding_snapshot_rows(conn, resolved_funding),
        "missing_companies": [
            action.row["company_name"]
            for action in [*resolved_companies, *resolved_funding]
            if action.company is None
        ],
    }
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    return path


def _insert_pending_company(conn: Any, row: dict[str, Any]) -> str:
    return supabase_db.upsert_company(
        conn,
        name=str(row["company_name"]),
        country=row.get("country"),
        city=row.get("city"),
        website=row.get("website"),
        sector_tags=row.get("sector_tags") or [],
        stage=row.get("stage"),
        founded_year=_parse_founded_year(row.get("founded_year")),
        summary=row.get("summary"),
        evidence_urls=row.get("evidence_urls") or [],
        discovery_status="auto_discovered_pending_review",
        discovery_source=row.get("discovery_source") or "cut_through_report",
    )


def _update_verified_company_fields(
    conn: Any, row: dict[str, Any], company: dict[str, Any]
) -> None:
    updates: dict[str, Any] = {}
    if row.get("stage"):
        updates["stage"] = row["stage"]
    founded_year = _parse_founded_year(row.get("founded_year"))
    if row["reviewed_action"] == "update_verified_fields" and founded_year is not None:
        updates["founded_year"] = founded_year
    if not updates:
        return
    supabase_db.update_company_enrichment(
        conn,
        str(company["id"]),
        updates={**updates, "profile_verified_at": datetime.now(UTC)},
        enriched_at=datetime.now(UTC),
    )


def _upsert_funding_event(conn: Any, row: dict[str, Any], company_id: str) -> str:
    return supabase_db.upsert_funding_event(
        conn,
        company_id=company_id,
        announced_on=_parse_date(row.get("announced_on")),
        stage=row.get("stage"),
        amount_usd=(
            float(_parse_decimal(row.get("amount_usd")))
            if _parse_decimal(row.get("amount_usd")) is not None
            else None
        ),
        currency_raw=row.get("currency_raw"),
        lead_investor=row.get("lead_investor"),
        investors=row.get("investors") or [],
        source_url=row.get("source_url"),
    )


def run_apply(
    *,
    input_path: Path,
    apply: bool,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> ApplySummary:
    """Validate and optionally apply a reviewed Cut Through import payload."""
    payload = _load_payload(input_path)
    summary = ApplySummary(input_path=str(input_path), apply=apply)
    validation_errors = _validate_payload(payload)
    if validation_errors:
        summary.errors.extend(validation_errors)
        return summary

    funding_rows = payload["funding_events"]
    company_rows = payload["company_candidates"]
    summary.funding_seen = len(funding_rows)
    summary.companies_seen = len(company_rows)

    if not apply:
        summary.funding_upserted = sum(
            1 for row in funding_rows if row["reviewed_action"] == "upsert"
        )
        summary.companies_inserted_pending = sum(
            1 for row in company_rows if row["reviewed_action"] == "insert_pending"
        )
        summary.companies_stage_updated = sum(
            1 for row in company_rows if row["reviewed_action"] == "update_verified_stage"
        )
        summary.companies_verified_updated = sum(
            1 for row in company_rows if row["reviewed_action"] == "update_verified_fields"
        )
        return summary

    if not _op_env_is_resolved():
        summary.errors.append(
            "live apply requires resolved SUPABASE_DB_URL; run via op run with .env.local"
        )
        return summary

    with supabase_db.connection() as conn:
        resolved_companies, resolved_funding, db_errors = _validate_against_db(
            conn,
            funding_rows=funding_rows,
            company_rows=company_rows,
        )
        if db_errors:
            summary.errors.extend(db_errors)
            return summary
        snapshot_path = _write_snapshot(
            conn=conn,
            input_path=input_path,
            snapshot_dir=snapshot_dir,
            resolved_companies=resolved_companies,
            resolved_funding=resolved_funding,
        )
        summary.snapshot_path = str(snapshot_path)

        inserted_company_ids: dict[tuple[str, str | None], str] = {}
        for action in resolved_companies:
            row = action.row
            if row["reviewed_action"] == "insert_pending":
                company_id = _insert_pending_company(conn, row)
                inserted_company_ids[_company_key(row)] = company_id
                summary.companies_inserted_pending += 1
            elif (
                row["reviewed_action"]
                in {
                    "update_verified_stage",
                    "update_verified_fields",
                }
                and action.company is not None
            ):
                _update_verified_company_fields(conn, row, action.company)
                if row["reviewed_action"] == "update_verified_stage":
                    summary.companies_stage_updated += 1
                else:
                    summary.companies_verified_updated += 1

        for action in resolved_funding:
            row = action.row
            company_id: str | None = None
            if action.company is not None:
                company_id = str(action.company["id"])
            elif _matching_insert_candidate(row, company_rows) is not None:
                company_id = inserted_company_ids.get(_company_key(row))
                if company_id is None:
                    company = _resolve_company(conn, row)
                    company_id = str(company["id"]) if company else None
            if company_id is None:
                summary.errors.append(
                    f"{row['company_name']}: could not resolve company after insert"
                )
                continue
            _upsert_funding_event(conn, row, company_id)
            summary.funding_upserted += 1

        if summary.errors:
            conn.rollback()
            return summary
        conn.commit()
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--apply", action="store_true", help="Write reviewed rows to Supabase")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    summary = run_apply(
        input_path=args.input_path,
        apply=args.apply,
        snapshot_dir=args.snapshot_dir,
    )
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
