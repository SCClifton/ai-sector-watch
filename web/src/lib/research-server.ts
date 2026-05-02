// Server-side helpers for stored research brief runs.
// Public pages read only stored Postgres rows or local JSON fallback files.

import "server-only";

import { promises as fs } from "fs";
import path from "path";

import { sql } from "./db";
import type {
  ResearchBriefItem,
  ResearchBriefRun,
  ResearchBriefSections,
  ResearchBriefSource,
} from "./types";

type Row = Record<string, unknown>;

const EMPTY_SECTIONS: ResearchBriefSections = {
  top_items: [],
  papers_worth_reading: [],
  research_artifacts: [],
  lab_company_updates: [],
  watchlist: [],
  skipped_noise_note: "",
};

export async function listResearchRuns(limit = 30): Promise<ResearchBriefRun[]> {
  const boundedLimit = Math.min(Math.max(Math.trunc(limit), 1), 100);
  if (!process.env.SUPABASE_DB_URL) {
    return listResearchRunsFromJson(boundedLimit);
  }
  try {
    const runs = await listResearchRunsFromDb(boundedLimit);
    if (runs.length > 0) return runs;
  } catch (err) {
    console.warn("research db read failed, falling back to JSON", err);
  }
  return listResearchRunsFromJson(boundedLimit);
}

async function listResearchRunsFromDb(limit: number): Promise<ResearchBriefRun[]> {
  const rows = await sql<Row[]>`
    SELECT id, run_date, window_start, window_end, title, summary,
           sections, sources, cost_usd, model, status, created_at, updated_at
    FROM research_brief_runs
    WHERE status = 'published'
    ORDER BY run_date DESC
    LIMIT ${limit}
  `;
  return rows.map(rowToResearchRun);
}

async function listResearchRunsFromJson(limit: number): Promise<ResearchBriefRun[]> {
  const directories = [
    path.resolve(process.cwd(), "data", "research_briefs"),
    path.resolve(process.cwd(), "..", "data", "research_briefs"),
  ];
  for (const directory of directories) {
    const runs = await listResearchRunsFromDirectory(directory, limit);
    if (runs.length > 0) return runs;
  }
  return [];
}

async function listResearchRunsFromDirectory(
  directory: string,
  limit: number,
): Promise<ResearchBriefRun[]> {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    const files = entries
      .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
      .map((entry) => path.join(directory, entry.name))
      .sort()
      .reverse()
      .slice(0, limit);
    const runs = await Promise.all(
      files.map(async (file) => {
        const raw = JSON.parse(await fs.readFile(file, "utf-8")) as unknown;
        return parseResearchRun(raw);
      }),
    );
    return runs.filter((run): run is ResearchBriefRun => run !== null);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
      console.warn("research JSON fallback failed", err);
    }
    return [];
  }
}

function rowToResearchRun(row: Row): ResearchBriefRun {
  return {
    id: String(row.id),
    run_date: toDateString(row.run_date) ?? "",
    window_start: toIso(row.window_start),
    window_end: toIso(row.window_end),
    title: toNullableString(row.title),
    summary: toNullableString(row.summary),
    sections: parseSections(row.sections),
    sources: parseSources(row.sources),
    cost_usd: row.cost_usd === null || row.cost_usd === undefined ? null : Number(row.cost_usd),
    model: toNullableString(row.model),
    status: String(row.status ?? "published"),
    created_at: toIso(row.created_at),
    updated_at: toIso(row.updated_at),
  };
}

function parseResearchRun(value: unknown): ResearchBriefRun | null {
  if (!isRecord(value)) return null;
  const id = toNullableString(value.id);
  const runDate = toNullableString(value.run_date);
  if (!id || !runDate) return null;
  return {
    id,
    run_date: runDate,
    window_start: toNullableString(value.window_start),
    window_end: toNullableString(value.window_end),
    title: toNullableString(value.title),
    summary: toNullableString(value.summary),
    sections: parseSections(value.sections),
    sources: parseSources(value.sources),
    cost_usd:
      value.cost_usd === null || value.cost_usd === undefined ? null : Number(value.cost_usd),
    model: toNullableString(value.model),
    status: toNullableString(value.status) ?? "published",
    created_at: toNullableString(value.created_at),
    updated_at: toNullableString(value.updated_at),
  };
}

function parseSections(value: unknown): ResearchBriefSections {
  if (!isRecord(value)) return EMPTY_SECTIONS;
  return {
    top_items: parseItems(value.top_items),
    papers_worth_reading: parseItems(value.papers_worth_reading),
    research_artifacts: parseItems(value.research_artifacts),
    lab_company_updates: parseItems(value.lab_company_updates),
    watchlist: parseItems(value.watchlist),
    skipped_noise_note: toNullableString(value.skipped_noise_note) ?? "",
  };
}

function parseItems(value: unknown): ResearchBriefItem[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).map((item) => ({
    title: String(item.title ?? ""),
    source_lab: String(item.source_lab ?? ""),
    item_type: String(item.item_type ?? "paper") as ResearchBriefItem["item_type"],
    published_at: toNullableString(item.published_at),
    primary_url: String(item.primary_url ?? ""),
    secondary_urls: Array.isArray(item.secondary_urls) ? item.secondary_urls.map(String) : [],
    takeaway: String(item.takeaway ?? ""),
    why_it_matters: String(item.why_it_matters ?? ""),
    evidence_quality: String(item.evidence_quality ?? ""),
    limitations: String(item.limitations ?? ""),
  }));
}

function parseSources(value: unknown): ResearchBriefSource[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).map((source) => ({
    slug: String(source.slug ?? ""),
    label: String(source.label ?? source.slug ?? ""),
    url: toNullableString(source.url) ?? undefined,
  }));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toNullableString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value;
  return String(value);
}

function toIso(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value;
  return null;
}

function toDateString(value: unknown): string | null {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "string") return value.slice(0, 10);
  return null;
}
