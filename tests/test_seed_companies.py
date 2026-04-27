"""Validate that data/seed/companies.yaml passes all static checks.

This catches typos in the seed list before they reach Supabase.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seed_companies import load_seed_yaml, validate_all  # noqa: E402


def test_seed_yaml_has_minimum_50_entries() -> None:
    entries = load_seed_yaml()
    assert len(entries) >= 50, f"expected at least 50 seed entries, got {len(entries)}"


def test_seed_yaml_passes_validation() -> None:
    entries = load_seed_yaml()
    errors = validate_all(entries)
    assert errors == [], "seed YAML failed validation:\n  " + "\n  ".join(errors)


def test_no_duplicate_company_names_per_country() -> None:
    entries = load_seed_yaml()
    pairs = [(e.get("name", "").strip().lower(), e.get("country", "")) for e in entries]
    assert len(pairs) == len(set(pairs)), "duplicate (name, country) in seed YAML"


def test_seed_yaml_has_au_and_nz_entries() -> None:
    entries = load_seed_yaml()
    countries = {e.get("country") for e in entries}
    assert "AU" in countries
    assert "NZ" in countries


def test_validator_catches_em_dash_in_description() -> None:
    """PRD section 16: em dashes are banned in user-facing copy."""
    from seed_companies import validate_company

    bad = {
        "name": "Test Co",
        "country": "AU",
        "city": "Sydney",
        "sector_tags": ["foundation_models"],
        "description_seed": "We do AI — and other things.",
    }
    errors = validate_company(bad, index=0)
    assert any("em dash" in e for e in errors)


def test_validator_catches_unknown_sector_tag() -> None:
    from seed_companies import validate_company

    bad = {
        "name": "Test Co",
        "country": "AU",
        "city": "Sydney",
        "sector_tags": ["not_a_real_sector"],
    }
    errors = validate_company(bad, index=0)
    assert any("unknown sector_tag" in e for e in errors)
