"""Tests for the sector and stage taxonomy."""

from __future__ import annotations

from ai_sector_watch.discovery.taxonomy import (
    SECTOR_GROUPS,
    SECTOR_TAGS,
    SECTORS,
    STAGES,
    colour_for_sector,
    get_sector,
    is_valid_sector,
    is_valid_stage,
    primary_sector_colour,
)


def test_all_prd_sectors_present() -> None:
    """Every sector in PRD section 9 must exist in the canonical list."""
    expected = {
        "foundation_models",
        "ai_infrastructure",
        "vector_search_and_retrieval",
        "evals_and_observability",
        "vertical_legal",
        "vertical_healthcare",
        "vertical_finance",
        "vertical_sales_marketing",
        "vertical_security",
        "robotics_industrial",
        "robotics_autonomous_vehicles",
        "robotics_household",
        "ai_for_science_biology",
        "ai_for_science_chemistry",
        "ai_for_science_materials",
        "ai_for_climate_energy",
        "defence_and_dual_use",
        "edge_and_on_device",
        "developer_tools",
        "agents_and_orchestration",
        "creative_and_media",
    }
    assert set(SECTOR_TAGS) == expected


def test_all_prd_stages_present() -> None:
    assert set(STAGES) == {"pre_seed", "seed", "series_a", "series_b_plus", "mature"}


def test_every_sector_has_known_group() -> None:
    for sector in SECTORS:
        assert sector.group in SECTOR_GROUPS, f"{sector.tag} maps to unknown group {sector.group}"


def test_get_sector_lookup_round_trips() -> None:
    for tag in SECTOR_TAGS:
        sector = get_sector(tag)
        assert sector is not None and sector.tag == tag


def test_get_sector_unknown_returns_none() -> None:
    assert get_sector("not-a-real-sector") is None


def test_is_valid_sector_and_stage() -> None:
    assert is_valid_sector("foundation_models")
    assert not is_valid_sector("crypto")
    assert is_valid_stage("seed")
    assert not is_valid_stage("ipo")


def test_colour_for_sector_returns_default_on_unknown() -> None:
    assert colour_for_sector("nonsense", default="gray") == "gray"
    assert colour_for_sector("foundation_models") != ""


def test_primary_sector_colour_uses_first_known_tag() -> None:
    # Foundation models are an "infra" group sector with a defined colour.
    colour = primary_sector_colour(["foundation_models", "agents_and_orchestration"])
    assert colour == colour_for_sector("foundation_models")


def test_primary_sector_colour_handles_empty_and_unknown() -> None:
    assert primary_sector_colour([]) == "gray"
    assert primary_sector_colour(["nonsense"]) == "gray"
    assert primary_sector_colour(["nonsense", "agents_and_orchestration"]) == colour_for_sector(
        "agents_and_orchestration"
    )
