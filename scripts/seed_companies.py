#!/usr/bin/env python3
"""Bootstrap Supabase from data/seed/companies.yaml.

Reads the human-curated YAML, validates every entry against the taxonomy and
geocoder, then upserts each company with `discovery_status = 'verified'`.
Idempotent: re-running is a no-op for unchanged rows.

Usage:
    op run --env-file=.env.local -- python scripts/seed_companies.py
    python scripts/seed_companies.py --dry-run   # validate only, no DB writes
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ai_sector_watch.config import configure_logging  # noqa: E402
from ai_sector_watch.discovery.geocoder import geocode_city  # noqa: E402
from ai_sector_watch.discovery.taxonomy import (  # noqa: E402
    is_valid_sector,
    is_valid_stage,
)
from ai_sector_watch.storage import supabase_db  # noqa: E402

LOGGER = logging.getLogger("seed_companies")

SEED_PATH = REPO_ROOT / "data" / "seed" / "companies.yaml"
ALLOWED_COUNTRIES = {"AU", "NZ"}


class SeedValidationError(Exception):
    pass


def load_seed_yaml(path: Path = SEED_PATH) -> list[dict]:
    """Load and shallow-validate the YAML structure. Returns the company list."""
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "companies" not in data:
        raise SeedValidationError(f"{path}: top-level 'companies' key missing")
    companies = data["companies"]
    if not isinstance(companies, list):
        raise SeedValidationError(f"{path}: 'companies' must be a list")
    return companies


def validate_company(entry: dict, *, index: int) -> list[str]:
    """Return a list of human-readable error messages for one entry."""
    errors: list[str] = []
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"entry {index}: missing or empty 'name'")
        return errors  # without a name we can't usefully check the rest

    prefix = f"entry {index} ({name!r})"

    country = entry.get("country")
    if country not in ALLOWED_COUNTRIES:
        errors.append(f"{prefix}: country must be one of {sorted(ALLOWED_COUNTRIES)}")

    city = entry.get("city")
    if not city:
        errors.append(f"{prefix}: 'city' is required")
    else:
        result = geocode_city(city)
        if not result:
            errors.append(f"{prefix}: city {city!r} not in ANZ_CITIES")

    tags = entry.get("sector_tags") or []
    if not tags:
        errors.append(f"{prefix}: at least one sector_tag is required")
    for tag in tags:
        if not is_valid_sector(tag):
            errors.append(f"{prefix}: unknown sector_tag {tag!r}")

    stage = entry.get("stage")
    if stage and not is_valid_stage(stage):
        errors.append(f"{prefix}: unknown stage {stage!r}")

    founded_year = entry.get("founded_year")
    if founded_year is not None and (
        not isinstance(founded_year, int) or founded_year < 1900 or founded_year > 2100
    ):
        errors.append(f"{prefix}: founded_year must be a sensible int")

    description = entry.get("description_seed", "")
    if "—" in description:
        errors.append(f"{prefix}: em dash found in description_seed (PRD section 16)")

    return errors


def validate_all(entries: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for i, entry in enumerate(entries):
        errors.extend(validate_company(entry, index=i))
        key = (entry.get("name", "").strip().lower(), entry.get("country", ""))
        if key in seen:
            errors.append(f"entry {i} ({entry.get('name')!r}): duplicate (name, country)")
        seen.add(key)
    return errors


def seed_to_supabase(entries: list[dict]) -> tuple[int, int]:
    """Apply schema if missing, then upsert every entry. Returns (inserted, updated)."""
    inserted, updated = 0, 0
    with supabase_db.connection() as conn:
        # Make sure the schema exists; safe and idempotent.
        supabase_db.apply_schema(conn)
        for entry in entries:
            geo = geocode_city(entry["city"], jitter_seed=entry["name"])
            assert geo is not None, "validate_all should have caught unknown cities"
            existing = supabase_db.get_company_by_name(conn, entry["name"], entry["country"])
            supabase_db.upsert_company(
                conn,
                name=entry["name"],
                country=entry["country"],
                city=geo.city,
                lat=geo.lat,
                lon=geo.lon,
                website=entry.get("website"),
                sector_tags=entry["sector_tags"],
                stage=entry.get("stage"),
                founded_year=entry.get("founded_year"),
                summary=(entry.get("description_seed") or "").strip() or None,
                discovery_status="verified",
                discovery_source="seed",
            )
            if existing is None:
                inserted += 1
            else:
                updated += 1
        conn.commit()
    return inserted, updated


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the YAML but do not write to Supabase",
    )
    args = parser.parse_args()

    entries = load_seed_yaml()
    LOGGER.info("loaded %d seed entries from %s", len(entries), SEED_PATH)

    errors = validate_all(entries)
    if errors:
        for err in errors:
            LOGGER.error(err)
        LOGGER.error("validation failed: %d issue(s)", len(errors))
        return 1
    LOGGER.info("validation passed")

    if args.dry_run:
        LOGGER.info("--dry-run: skipping Supabase writes")
        return 0

    inserted, updated = seed_to_supabase(entries)
    LOGGER.info("seed complete: inserted=%d updated=%d", inserted, updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
