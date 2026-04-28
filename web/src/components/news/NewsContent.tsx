"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Sparkles } from "lucide-react";

import type { Company, NewsItem } from "@/lib/types";
import { slugFor } from "@/lib/slug";

interface SpendSummary {
  total_usd: number;
  average_usd: number;
  run_count: number;
}

export function NewsContent() {
  const [items, setItems] = useState<NewsItem[] | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [spend, setSpend] = useState<SpendSummary | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch("/api/news?limit=100").then((r) => r.json()),
      fetch("/api/companies").then((r) => r.json()),
      fetch("/api/spend-summary").then((r) => r.json()),
    ])
      .then(([news, companiesRes, spendRes]) => {
        if (cancelled) return;
        setItems(news.items ?? []);
        setCompanies(companiesRes.companies ?? []);
        setSpend(spendRes.summary ?? null);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const companyById = useMemo(
    () => new Map(companies.map((c) => [c.id, c])),
    [companies],
  );

  return (
    <section className="mx-auto w-full max-w-[900px] px-5 py-10">
      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
        Pipeline
      </div>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-text sm:text-4xl">
        News
      </h1>
      <p className="mt-2 max-w-2xl text-[14px] text-text-muted">
        Funding, launches, hires, and partnerships from the most recent weekly pipeline
        runs. Headlines link to the original story; mention chips link to the company
        profile.
      </p>

      {spend && <SpendCard spend={spend} />}

      {loadError && (
        <div className="mt-6 rounded-md border border-error/40 bg-surface px-4 py-3 text-[13px] text-error">
          Failed to load news: {loadError}
        </div>
      )}

      {!loadError && items === null && (
        <div className="mt-6 rounded-md border border-border bg-surface px-4 py-3 text-[13px] text-text-muted">
          Loading news...
        </div>
      )}

      {!loadError && items !== null && items.length === 0 && (
        <div className="mt-6 rounded-md border border-border bg-surface px-4 py-8 text-center text-[13px] text-text-muted">
          No news items yet. The pipeline runs weekly on Monday morning.
        </div>
      )}

      {!loadError && items && items.length > 0 && (
        <ul className="mt-6 space-y-3">
          {items.map((item) => (
            <NewsCard key={item.id} item={item} companyById={companyById} allCompanies={companies} />
          ))}
        </ul>
      )}
    </section>
  );
}

function SpendCard({ spend }: { spend: SpendSummary }) {
  return (
    <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-border bg-surface/60 px-4 py-3">
      <div className="flex items-center gap-2 text-[12px] font-medium uppercase tracking-[0.14em] text-text-subtle">
        <Sparkles className="h-3.5 w-3.5 text-accent" />
        Pipeline cost - last 4 weeks
      </div>
      <div className="flex items-baseline gap-1.5 font-mono text-[13px] text-text-muted">
        <span className="text-[18px] font-semibold tabular-nums text-text">
          {formatUsd(spend.total_usd)}
        </span>
        <span>total</span>
      </div>
      <div className="flex items-baseline gap-1.5 font-mono text-[13px] text-text-muted">
        <span className="text-[15px] font-semibold tabular-nums text-text">
          {formatUsd(spend.average_usd)}
        </span>
        <span>per run avg</span>
      </div>
      <div className="flex items-baseline gap-1.5 font-mono text-[13px] text-text-muted">
        <span className="text-[15px] font-semibold tabular-nums text-text">
          {spend.run_count}
        </span>
        <span>runs</span>
      </div>
    </div>
  );
}

function NewsCard({
  item,
  companyById,
  allCompanies,
}: {
  item: NewsItem;
  companyById: Map<string, Company>;
  allCompanies: Company[];
}) {
  const date = item.published_at ? formatDate(item.published_at) : null;
  const mentions = item.company_ids
    .map((id) => companyById.get(id))
    .filter((c): c is Company => Boolean(c));

  return (
    <li className="rounded-xl border border-border bg-surface/60 transition-colors hover:border-border-strong">
      <div className="px-5 py-4">
        <div className="flex flex-wrap items-baseline gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-text-subtle">
          <span className="text-accent">{item.kind}</span>
          {date && <span className="text-text-muted normal-case tracking-normal">{date}</span>}
          <span className="text-text-subtle normal-case tracking-normal">
            via {item.source_slug}
          </span>
        </div>
        <h2 className="mt-2 text-[16px] font-semibold leading-snug text-text">
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-start gap-1.5 text-text transition-colors hover:text-accent"
          >
            {item.title}
            <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" />
          </a>
        </h2>
        {item.summary && (
          <p className="mt-2 text-[13px] leading-relaxed text-text-muted">
            {cleanSummary(item.summary)}
          </p>
        )}
        {mentions.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-text-subtle">
              Mentions
            </span>
            {mentions.map((c) => {
              const slug = slugFor(c, allCompanies);
              return (
                <Link
                  key={c.id}
                  href={`/companies/${slug}`}
                  className="rounded-md border border-border bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-text transition-colors hover:border-accent hover:text-accent"
                >
                  {c.name}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </li>
  );
}

function cleanSummary(raw: string): string {
  // Strip HTML tags and decode common entities. The pipeline sometimes ingests
  // raw RSS HTML; we keep the text but drop the markup.
  const stripped = raw
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#(\d+);/g, (_m, code) => String.fromCharCode(Number(code)))
    .replace(/\s+/g, " ")
    .trim();
  return stripped.length > 320 ? `${stripped.slice(0, 320).trimEnd()}...` : stripped;
}

function formatUsd(amount: number): string {
  if (amount < 1) return `$${amount.toFixed(2)}`;
  if (amount < 10) return `$${amount.toFixed(2)}`;
  if (amount < 100) return `$${amount.toFixed(1)}`;
  return `$${Math.round(amount)}`;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
    if (diffDays === 0) return "today";
    if (diffDays === 1) return "yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return d.toISOString().slice(0, 10);
  } catch {
    return iso.slice(0, 10);
  }
}
