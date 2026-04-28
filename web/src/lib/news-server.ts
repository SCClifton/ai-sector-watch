// Server-side helpers for fetching news + LLM spend summary.
// Mirrors SupabaseSource.recent_news / llm_spend_summary in
// src/ai_sector_watch/storage/data_source.py.

import "server-only";

import { sql } from "./db";
import type { NewsItem } from "./types";

type Row = Record<string, unknown>;

export interface SpendSummary {
  total_usd: number;
  average_usd: number;
  run_count: number;
}

function toIso(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value;
  return null;
}

export async function listRecentNews(limit = 100): Promise<NewsItem[]> {
  const rows = await sql<Row[]>`
    SELECT id, source_slug, source_url, title, summary,
           published_at, kind, company_ids
    FROM news_items
    ORDER BY published_at DESC NULLS LAST, fetched_at DESC
    LIMIT ${limit}
  `;
  return rows.map((r) => ({
    id: String(r.id),
    source_slug: r.source_slug as string,
    source_url: r.source_url as string,
    title: r.title as string,
    summary: (r.summary as string | null) ?? null,
    published_at: toIso(r.published_at),
    kind: r.kind as string,
    company_ids: Array.isArray(r.company_ids) ? r.company_ids.map(String) : [],
  }));
}

export async function getSpendSummary(): Promise<SpendSummary | null> {
  const rows = await sql<Row[]>`
    SELECT
        COUNT(cost_usd)::int AS run_count,
        SUM(cost_usd) AS total_usd,
        AVG(cost_usd) AS average_usd
    FROM ingest_events
    WHERE kind = 'weekly_run'
      AND cost_usd IS NOT NULL
      AND fetched_at >= NOW() - INTERVAL '4 weeks'
  `;
  const r = rows[0];
  if (!r || Number(r.run_count) === 0) return null;
  return {
    total_usd: Number(r.total_usd),
    average_usd: Number(r.average_usd),
    run_count: Number(r.run_count),
  };
}
