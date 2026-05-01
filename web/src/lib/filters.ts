// Mirrors apply_filters and FilterState in dashboard/components/filters.py.

import type { Company } from "./types";
import {
  FRESHNESS_FUNDED,
  FRESHNESS_VERIFIED,
  isRecentlyFunded,
  isRecentlyVerified,
  type FreshnessFlag,
} from "./freshness";

export interface FilterState {
  sectors: string[];
  stages: string[];
  countries: string[];
  foundedMin: number | null;
  foundedMax: number | null;
  nameQuery: string;
  freshness: FreshnessFlag[];
}

export const EMPTY_FILTERS: FilterState = {
  sectors: [],
  stages: [],
  countries: [],
  foundedMin: null,
  foundedMax: null,
  nameQuery: "",
  freshness: [],
};

export function isFilterActive(state: FilterState): boolean {
  return (
    state.sectors.length > 0 ||
    state.stages.length > 0 ||
    state.countries.length > 0 ||
    state.foundedMin !== null ||
    state.foundedMax !== null ||
    state.nameQuery.trim() !== "" ||
    state.freshness.length > 0
  );
}

export function applyFilters(companies: Company[], state: FilterState): Company[] {
  let out = companies;

  if (state.sectors.length > 0) {
    const wanted = new Set(state.sectors);
    out = out.filter((c) => c.sector_tags.some((t) => wanted.has(t)));
  }
  if (state.stages.length > 0) {
    const wanted = new Set(state.stages);
    out = out.filter((c) => (c.stage ? wanted.has(c.stage) : false));
  }
  if (state.countries.length > 0) {
    const wanted = new Set(state.countries);
    out = out.filter((c) => (c.country ? wanted.has(c.country) : false));
  }
  if (state.foundedMin !== null) {
    const min = state.foundedMin;
    out = out.filter((c) => c.founded_year === null || c.founded_year >= min);
  }
  if (state.foundedMax !== null) {
    const max = state.foundedMax;
    out = out.filter((c) => c.founded_year === null || c.founded_year <= max);
  }
  const q = state.nameQuery.trim().toLowerCase();
  if (q) {
    out = out.filter((c) => c.name.toLowerCase().includes(q));
  }
  if (state.freshness.length > 0) {
    const now = new Date();
    const wantVerified = state.freshness.includes(FRESHNESS_VERIFIED);
    const wantFunded = state.freshness.includes(FRESHNESS_FUNDED);
    out = out.filter((c) => {
      const v = wantVerified && isRecentlyVerified(c, now);
      const f = wantFunded && isRecentlyFunded(c, now);
      return v || f;
    });
  }

  return out;
}

export interface FilterMeta {
  countries: string[];
  foundedMin: number;
  foundedMax: number;
}

export function deriveMeta(companies: Company[]): FilterMeta {
  const countries = Array.from(
    new Set(companies.map((c) => c.country).filter((c): c is string => Boolean(c))),
  ).sort();
  const years = companies
    .map((c) => c.founded_year)
    .filter((y): y is number => y !== null);
  const currentYear = new Date().getFullYear();
  if (years.length === 0) {
    return { countries, foundedMin: 2000, foundedMax: currentYear };
  }
  return {
    countries,
    foundedMin: Math.min(...years),
    foundedMax: Math.max(...years),
  };
}

// URL-state helpers ----------------------------------------------------------

export function filtersToParams(state: FilterState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.sectors.length > 0) params.set("sectors", state.sectors.join(","));
  if (state.stages.length > 0) params.set("stages", state.stages.join(","));
  if (state.countries.length > 0) params.set("countries", state.countries.join(","));
  if (state.foundedMin !== null) params.set("yearMin", String(state.foundedMin));
  if (state.foundedMax !== null) params.set("yearMax", String(state.foundedMax));
  if (state.nameQuery.trim() !== "") params.set("q", state.nameQuery.trim());
  if (state.freshness.length > 0) params.set("fresh", state.freshness.join(","));
  return params;
}

export function paramsToFilters(params: URLSearchParams): FilterState {
  const split = (key: string): string[] => {
    const raw = params.get(key);
    if (!raw) return [];
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  };
  const numOrNull = (key: string): number | null => {
    const raw = params.get(key);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  };
  const freshness = split("fresh").filter(
    (v): v is FreshnessFlag => v === FRESHNESS_VERIFIED || v === FRESHNESS_FUNDED,
  );
  return {
    sectors: split("sectors"),
    stages: split("stages"),
    countries: split("countries"),
    foundedMin: numOrNull("yearMin"),
    foundedMax: numOrNull("yearMax"),
    nameQuery: params.get("q") ?? "",
    freshness,
  };
}
