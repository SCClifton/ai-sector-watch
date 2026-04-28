"""Sector and stage enums for the v0 ANZ AI map.

Sectors and stages are intentionally a fixed list (PRD section 9). New entries
require both editing this file and updating `docs/taxonomy.md`. Keep the list
short and orthogonal so the dashboard filters stay usable.

Each sector belongs to a broader colour group used by the map page (PRD
section 11) so markers stay visually decipherable when 21 sector tags are in
play.
"""

from __future__ import annotations

from dataclasses import dataclass

# Stage enum (matches the SQL enum in storage/supabase_schema.sql).
STAGES: tuple[str, ...] = (
    "pre_seed",
    "seed",
    "series_a",
    "series_b_plus",
    "mature",
)


@dataclass(frozen=True)
class Sector:
    """A canonical sector tag plus its colour group and human label."""

    tag: str
    label: str
    group: str  # one of SECTOR_GROUPS
    colour: str  # folium-compatible colour name


SECTOR_GROUPS: tuple[str, ...] = (
    "infra",
    "vertical",
    "robotics",
    "science",
    "climate",
    "defence",
    "dev_tools",
    "agents",
    "creative",
)

_GROUP_COLOURS: dict[str, str] = {
    "infra": "blue",
    "vertical": "green",
    "robotics": "orange",
    "science": "purple",
    "climate": "darkgreen",
    "defence": "black",
    "dev_tools": "cadetblue",
    "agents": "red",
    "creative": "pink",
}

# Hex equivalents tuned for the dark-theme background (#0B0F14). The folium
# named colours above feed `folium.Icon`, which is being phased out for a
# `DivIcon` circle on the dashboard map. The `DivIcon` HTML needs an actual
# CSS hex value, and the dashboard sector legend reuses the same map so the
# legend swatches and map markers stay in sync.
_GROUP_HEX: dict[str, str] = {
    "infra": "#4F8DFF",
    "vertical": "#4ADE80",
    "robotics": "#FB923C",
    "science": "#C084FC",
    "climate": "#34D399",
    "defence": "#94A3B8",
    "dev_tools": "#67E8F9",
    "agents": "#F87171",
    "creative": "#F472B6",
}
_DEFAULT_HEX = "#8B95A6"


def _sector(tag: str, label: str, group: str) -> Sector:
    return Sector(tag=tag, label=label, group=group, colour=_GROUP_COLOURS[group])


SECTORS: tuple[Sector, ...] = (
    _sector("foundation_models", "Foundation models", "infra"),
    _sector("ai_infrastructure", "AI infrastructure", "infra"),
    _sector("vector_search_and_retrieval", "Vector search and retrieval", "infra"),
    _sector("evals_and_observability", "Evals and observability", "infra"),
    _sector("vertical_legal", "Legal", "vertical"),
    _sector("vertical_healthcare", "Healthcare", "vertical"),
    _sector("vertical_finance", "Finance", "vertical"),
    _sector("vertical_sales_marketing", "Sales and marketing", "vertical"),
    _sector("vertical_security", "Security", "vertical"),
    _sector("robotics_industrial", "Industrial robotics", "robotics"),
    _sector("robotics_autonomous_vehicles", "Autonomous vehicles", "robotics"),
    _sector("robotics_household", "Household robotics", "robotics"),
    _sector("ai_for_science_biology", "Science: biology", "science"),
    _sector("ai_for_science_chemistry", "Science: chemistry", "science"),
    _sector("ai_for_science_materials", "Science: materials", "science"),
    _sector("ai_for_climate_energy", "Climate and energy", "climate"),
    _sector("defence_and_dual_use", "Defence and dual use", "defence"),
    _sector("edge_and_on_device", "Edge and on-device", "infra"),
    _sector("developer_tools", "Developer tools", "dev_tools"),
    _sector("agents_and_orchestration", "Agents and orchestration", "agents"),
    _sector("creative_and_media", "Creative and media", "creative"),
)

SECTOR_TAGS: tuple[str, ...] = tuple(s.tag for s in SECTORS)
_SECTOR_BY_TAG: dict[str, Sector] = {s.tag: s for s in SECTORS}


def get_sector(tag: str) -> Sector | None:
    return _SECTOR_BY_TAG.get(tag)


def is_valid_sector(tag: str) -> bool:
    return tag in _SECTOR_BY_TAG


def is_valid_stage(stage: str) -> bool:
    return stage in STAGES


def colour_for_sector(tag: str, *, default: str = "gray") -> str:
    """Return the marker colour for a sector tag, falling back to `default`."""
    sector = get_sector(tag)
    return sector.colour if sector else default


def primary_sector_colour(tags: list[str]) -> str:
    """Pick a single colour for a marker that has multiple sector tags.

    Strategy: use the first tag's colour. The order of `tags` is meaningful
    (most specific or most representative first) and it keeps the visual
    legend simple.
    """
    for tag in tags:
        colour = colour_for_sector(tag, default="")
        if colour:
            return colour
    return "gray"


def hex_for_sector(tag: str, *, default: str = _DEFAULT_HEX) -> str:
    """Return the hex colour for a sector tag, falling back to ``default``."""
    sector = get_sector(tag)
    if sector is None:
        return default
    return _GROUP_HEX.get(sector.group, default)


def primary_sector_hex(tags: list[str], *, default: str = _DEFAULT_HEX) -> str:
    """Pick a single hex colour for a marker that has multiple sector tags."""
    for tag in tags:
        sector = get_sector(tag)
        if sector is None:
            continue
        hex_value = _GROUP_HEX.get(sector.group)
        if hex_value:
            return hex_value
    return default


def hex_for_group(group: str, *, default: str = _DEFAULT_HEX) -> str:
    """Return the hex colour for a sector colour group."""
    return _GROUP_HEX.get(group, default)
