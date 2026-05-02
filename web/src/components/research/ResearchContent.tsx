"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  Beaker,
  BookOpenText,
  Boxes,
  CalendarDays,
  ExternalLink,
  FileText,
  Microscope,
} from "lucide-react";

import type { ResearchBriefItem, ResearchBriefRun, ResearchItemType } from "@/lib/types";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function ResearchContent() {
  const [runs, setRuns] = useState<ResearchBriefRun[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJson<{ runs?: ResearchBriefRun[] }>("/api/research?limit=30")
      .then((res) => {
        if (!cancelled) setRuns(res.runs ?? []);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const latestRun = runs?.[0] ?? null;
  const archiveRuns = runs?.slice(1) ?? [];

  return (
    <section className="mx-auto w-full max-w-[1100px] px-4 py-8 sm:px-5 sm:py-10">
      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
        Research archive
      </div>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-text sm:text-4xl">
        Research
      </h1>
      <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-text-muted">
        Daily frontier AI papers, lab releases, benchmarks, model cards, and research
        artifacts from primary sources.
      </p>

      {loadError && (
        <div className="mt-6 rounded-md border border-error/40 bg-surface px-4 py-3 text-[13px] text-error">
          Failed to load research: {loadError}
        </div>
      )}

      {!loadError && runs === null && (
        <div className="mt-6 rounded-md border border-border bg-surface px-4 py-3 text-[13px] text-text-muted">
          Loading research...
        </div>
      )}

      {!loadError && runs !== null && runs.length === 0 && <EmptyState />}

      {!loadError && latestRun && (
        <div className="mt-8">
          <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
            <Microscope className="h-3.5 w-3.5 text-accent" />
            Latest run
          </div>
          <RunBlock run={latestRun} prominent />
        </div>
      )}

      {!loadError && archiveRuns.length > 0 && (
        <div className="mt-10">
          <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
            <CalendarDays className="h-3.5 w-3.5 text-accent" />
            Chronological archive
          </div>
          <div className="space-y-8">
            {archiveRuns.map((run) => (
              <RunBlock key={run.id} run={run} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function EmptyState() {
  return (
    <div className="mt-6 rounded-md border border-border bg-surface px-4 py-8 text-center">
      <div className="mx-auto grid h-9 w-9 place-items-center rounded-md border border-border bg-surface-2 text-text-muted">
        <AlertCircle className="h-4 w-4" />
      </div>
      <h2 className="mt-3 text-[15px] font-semibold text-text">No research runs yet</h2>
      <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-text-muted">
        Daily research briefs will appear here after the next automated run writes a
        stored brief.
      </p>
    </div>
  );
}

function RunBlock({ run, prominent = false }: { run: ResearchBriefRun; prominent?: boolean }) {
  const topItems = run.sections.top_items.slice(0, 5);
  const topUrls = new Set(topItems.map((item) => item.primary_url));
  const paperItems = uniqueItems(
    run.sections.papers_worth_reading.filter((item) => !topUrls.has(item.primary_url)),
  );
  const paperUrls = new Set([...topUrls, ...paperItems.map((item) => item.primary_url)]);
  const artifactItems = uniqueItems(
    run.sections.research_artifacts.filter((item) => !paperUrls.has(item.primary_url)),
  );
  const artifactUrls = new Set([...paperUrls, ...artifactItems.map((item) => item.primary_url)]);
  const updateItems = uniqueItems(
    run.sections.lab_company_updates.filter((item) => !artifactUrls.has(item.primary_url)),
  );
  const updateUrls = new Set([...artifactUrls, ...updateItems.map((item) => item.primary_url)]);
  const watchlistItems = uniqueItems(
    run.sections.watchlist.filter((item) => !updateUrls.has(item.primary_url)),
  );

  return (
    <article className="border-t border-border pt-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-text-subtle">
            <span className="text-accent">{formatDate(run.run_date)}</span>
            {run.window_start && run.window_end && (
              <span className="normal-case tracking-normal text-text-subtle">
                {formatShortDate(run.window_start)} to {formatShortDate(run.window_end)}
              </span>
            )}
          </div>
          <h2
            className={
              prominent
                ? "mt-1 text-xl font-semibold tracking-tight text-text"
                : "mt-1 text-lg font-semibold tracking-tight text-text"
            }
          >
            {run.title || "Research run"}
          </h2>
          {run.summary && (
            <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-text-muted">
              {run.summary}
            </p>
          )}
        </div>
        {run.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 sm:max-w-[360px] sm:justify-end">
            {run.sources.map((source) => (
              <span
                key={`${run.id}-${source.slug}`}
                className="rounded-md border border-border bg-surface px-2 py-1 text-[11px] font-medium text-text-subtle"
              >
                {source.label}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-5 space-y-6">
        <SectionList title="Top 5 items" icon="top" items={topItems} />
        <SectionList title="Papers worth reading" icon="papers" items={paperItems} />
        <SectionList title="Research artifacts" icon="artifacts" items={artifactItems} />
        <SectionList title="Lab/company updates" icon="updates" items={updateItems} />
        <SectionList title="Watchlist" icon="watchlist" items={watchlistItems} />
        {run.sections.skipped_noise_note && (
          <div className="rounded-md border border-border bg-surface/50 px-3 py-2 text-[12px] leading-relaxed text-text-subtle">
            <span className="font-semibold uppercase tracking-[0.12em] text-text-muted">
              Skipped/noise note
            </span>
            <span className="ml-2">{run.sections.skipped_noise_note}</span>
          </div>
        )}
      </div>
    </article>
  );
}

function SectionList({
  title,
  icon,
  items,
}: {
  title: string;
  icon: "top" | "papers" | "artifacts" | "updates" | "watchlist";
  items: ResearchBriefItem[];
}) {
  const Icon = iconMap[icon];
  return (
    <section>
      <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        <Icon className="h-3.5 w-3.5 text-accent" />
        <span>{title}</span>
        <span className="rounded-sm bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] tracking-normal text-text-muted">
          {items.length}
        </span>
      </div>
      {items.length > 0 ? (
        <ul className="space-y-2">
          {items.map((item, index) => (
            <ResearchItemRow key={`${item.primary_url}-${index}`} item={item} />
          ))}
        </ul>
      ) : (
        <div className="rounded-md border border-border bg-surface/40 px-3 py-2 text-[12px] text-text-subtle">
          No items selected for this run.
        </div>
      )}
    </section>
  );
}

function ResearchItemRow({ item }: { item: ResearchBriefItem }) {
  return (
    <li className="rounded-lg border border-border bg-surface/60 px-3 py-3 transition-colors hover:border-border-strong sm:px-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium uppercase tracking-[0.13em] text-text-subtle">
            <span className="text-accent">{itemTypeLabel(item.item_type)}</span>
            <span className="normal-case tracking-normal text-text-muted">{item.source_lab}</span>
            {item.published_at && (
              <span className="normal-case tracking-normal text-text-subtle">
                {formatShortDate(item.published_at)}
              </span>
            )}
          </div>
          <h3 className="mt-1 text-[15px] font-semibold leading-snug text-text">
            <a
              href={item.primary_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-w-0 items-start gap-1.5 break-words transition-colors hover:text-accent"
            >
              {item.title}
              <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" />
            </a>
          </h3>
        </div>
        {item.secondary_urls.length > 0 && (
          <div className="flex shrink-0 flex-wrap gap-1.5 sm:justify-end">
            {item.secondary_urls.map((url) => (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-8 items-center gap-1 rounded-md border border-border bg-surface-2 px-2 text-[11px] font-medium text-text-muted transition-colors hover:border-accent hover:text-accent"
              >
                Source
                <ArrowUpRight className="h-3 w-3" />
              </a>
            ))}
          </div>
        )}
      </div>
      <dl className="mt-3 grid grid-cols-1 gap-2 text-[12px] leading-relaxed text-text-muted md:grid-cols-2">
        <ItemDetail label="Takeaway" value={item.takeaway} />
        <ItemDetail label="Why it matters" value={item.why_it_matters} />
        <ItemDetail label="Evidence" value={item.evidence_quality} />
        <ItemDetail label="Caveats" value={item.limitations} />
      </dl>
    </li>
  );
}

function ItemDetail({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
        {label}
      </dt>
      <dd className="mt-0.5">{value}</dd>
    </div>
  );
}

const iconMap = {
  top: Beaker,
  papers: BookOpenText,
  artifacts: Boxes,
  updates: FileText,
  watchlist: Microscope,
};

function itemTypeLabel(type: ResearchItemType): string {
  return type.replace(/_/g, " ");
}

function uniqueItems(items: ResearchBriefItem[]): ResearchBriefItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.primary_url)) return false;
    seen.add(item.primary_url);
    return true;
  });
}

function formatDate(value: string): string {
  const d = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat("en-AU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

function formatShortDate(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value.slice(0, 10);
  return d.toISOString().slice(0, 10);
}
