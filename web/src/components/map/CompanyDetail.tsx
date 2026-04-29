"use client";

import { useEffect } from "react";
import { ExternalLink, X } from "lucide-react";

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
  company: Company | null;
  onClose: () => void;
}

export function CompanyDetail({ company, onClose }: Props) {
  useEffect(() => {
    if (!company) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [company, onClose]);

  if (!company) return null;

  const accent = primarySectorHex(company.sector_tags);
  const location = formatLocation(company);
  const stage = formatStage(company.stage);
  const latestFunding = formatLatestFunding(company.latest_funding_event);
  const totalRaised = formatUsd(company.total_raised_usd);
  const valuation = formatUsd(company.valuation_usd);
  const headcount = formatHeadcount(company);

  return (
    <aside
      role="dialog"
      aria-label={`${company.name} details`}
      className="aisw-scroll absolute right-3 top-3 bottom-3 z-10 w-[360px] max-w-[calc(100vw-1.5rem)] overflow-y-auto rounded-xl border border-border bg-surface/95 shadow-2xl backdrop-blur-md"
    >
      <div
        className="h-1 w-full rounded-t-xl"
        style={{ background: accent }}
        aria-hidden
      />
      <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div className="min-w-0">
          <h2 className="truncate text-[18px] font-semibold tracking-tight text-text">
            {company.website ? (
              <a
                href={company.website}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-text hover:text-accent"
              >
                {company.name}
                <ExternalLink className="h-3.5 w-3.5 text-text-muted" />
              </a>
            ) : (
              company.name
            )}
          </h2>
          {location && (
            <p className="mt-0.5 text-[12px] text-text-muted">{location}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close details"
          className="rounded-md p-1 text-text-muted transition-colors hover:bg-surface-2 hover:text-text"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="px-5 py-4 text-[13px]">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          {stage && <Cell label="Stage" value={stage} />}
          {company.founded_year !== null && (
            <Cell label="Founded" value={String(company.founded_year)} />
          )}
          {totalRaised && <Cell label="Total raised" value={totalRaised} />}
          {valuation && <Cell label="Valuation" value={valuation} />}
          {headcount && <Cell label="Headcount" value={headcount} />}
          {latestFunding && <Cell label="Latest funding" value={latestFunding} span={2} />}
        </dl>

        {company.sector_tags.length > 0 && (
          <div className="mt-5">
            <Label>Sectors</Label>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {company.sector_tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-md border border-border bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-text"
                >
                  {sectorLabel(tag)}
                </span>
              ))}
            </div>
          </div>
        )}

        {company.summary && (
          <div className="mt-5">
            <Label>Summary</Label>
            <p className="mt-1 text-[13px] leading-relaxed text-text">{company.summary}</p>
          </div>
        )}
      </div>
    </aside>
  );
}

function Cell({
  label,
  value,
  span = 1,
}: {
  label: string;
  value: string;
  span?: 1 | 2;
}) {
  return (
    <div className={span === 2 ? "col-span-2" : "col-span-1"}>
      <Label>{label}</Label>
      <dd className="mt-0.5 text-[13px] text-text">{value}</dd>
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
      {children}
    </dt>
  );
}
