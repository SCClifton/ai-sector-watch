// Server-only Supabase mutations for admin actions.

import "server-only";

import { sql } from "./db";

export type DiscoveryStatus = "verified" | "rejected";

export async function setCompanyStatus(id: string, status: DiscoveryStatus): Promise<void> {
  if (status === "verified") {
    await sql`
      UPDATE companies
      SET discovery_status = 'verified', profile_verified_at = NOW()
      WHERE id = ${id}
    `;
  } else {
    await sql`
      UPDATE companies
      SET discovery_status = 'rejected'
      WHERE id = ${id}
    `;
  }
}

export async function logAdminAction(
  companyId: string,
  status: DiscoveryStatus,
): Promise<void> {
  // Audit log: ingest_events with source_slug='admin_ui', kind='admin_action'.
  // payload_hash bundles company_id + status + epoch_ms to keep each action
  // distinct in time. The unique index on (source_slug, kind, payload_hash)
  // dedupes if the same admin action lands twice.
  const payloadHash = `${companyId}:${status}:${Date.now()}`;
  await sql`
    INSERT INTO ingest_events (source_slug, kind, payload_hash, fetched_at, metadata)
    VALUES (
      'admin_ui',
      'admin_action',
      ${payloadHash},
      NOW(),
      ${sql.json({ company_id: companyId, status, actor: "admin_ui" })}
    )
    ON CONFLICT (source_slug, kind, payload_hash) DO NOTHING
  `;
}

interface PendingRow {
  id: string;
  name: string;
  country: string | null;
  city: string | null;
  stage: string | null;
  founded_year: number | null;
  summary: string | null;
  sector_tags: string[];
  founders: string[];
  website: string | null;
  discovery_source: string | null;
  profile_sources: string[];
}

export async function listPendingCompanies(): Promise<PendingRow[]> {
  const rows = await sql<Record<string, unknown>[]>`
    SELECT id, name, country, city, stage, founded_year, summary,
           sector_tags, founders, website, discovery_source, profile_sources
    FROM companies
    WHERE discovery_status = 'auto_discovered_pending_review'
    ORDER BY name
  `;
  return rows.map((r) => ({
    id: String(r.id),
    name: r.name as string,
    country: (r.country as string | null) ?? null,
    city: (r.city as string | null) ?? null,
    stage: (r.stage as string | null) ?? null,
    founded_year:
      r.founded_year === null || r.founded_year === undefined
        ? null
        : Number(r.founded_year),
    summary: (r.summary as string | null) ?? null,
    sector_tags: Array.isArray(r.sector_tags) ? r.sector_tags.map(String) : [],
    founders: Array.isArray(r.founders) ? r.founders.map(String) : [],
    website: (r.website as string | null) ?? null,
    discovery_source: (r.discovery_source as string | null) ?? null,
    profile_sources: Array.isArray(r.profile_sources)
      ? r.profile_sources.map(String)
      : [],
  }));
}

export async function getRejectedCount(): Promise<number> {
  const rows = await sql<Record<string, unknown>[]>`
    SELECT COUNT(*)::int AS n
    FROM companies
    WHERE discovery_status = 'rejected'
  `;
  return rows[0] ? Number(rows[0].n) : 0;
}
