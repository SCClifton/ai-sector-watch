import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";

import type { Company } from "@/lib/types";
import { primarySectorHex, sectorLabel } from "@/lib/taxonomy";
import {
  formatHeadcount,
  formatLatestFunding,
  formatLocation,
  formatStage,
  formatUsd,
} from "@/lib/format";

interface Props {
  company: Company;
}

export function CompanyProfile({ company }: Props) {
  const accent = primarySectorHex(company.sector_tags);
  const location = formatLocation(company);
  const stage = formatStage(company.stage);
  const latestFunding = formatLatestFunding(company.latest_funding_event);
  const totalRaised = formatUsd(company.total_raised_usd);
  const valuation = formatUsd(company.valuation_usd);
  const headcount = formatHeadcount(company);

  return (
    <article className="mx-auto w-full max-w-[900px] px-5 py-10">
      <Link
        href="/companies"
        className="inline-flex items-center gap-1.5 text-[12px] font-medium text-text-muted transition-colors hover:text-accent"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        All companies
      </Link>

      <div className="mt-6 overflow-hidden rounded-xl border border-border bg-surface">
        <div className="h-1.5 w-full" style={{ background: accent }} aria-hidden />

        <header className="border-b border-border px-6 py-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h1 className="text-3xl font-semibold tracking-tight text-text sm:text-4xl">
                {company.name}
              </h1>
              {location && (
                <p className="mt-1.5 text-[14px] text-text-muted">{location}</p>
              )}
            </div>
            {company.website && (
              <a
                href={company.website}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border border-border-strong bg-surface-2 px-3 py-1.5 text-[13px] font-medium text-text transition-colors hover:border-accent hover:text-accent"
              >
                Website
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>

          <dl className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Stage" value={stage} />
            <Stat label="Founded" value={company.founded_year !== null ? String(company.founded_year) : null} />
            <Stat label="Total raised" value={totalRaised} highlight />
            <Stat label="Valuation" value={valuation} highlight />
            <Stat label="Headcount" value={headcount} />
            <Stat label="Verified" value={company.profile_verified_at?.slice(0, 10) ?? null} />
            {latestFunding && (
              <div className="col-span-2">
                <Label>Latest funding</Label>
                <div className="mt-1 text-[14px] text-text">{latestFunding}</div>
              </div>
            )}
          </dl>
        </header>

        <div className="grid grid-cols-1 gap-6 px-6 py-6 sm:grid-cols-3">
          <section className="sm:col-span-2">
            {company.summary && (
              <>
                <Label>Summary</Label>
                <p className="mt-2 whitespace-pre-line text-[14px] leading-relaxed text-text">
                  {company.summary}
                </p>
              </>
            )}

            {company.founders.length > 0 && (
              <div className="mt-6">
                <Label>Founders</Label>
                <p className="mt-2 text-[14px] text-text">{company.founders.join(", ")}</p>
              </div>
            )}

            {company.profile_sources.length > 0 && (
              <div className="mt-6">
                <Label>Sources</Label>
                <ul className="mt-2 space-y-1">
                  {company.profile_sources.map((src) => (
                    <li key={src}>
                      <a
                        href={src}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[13px] text-text-muted transition-colors hover:text-accent"
                      >
                        {prettyHostname(src)}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <aside>
            <Label>Sectors</Label>
            <ul className="mt-2 space-y-1.5">
              {company.sector_tags.map((tag) => (
                <li key={tag} className="flex items-center gap-2 text-[13px] text-text">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: primarySectorHex([tag]) }}
                    aria-hidden
                  />
                  {sectorLabel(tag)}
                </li>
              ))}
            </ul>

            {company.discovery_source && (
              <div className="mt-6 rounded-md border border-border bg-bg/40 px-3 py-2 text-[12px] text-text-muted">
                <Label>Discovery</Label>
                <div className="mt-1 text-text">{company.discovery_source}</div>
              </div>
            )}
          </aside>
        </div>
      </div>
    </article>
  );
}

function Stat({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string | null;
  highlight?: boolean;
}) {
  if (!value) {
    return (
      <div>
        <Label>{label}</Label>
        <div className="mt-1 text-[14px] text-text-subtle">-</div>
      </div>
    );
  }
  return (
    <div>
      <Label>{label}</Label>
      <div
        className={`mt-1 text-[14px] tabular-nums ${highlight ? "font-semibold text-accent" : "text-text"}`}
      >
        {value}
      </div>
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
      {children}
    </div>
  );
}

function prettyHostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
