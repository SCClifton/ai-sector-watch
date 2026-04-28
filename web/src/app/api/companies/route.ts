// GET /api/companies?statuses=verified
//
// Mirrors SupabaseSource.list_companies() in
// src/ai_sector_watch/storage/data_source.py. Returns the verified set by default.

import { NextResponse } from "next/server";

import { sql } from "@/lib/db";
import type { Company, FundingEvent } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Row = Record<string, unknown>;

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function toIsoDate(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") return value;
  return null;
}

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => String(v));
  return [];
}

function buildFunding(row: Row): FundingEvent | null {
  if (!row.latest_funding_id) return null;
  return {
    id: String(row.latest_funding_id),
    announced_on: toIsoDate(row.latest_funding_announced_on),
    stage: (row.latest_funding_stage as string | null) ?? null,
    amount_usd: toNumber(row.latest_funding_amount_usd),
    currency_raw: (row.latest_funding_currency_raw as string | null) ?? null,
    lead_investor: (row.latest_funding_lead_investor as string | null) ?? null,
    investors: toStringArray(row.latest_funding_investors),
    source_url: (row.latest_funding_source_url as string | null) ?? null,
  };
}

function buildCompany(row: Row): Company {
  return {
    id: String(row.id),
    name: row.name as string,
    country: (row.country as string | null) ?? null,
    city: (row.city as string | null) ?? null,
    lat: toNumber(row.lat),
    lon: toNumber(row.lon),
    website: (row.website as string | null) ?? null,
    sector_tags: toStringArray(row.sector_tags),
    stage: (row.stage as string | null) ?? null,
    founded_year: toNumber(row.founded_year),
    summary: (row.summary as string | null) ?? null,
    discovery_status: row.discovery_status as string,
    discovery_source: (row.discovery_source as string | null) ?? null,
    founders: toStringArray(row.founders),
    total_raised_usd: toNumber(row.total_raised_usd),
    total_raised_currency_raw: (row.total_raised_currency_raw as string | null) ?? null,
    total_raised_as_of: toIsoDate(row.total_raised_as_of),
    total_raised_source_url: (row.total_raised_source_url as string | null) ?? null,
    valuation_usd: toNumber(row.valuation_usd),
    valuation_currency_raw: (row.valuation_currency_raw as string | null) ?? null,
    valuation_as_of: toIsoDate(row.valuation_as_of),
    valuation_source_url: (row.valuation_source_url as string | null) ?? null,
    headcount_estimate: toNumber(row.headcount_estimate),
    headcount_min: toNumber(row.headcount_min),
    headcount_max: toNumber(row.headcount_max),
    headcount_as_of: toIsoDate(row.headcount_as_of),
    headcount_source_url: (row.headcount_source_url as string | null) ?? null,
    profile_confidence: toNumber(row.profile_confidence),
    profile_sources: toStringArray(row.profile_sources),
    profile_verified_at: toIsoDate(row.profile_verified_at),
    latest_funding_event: buildFunding(row),
  };
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const statusesParam = url.searchParams.getAll("statuses");
  const statuses = statusesParam.length > 0 ? statusesParam : ["verified"];

  try {
    const rows = await sql<Row[]>`
      SELECT
          c.*,
          fe.id AS latest_funding_id,
          fe.announced_on AS latest_funding_announced_on,
          fe.stage AS latest_funding_stage,
          fe.amount_usd AS latest_funding_amount_usd,
          fe.currency_raw AS latest_funding_currency_raw,
          fe.lead_investor AS latest_funding_lead_investor,
          fe.investors AS latest_funding_investors,
          fe.source_url AS latest_funding_source_url
      FROM companies c
      LEFT JOIN LATERAL (
          SELECT id, announced_on, stage, amount_usd, currency_raw,
                 lead_investor, investors, source_url, created_at
          FROM funding_events
          WHERE company_id = c.id
          ORDER BY announced_on DESC NULLS LAST, created_at DESC
          LIMIT 1
      ) fe ON TRUE
      WHERE c.discovery_status = ANY(${statuses})
      ORDER BY c.name
    `;

    const companies = rows.map(buildCompany);
    return NextResponse.json({ companies });
  } catch (err) {
    console.error("GET /api/companies failed", err);
    return NextResponse.json(
      { error: "failed to load companies", detail: String(err) },
      { status: 500 },
    );
  }
}
