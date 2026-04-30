// Freshness signals derived from existing profile fields. Used by the
// directory, map, and profile surfaces to highlight recently verified or
// recently funded companies.

import type { Company } from "./types";

export const RECENTLY_VERIFIED_DAYS = 30;
export const RECENTLY_FUNDED_DAYS = 90;

export const FRESHNESS_VERIFIED = "verified";
export const FRESHNESS_FUNDED = "funded";

export type FreshnessFlag = typeof FRESHNESS_VERIFIED | typeof FRESHNESS_FUNDED;

export const FRESHNESS_OPTIONS: { value: FreshnessFlag; label: string }[] = [
  { value: FRESHNESS_VERIFIED, label: "Recently verified" },
  { value: FRESHNESS_FUNDED, label: "Newly funded" },
];

function daysSince(iso: string | null, now: Date): number | null {
  if (!iso) return null;
  const parsed = Date.parse(iso);
  if (!Number.isFinite(parsed)) return null;
  const diffMs = now.getTime() - parsed;
  if (diffMs < 0) return 0;
  return diffMs / (1000 * 60 * 60 * 24);
}

export function isRecentlyVerified(c: Company, now: Date = new Date()): boolean {
  const days = daysSince(c.profile_verified_at, now);
  return days !== null && days <= RECENTLY_VERIFIED_DAYS;
}

export function isRecentlyFunded(c: Company, now: Date = new Date()): boolean {
  const days = daysSince(c.total_raised_as_of, now);
  return days !== null && days <= RECENTLY_FUNDED_DAYS;
}

export function verifiedAtMs(c: Company): number | null {
  if (!c.profile_verified_at) return null;
  const parsed = Date.parse(c.profile_verified_at);
  return Number.isFinite(parsed) ? parsed : null;
}

export function fundedAtMs(c: Company): number | null {
  if (!c.total_raised_as_of) return null;
  const parsed = Date.parse(c.total_raised_as_of);
  return Number.isFinite(parsed) ? parsed : null;
}
