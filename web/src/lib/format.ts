// Mirrors _format_amount_usd / _headcount_line in
// dashboard/components/map_view.py.

import type { Company, FundingEvent, Stage } from "./types";
import { STAGE_LABELS } from "./taxonomy";

const isStage = (value: string | null): value is Stage =>
  value === "pre_seed" ||
  value === "seed" ||
  value === "series_a" ||
  value === "series_b_plus" ||
  value === "mature";

export function formatUsd(amount: number | null | undefined): string | null {
  if (amount === null || amount === undefined) return null;
  if (amount >= 1_000_000_000) {
    const value = (amount / 1_000_000_000).toFixed(1).replace(/\.0$/, "");
    return `US$${value}B`;
  }
  if (amount >= 1_000_000) {
    const value = (amount / 1_000_000).toFixed(1).replace(/\.0$/, "");
    return `US$${value}M`;
  }
  if (amount >= 1_000) {
    const value = (amount / 1_000).toFixed(1).replace(/\.0$/, "");
    return `US$${value}K`;
  }
  return `US$${Math.round(amount).toLocaleString()}`;
}

export function formatStage(stage: string | null | undefined): string | null {
  if (!stage) return null;
  if (isStage(stage)) return STAGE_LABELS[stage];
  return stage.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatHeadcount(c: Company): string | null {
  if (c.headcount_estimate !== null) return String(c.headcount_estimate);
  if (c.headcount_min !== null && c.headcount_max !== null) {
    return `${c.headcount_min}-${c.headcount_max}`;
  }
  if (c.headcount_min !== null) return `${c.headcount_min}+`;
  if (c.headcount_max !== null) return `up to ${c.headcount_max}`;
  return null;
}

export function formatFundingAmount(event: FundingEvent | null): string | null {
  if (!event) return null;
  return formatUsd(event.amount_usd) ?? event.currency_raw;
}

export function formatLatestFunding(event: FundingEvent | null): string | null {
  if (!event) return null;
  const bits: string[] = [];
  const stageLabel = formatStage(event.stage);
  if (stageLabel) bits.push(stageLabel);
  if (event.announced_on) bits.push(event.announced_on.slice(0, 10));
  const amount = formatFundingAmount(event);
  if (amount) bits.push(amount);
  return bits.length > 0 ? bits.join(", ") : null;
}

export function formatLocation(c: Company): string | null {
  const bits = [c.city, c.country].filter((b): b is string => Boolean(b));
  return bits.length > 0 ? bits.join(", ") : null;
}
