// Mirrors src/ai_sector_watch/storage/data_source.py. Edit in lockstep.

export type Stage = "pre_seed" | "seed" | "series_a" | "series_b_plus" | "mature";

export interface FundingEvent {
  id: string;
  announced_on: string | null;
  stage: Stage | string | null;
  amount_usd: number | null;
  currency_raw: string | null;
  lead_investor: string | null;
  investors: string[];
}

export interface Company {
  id: string;
  name: string;
  country: string | null;
  city: string | null;
  lat: number | null;
  lon: number | null;
  website: string | null;
  sector_tags: string[];
  stage: Stage | string | null;
  founded_year: number | null;
  summary: string | null;
  total_raised_usd: number | null;
  total_raised_currency_raw: string | null;
  total_raised_as_of: string | null;
  valuation_usd: number | null;
  valuation_currency_raw: string | null;
  valuation_as_of: string | null;
  headcount_estimate: number | null;
  headcount_min: number | null;
  headcount_max: number | null;
  headcount_as_of: string | null;
  profile_confidence: number | null;
  profile_verified_at: string | null;
  latest_funding_event: FundingEvent | null;
  funding_events: FundingEvent[];
}

export interface NewsItem {
  id: string;
  source_slug: string;
  source_url: string;
  title: string;
  summary: string | null;
  published_at: string | null;
  kind: string;
  company_ids: string[];
}

export type ResearchItemType =
  | "paper"
  | "artifact"
  | "lab_update"
  | "benchmark"
  | "model_card"
  | "system_card"
  | "dataset"
  | "code"
  | "watchlist";

export interface ResearchBriefItem {
  title: string;
  source_lab: string;
  item_type: ResearchItemType;
  published_at: string | null;
  primary_url: string;
  secondary_urls: string[];
  takeaway: string;
  why_it_matters: string;
  evidence_quality: string;
  limitations: string;
}

export interface ResearchBriefSections {
  top_items: ResearchBriefItem[];
  papers_worth_reading: ResearchBriefItem[];
  research_artifacts: ResearchBriefItem[];
  lab_company_updates: ResearchBriefItem[];
  watchlist: ResearchBriefItem[];
  skipped_noise_note: string;
}

export interface ResearchBriefSource {
  slug: string;
  label: string;
  url?: string;
}

export interface ResearchBriefRun {
  id: string;
  run_date: string;
  window_start: string | null;
  window_end: string | null;
  title: string | null;
  summary: string | null;
  sections: ResearchBriefSections;
  sources: ResearchBriefSource[];
  cost_usd: number | null;
  model: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}
