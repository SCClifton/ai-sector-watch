# Taxonomy

Canonical list of sector tags, stage values, and the sector colour groupings used on the map.

The Python source of truth is `src/ai_sector_watch/discovery/taxonomy.py`. This document mirrors it for human reference. Any change here requires a matching change there (and vice versa) plus an update to `src/ai_sector_watch/storage/supabase_schema.sql` if enums are involved.

## Sectors (21 tags, 9 colour groups)

| Tag | Label | Colour group |
|---|---|---|
| foundation_models | Foundation models | infra |
| ai_infrastructure | AI infrastructure | infra |
| vector_search_and_retrieval | Vector search and retrieval | infra |
| evals_and_observability | Evals and observability | infra |
| edge_and_on_device | Edge and on-device | infra |
| vertical_legal | Legal | vertical |
| vertical_healthcare | Healthcare | vertical |
| vertical_finance | Finance | vertical |
| vertical_sales_marketing | Sales and marketing | vertical |
| vertical_security | Security | vertical |
| robotics_industrial | Industrial robotics | robotics |
| robotics_autonomous_vehicles | Autonomous vehicles | robotics |
| robotics_household | Household robotics | robotics |
| ai_for_science_biology | Science: biology | science |
| ai_for_science_chemistry | Science: chemistry | science |
| ai_for_science_materials | Science: materials | science |
| ai_for_climate_energy | Climate and energy | climate |
| defence_and_dual_use | Defence and dual use | defence |
| developer_tools | Developer tools | dev_tools |
| agents_and_orchestration | Agents and orchestration | agents |
| creative_and_media | Creative and media | creative |

## Colour group -> map marker colour

| Group | Folium colour |
|---|---|
| infra | blue |
| vertical | green |
| robotics | orange |
| science | purple |
| climate | darkgreen |
| defence | black |
| dev_tools | cadetblue |
| agents | red |
| creative | pink |

A company with multiple sector tags renders with the colour of its first listed tag (most specific or most representative first).

## Stages

| Value | Description |
|---|---|
| pre_seed | Pre-seed (friends and family, angel, accelerator) |
| seed | Seed |
| series_a | Series A |
| series_b_plus | Series B and beyond (until graduation to "mature") |
| mature | Public, profitable, or large-scale private |

## Adding a sector

1. Add a tuple to `SECTORS` in `src/ai_sector_watch/discovery/taxonomy.py`.
2. Pick an existing colour group, or add a new group + colour to `SECTOR_GROUPS` and `_GROUP_COLOURS`.
3. Update the table above.
4. Update the SQL enum in `src/ai_sector_watch/storage/supabase_schema.sql` (will land in commit 03) and ship a migration.
5. Run `pytest tests/test_taxonomy.py`.
