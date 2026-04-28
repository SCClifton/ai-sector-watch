// Mirrors src/ai_sector_watch/discovery/taxonomy.py. Edit in lockstep.

import type { Stage } from "./types";

export const STAGES: readonly Stage[] = [
  "pre_seed",
  "seed",
  "series_a",
  "series_b_plus",
  "mature",
] as const;

export const STAGE_LABELS: Record<Stage, string> = {
  pre_seed: "Pre-seed",
  seed: "Seed",
  series_a: "Series A",
  series_b_plus: "Series B+",
  mature: "Mature",
};

export type SectorGroup =
  | "infra"
  | "vertical"
  | "robotics"
  | "science"
  | "climate"
  | "defence"
  | "dev_tools"
  | "agents"
  | "creative";

export interface Sector {
  tag: string;
  label: string;
  group: SectorGroup;
}

const GROUP_HEX: Record<SectorGroup, string> = {
  infra: "#4F8DFF",
  vertical: "#4ADE80",
  robotics: "#FB923C",
  science: "#C084FC",
  climate: "#34D399",
  defence: "#94A3B8",
  dev_tools: "#67E8F9",
  agents: "#F87171",
  creative: "#F472B6",
};

const DEFAULT_HEX = "#8B95A6";

export const SECTORS: readonly Sector[] = [
  { tag: "foundation_models", label: "Foundation models", group: "infra" },
  { tag: "ai_infrastructure", label: "AI infrastructure", group: "infra" },
  { tag: "vector_search_and_retrieval", label: "Vector search and retrieval", group: "infra" },
  { tag: "evals_and_observability", label: "Evals and observability", group: "infra" },
  { tag: "vertical_legal", label: "Legal", group: "vertical" },
  { tag: "vertical_healthcare", label: "Healthcare", group: "vertical" },
  { tag: "vertical_finance", label: "Finance", group: "vertical" },
  { tag: "vertical_sales_marketing", label: "Sales and marketing", group: "vertical" },
  { tag: "vertical_security", label: "Security", group: "vertical" },
  { tag: "robotics_industrial", label: "Industrial robotics", group: "robotics" },
  { tag: "robotics_autonomous_vehicles", label: "Autonomous vehicles", group: "robotics" },
  { tag: "robotics_household", label: "Household robotics", group: "robotics" },
  { tag: "ai_for_science_biology", label: "Science: biology", group: "science" },
  { tag: "ai_for_science_chemistry", label: "Science: chemistry", group: "science" },
  { tag: "ai_for_science_materials", label: "Science: materials", group: "science" },
  { tag: "ai_for_climate_energy", label: "Climate and energy", group: "climate" },
  { tag: "defence_and_dual_use", label: "Defence and dual use", group: "defence" },
  { tag: "edge_and_on_device", label: "Edge and on-device", group: "infra" },
  { tag: "developer_tools", label: "Developer tools", group: "dev_tools" },
  { tag: "agents_and_orchestration", label: "Agents and orchestration", group: "agents" },
  { tag: "creative_and_media", label: "Creative and media", group: "creative" },
] as const;

const SECTOR_BY_TAG = new Map<string, Sector>(SECTORS.map((s) => [s.tag, s]));

export function getSector(tag: string): Sector | undefined {
  return SECTOR_BY_TAG.get(tag);
}

export function sectorLabel(tag: string): string {
  return SECTOR_BY_TAG.get(tag)?.label ?? tag;
}

export function hexForSector(tag: string): string {
  const sector = SECTOR_BY_TAG.get(tag);
  return sector ? GROUP_HEX[sector.group] : DEFAULT_HEX;
}

export function primarySectorHex(tags: string[]): string {
  for (const tag of tags) {
    const sector = SECTOR_BY_TAG.get(tag);
    if (sector) return GROUP_HEX[sector.group];
  }
  return DEFAULT_HEX;
}
