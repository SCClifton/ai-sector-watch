"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, MapPin, Newspaper, Sparkles } from "lucide-react";

import { AmbientGlow } from "./AmbientGlow";
import { Constellation } from "./Constellation";
import { RotatingWord } from "./RotatingWord";
import { useCountUp } from "@/lib/useCountUp";
import { SECTORS } from "@/lib/taxonomy";
import type { Company } from "@/lib/types";

const CITY_ROTATION = [
  "Sydney",
  "Melbourne",
  "Brisbane",
  "Auckland",
  "Wellington",
  "Adelaide",
  "Perth",
  "Christchurch",
];

export function HomeContent() {
  const [companies, setCompanies] = useState<Company[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/companies")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: { companies: Company[] }) => {
        if (!cancelled) setCompanies(data.companies);
      })
      .catch(() => {
        // Silent fallback: stats show " - ".
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const totalCompanies = companies?.length ?? null;
  const sectorsActive = companies
    ? new Set(companies.flatMap((c) => c.sector_tags)).size
    : null;
  const cityCount = companies
    ? new Set(companies.map((c) => c.city).filter(Boolean) as string[]).size
    : null;

  return (
    <div className="relative flex flex-1 flex-col">
      <AmbientGlow />

      <section className="mx-auto w-full max-w-[1100px] px-4 pt-12 pb-10 sm:px-5 sm:pt-24">
        <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
          <Sparkles className="h-3.5 w-3.5 text-accent" />
          ANZ AI startup ecosystem
        </div>

        <h1 className="mt-4 text-balance text-4xl font-semibold leading-[1.05] tracking-tight text-text sm:text-[64px] sm:leading-[1.02]">
          A live map of AI companies
          <br className="hidden sm:block" /> building from{" "}
          <span className="text-accent">
            <RotatingWord words={CITY_ROTATION} />
          </span>
          .
        </h1>

        <p className="mt-6 max-w-2xl text-balance text-lg leading-relaxed text-text-muted">
          Updated weekly by an automated agent pipeline. Sector-tagged, geocoded, with funding
          and headcount where we can verify them. Independent and free to use.
        </p>

        <LiveStats
          total={totalCompanies}
          sectors={sectorsActive ?? SECTORS.length}
          cities={cityCount}
        />

        <div className="mt-8 flex flex-col items-stretch gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          <Link
            href="/map"
            className="group inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-accent px-5 py-2.5 text-[14px] font-semibold text-bg transition-colors hover:bg-accent-hover sm:justify-start"
          >
            <MapPin className="h-4 w-4" />
            Open the map
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link
            href="/companies"
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-border-strong bg-surface px-5 py-2.5 text-[14px] font-medium text-text transition-colors hover:border-accent hover:text-accent sm:justify-start"
          >
            Browse companies
          </Link>
          <Link
            href="/news"
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-3 py-2.5 text-[14px] font-medium text-text-muted transition-colors hover:text-text sm:justify-start"
          >
            <Newspaper className="h-4 w-4" />
            News digest
          </Link>
        </div>
      </section>

      <section className="mx-auto w-full max-w-[1100px] px-4 pb-14 sm:px-5">
        <Constellation companies={companies} />
      </section>

      <section className="mx-auto grid w-full max-w-[1100px] grid-cols-1 gap-3 px-4 pb-20 sm:grid-cols-3 sm:px-5">
        {[
          {
            label: "Coverage",
            value: "Australia & New Zealand",
            note: "Founded or HQ'd in ANZ.",
          },
          {
            label: "Cadence",
            value: "Weekly",
            note: "Pipeline runs every Monday morning.",
          },
          {
            label: "Method",
            value: "Agent-curated",
            note: "LLM extraction, human-promoted.",
          },
        ].map((card) => (
          <div
            key={card.label}
            className="rounded-lg border border-border bg-surface p-5 transition-colors hover:border-border-strong"
          >
            <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-text-subtle">
              {card.label}
            </div>
            <div className="mt-2 text-lg font-semibold text-text">{card.value}</div>
            <p className="mt-1 text-[13px] text-text-muted">{card.note}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

function LiveStats({
  total,
  sectors,
  cities,
}: {
  total: number | null;
  sectors: number;
  cities: number | null;
}) {
  const totalAnimated = useCountUp(total);
  const sectorsAnimated = useCountUp(sectors);
  const citiesAnimated = useCountUp(cities);

  const items: { label: string; value: string }[] = [
    {
      label: "verified",
      value: total === null ? "..." : String(totalAnimated),
    },
    {
      label: "sectors",
      value: String(sectorsAnimated || sectors),
    },
    {
      label: "cities",
      value: cities === null ? "..." : String(citiesAnimated),
    },
  ];

  return (
    <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[13px] text-text-muted">
      {items.map((item, i) => (
        <div key={item.label} className="flex items-center gap-5">
          <div className="flex items-baseline gap-1.5">
            <span className="text-[22px] font-semibold tabular-nums text-text">{item.value}</span>
            <span>{item.label}</span>
          </div>
          {i < items.length - 1 && (
            <span aria-hidden className="hidden text-border-strong sm:inline">
              ·
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
