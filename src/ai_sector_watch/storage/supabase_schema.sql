-- AI Sector Watch — Supabase Postgres schema (v0).
-- Idempotent: safe to apply repeatedly. Uses IF NOT EXISTS and DO blocks.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================================
-- Enums
-- =========================================================================

DO $$ BEGIN
    CREATE TYPE discovery_status AS ENUM (
        'verified',
        'auto_discovered_pending_review',
        'rejected'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE company_stage AS ENUM (
        'pre_seed',
        'seed',
        'series_a',
        'series_b_plus',
        'mature'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE news_kind AS ENUM (
        'funding',
        'launch',
        'hire',
        'partnership',
        'other'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- =========================================================================
-- Companies
-- =========================================================================

CREATE TABLE IF NOT EXISTS companies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    name_normalised TEXT NOT NULL,        -- lower(trim(name)) for de-dup
    website         TEXT,
    country         TEXT,                 -- AU / NZ / other ISO-ish
    city            TEXT,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    sector_tags     TEXT[] NOT NULL DEFAULT '{}',
    stage           company_stage,
    founded_year    INTEGER,
    summary         TEXT,
    evidence_urls   TEXT[] NOT NULL DEFAULT '{}',
    enriched_at     TIMESTAMPTZ,
    founders        TEXT[] NOT NULL DEFAULT '{}',
    total_raised_usd NUMERIC(14, 2),
    total_raised_currency_raw TEXT,
    total_raised_as_of DATE,
    total_raised_source_url TEXT,
    valuation_usd   NUMERIC(14, 2),
    valuation_currency_raw TEXT,
    valuation_as_of DATE,
    valuation_source_url TEXT,
    headcount_estimate INTEGER,
    headcount_min   INTEGER,
    headcount_max   INTEGER,
    headcount_as_of DATE,
    headcount_source_url TEXT,
    profile_confidence NUMERIC(3, 2),
    profile_sources TEXT[] NOT NULL DEFAULT '{}',
    profile_verified_at TIMESTAMPTZ,
    discovery_status discovery_status NOT NULL DEFAULT 'auto_discovered_pending_review',
    discovery_source TEXT,                -- e.g. 'seed', 'startup_daily_au'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS evidence_urls TEXT[] NOT NULL DEFAULT '{}';

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ;

ALTER TABLE companies
    ADD COLUMN IF NOT EXISTS founders TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS total_raised_usd NUMERIC(14, 2),
    ADD COLUMN IF NOT EXISTS total_raised_currency_raw TEXT,
    ADD COLUMN IF NOT EXISTS total_raised_as_of DATE,
    ADD COLUMN IF NOT EXISTS total_raised_source_url TEXT,
    ADD COLUMN IF NOT EXISTS valuation_usd NUMERIC(14, 2),
    ADD COLUMN IF NOT EXISTS valuation_currency_raw TEXT,
    ADD COLUMN IF NOT EXISTS valuation_as_of DATE,
    ADD COLUMN IF NOT EXISTS valuation_source_url TEXT,
    ADD COLUMN IF NOT EXISTS headcount_estimate INTEGER,
    ADD COLUMN IF NOT EXISTS headcount_min INTEGER,
    ADD COLUMN IF NOT EXISTS headcount_max INTEGER,
    ADD COLUMN IF NOT EXISTS headcount_as_of DATE,
    ADD COLUMN IF NOT EXISTS headcount_source_url TEXT,
    ADD COLUMN IF NOT EXISTS profile_confidence NUMERIC(3, 2),
    ADD COLUMN IF NOT EXISTS profile_sources TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS profile_verified_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS companies_name_country_unique
    ON companies (name_normalised, COALESCE(country, ''));

CREATE INDEX IF NOT EXISTS companies_status_idx
    ON companies (discovery_status);

CREATE INDEX IF NOT EXISTS companies_country_idx
    ON companies (country);

CREATE INDEX IF NOT EXISTS companies_sector_tags_gin
    ON companies USING GIN (sector_tags);

-- =========================================================================
-- Funding events
-- =========================================================================

CREATE TABLE IF NOT EXISTS funding_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    announced_on  DATE,
    stage         company_stage,
    amount_usd    NUMERIC(14, 2),
    currency_raw  TEXT,                   -- e.g. 'AUD 5M' before USD normalisation
    lead_investor TEXT,
    investors     TEXT[] NOT NULL DEFAULT '{}',
    source_url    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, announced_on, stage)
);

CREATE INDEX IF NOT EXISTS funding_events_company_idx
    ON funding_events (company_id);

CREATE INDEX IF NOT EXISTS funding_events_announced_idx
    ON funding_events (announced_on DESC);

-- =========================================================================
-- News items (per-source articles already filtered as relevant)
-- =========================================================================

CREATE TABLE IF NOT EXISTS news_items (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_slug   TEXT NOT NULL,           -- matches sources/<slug>.py
    source_url    TEXT NOT NULL,
    url_hash      TEXT NOT NULL,           -- SHA256(source_url) for unique idx
    title         TEXT NOT NULL,
    summary       TEXT,
    published_at  TIMESTAMPTZ,
    kind          news_kind NOT NULL DEFAULT 'other',
    company_ids   UUID[] NOT NULL DEFAULT '{}',
    raw_payload   JSONB,                   -- minimal structured snapshot
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (url_hash)
);

CREATE INDEX IF NOT EXISTS news_items_published_idx
    ON news_items (published_at DESC);

CREATE INDEX IF NOT EXISTS news_items_companies_gin
    ON news_items USING GIN (company_ids);

-- =========================================================================
-- Ingest events (per-source-fetch audit, deduplicates by payload hash)
-- =========================================================================

CREATE TABLE IF NOT EXISTS ingest_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_slug   TEXT NOT NULL,
    kind          TEXT NOT NULL,           -- e.g. 'rss_fetch', 'extraction'
    payload_hash  TEXT NOT NULL,
    window_start  TIMESTAMPTZ,
    window_end    TIMESTAMPTZ,
    status        TEXT NOT NULL DEFAULT 'ok',
    error         TEXT,
    items_seen    INTEGER NOT NULL DEFAULT 0,
    items_new     INTEGER NOT NULL DEFAULT 0,
    cost_usd      NUMERIC(8, 4),
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_slug, kind, payload_hash)
);

CREATE INDEX IF NOT EXISTS ingest_events_fetched_idx
    ON ingest_events (fetched_at DESC);

-- Structured per-event detail. Used by the admin UI's audit log
-- (kind='admin_action') to capture which company was acted on, the
-- resulting status, and the actor. Pipeline writers may also use it.
ALTER TABLE ingest_events
    ADD COLUMN IF NOT EXISTS metadata JSONB;

-- =========================================================================
-- updated_at trigger for companies
-- =========================================================================

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS companies_set_updated_at ON companies;
CREATE TRIGGER companies_set_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
