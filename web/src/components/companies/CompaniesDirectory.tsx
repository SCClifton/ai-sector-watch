"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowDown, ArrowUp, ArrowUpDown, ExternalLink } from "lucide-react";

import { CompaniesFilterBar } from "./CompaniesFilterBar";
import {
  applyFilters,
  deriveMeta,
  filtersToParams,
  paramsToFilters,
} from "@/lib/filters";
import { primarySectorHex, sectorLabel } from "@/lib/taxonomy";
import { formatStage } from "@/lib/format";
import { slugFor } from "@/lib/slug";
import { cn } from "@/lib/cn";
import type { Company } from "@/lib/types";

type SortKey = "name" | "founded";
type SortDir = "asc" | "desc";
const SORT_KEYS: SortKey[] = ["name", "founded"];

export function CompaniesDirectory() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/companies")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: { companies: Company[] }) => {
        if (!cancelled) setCompanies(data.companies);
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const meta = useMemo(() => deriveMeta(companies ?? []), [companies]);
  const filterState = useMemo(
    () => paramsToFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );
  const requestedSort = searchParams.get("sort");
  const sortKey = SORT_KEYS.includes(requestedSort as SortKey)
    ? (requestedSort as SortKey)
    : "name";
  const sortDir = (searchParams.get("dir") as SortDir) || "asc";

  const filtered = useMemo(
    () => applyFilters(companies ?? [], filterState),
    [companies, filterState],
  );

  const sorted = useMemo(() => sortCompanies(filtered, sortKey, sortDir), [filtered, sortKey, sortDir]);

  const updateUrl = useCallback(
    (overrides: { state?: typeof filterState; sort?: SortKey; dir?: SortDir }) => {
      const next = filtersToParams(overrides.state ?? filterState);
      const finalSort = overrides.sort ?? sortKey;
      const finalDir = overrides.dir ?? sortDir;
      if (finalSort !== "name") next.set("sort", finalSort);
      if (finalDir !== "asc") next.set("dir", finalDir);
      const qs = next.toString();
      router.replace(qs ? `/companies?${qs}` : "/companies", { scroll: false });
    },
    [filterState, sortKey, sortDir, router],
  );

  const onSort = useCallback(
    (key: SortKey) => {
      const nextDir: SortDir = sortKey === key ? (sortDir === "asc" ? "desc" : "asc") : "asc";
      updateUrl({ sort: key, dir: nextDir });
    },
    [sortKey, sortDir, updateUrl],
  );

  return (
    <section className="mx-auto w-full max-w-[1200px] px-5 py-10">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
            Browse
          </div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-text sm:text-4xl">
            Companies
          </h1>
          <p className="mt-2 text-[14px] text-text-muted">
            Every verified ANZ AI startup we track. Filter, sort, and click through to a profile.
          </p>
        </div>
        <div className="text-[12px] text-text-muted">
          <span className="font-mono tabular-nums text-text">{sorted.length}</span>
          {companies && (
            <span>
              {" "}
              of <span className="font-mono tabular-nums">{companies.length}</span> companies
            </span>
          )}
        </div>
      </div>

      <div className="mt-5">
        <CompaniesFilterBar
          state={filterState}
          meta={meta}
          onChange={(next) => updateUrl({ state: next })}
        />
      </div>

      {error && (
        <div className="mt-6 rounded-md border border-error/40 bg-surface px-4 py-3 text-[13px] text-error">
          Failed to load companies: {error}
        </div>
      )}

      {!error && companies === null && (
        <div className="mt-6 rounded-md border border-border bg-surface px-4 py-3 text-[13px] text-text-muted">
          Loading companies...
        </div>
      )}

      {!error && companies !== null && sorted.length === 0 && (
        <div className="mt-6 rounded-md border border-border bg-surface px-4 py-8 text-center text-[13px] text-text-muted">
          No companies match the current filters.
        </div>
      )}

      {!error && sorted.length > 0 && (
        <>
          {/* Desktop table */}
          <div className="aisw-scroll mt-5 hidden overflow-x-auto rounded-xl border border-border bg-surface/40 lg:block">
            <table className="w-full text-[13px]">
              <thead className="border-b border-border text-text-muted">
                <tr className="text-left">
                  <SortableTh label="Name" active={sortKey} dir={sortDir} field="name" onSort={onSort} />
                  <th className="px-4 py-2 font-medium">Stage</th>
                  <SortableTh label="Founded" active={sortKey} dir={sortDir} field="founded" onSort={onSort} />
                  <th className="px-4 py-2 font-medium">Sectors</th>
                  <th className="px-4 py-2 font-medium">Location</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((c) => {
                  const slug = slugFor(c, companies ?? [c]);
                  const accent = primarySectorHex(c.sector_tags);
                  return (
                    <tr
                      key={c.id}
                      className="border-b border-border last:border-0 transition-colors hover:bg-surface/80"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span
                            className="h-2 w-2 shrink-0 rounded-full"
                            style={{ background: accent }}
                            aria-hidden
                          />
                          <Link
                            href={`/companies/${slug}`}
                            className="font-semibold text-text hover:text-accent"
                          >
                            {c.name}
                          </Link>
                          {c.website && (
                            <a
                              href={c.website}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-text-muted hover:text-accent"
                              aria-label={`${c.name} website`}
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-text-muted">{formatStage(c.stage) ?? "-"}</td>
                      <td className="px-4 py-3 text-text-muted tabular-nums">
                        {c.founded_year ?? "-"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {c.sector_tags.slice(0, 2).map((tag) => (
                            <span
                              key={tag}
                              className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-muted"
                            >
                              {sectorLabel(tag)}
                            </span>
                          ))}
                          {c.sector_tags.length > 2 && (
                            <span className="text-[11px] text-text-subtle">
                              +{c.sector_tags.length - 2}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-text-muted">
                        {[c.city, c.country].filter(Boolean).join(", ") || "-"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile / tablet cards */}
          <ul className="mt-5 grid grid-cols-1 gap-3 lg:hidden sm:grid-cols-2">
            {sorted.map((c) => {
              const slug = slugFor(c, companies ?? [c]);
              const accent = primarySectorHex(c.sector_tags);
              return (
                <li key={c.id} className="overflow-hidden rounded-xl border border-border bg-surface">
                  <div className="h-1 w-full" style={{ background: accent }} aria-hidden />
                  <Link href={`/companies/${slug}`} className="block px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-[15px] font-semibold text-text">{c.name}</h3>
                      <span className="text-[11px] text-text-subtle whitespace-nowrap">
                        {[c.city, c.country].filter(Boolean).join(", ")}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-text-muted tabular-nums">
                      {formatStage(c.stage) && <span>{formatStage(c.stage)}</span>}
                      {c.founded_year !== null && <span>Founded {c.founded_year}</span>}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1">
                      {c.sector_tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-muted"
                        >
                          {sectorLabel(tag)}
                        </span>
                      ))}
                      {c.sector_tags.length > 3 && (
                        <span className="text-[11px] text-text-subtle">
                          +{c.sector_tags.length - 3}
                        </span>
                      )}
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}

function SortableTh({
  label,
  active,
  dir,
  field,
  onSort,
}: {
  label: string;
  active: SortKey;
  dir: SortDir;
  field: SortKey;
  onSort: (k: SortKey) => void;
}) {
  const isActive = active === field;
  const Icon = !isActive ? ArrowUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className="px-4 py-2 font-medium">
      <button
        type="button"
        onClick={() => onSort(field)}
        className={cn(
          "inline-flex items-center gap-1 transition-colors",
          isActive ? "text-text" : "text-text-muted hover:text-text",
        )}
      >
        {label}
        <Icon className="h-3 w-3" />
      </button>
    </th>
  );
}

function sortCompanies(items: Company[], key: SortKey, dir: SortDir): Company[] {
  const mult = dir === "asc" ? 1 : -1;
  const cmpNullable = (a: number | null, b: number | null): number => {
    if (a === null && b === null) return 0;
    if (a === null) return 1; // nulls last
    if (b === null) return -1;
    return a - b;
  };

  const sorted = [...items];
  switch (key) {
    case "founded":
      sorted.sort((a, b) => mult * cmpNullable(a.founded_year, b.founded_year));
      break;
    case "name":
    default:
      sorted.sort((a, b) => mult * a.name.localeCompare(b.name));
  }
  return sorted;
}
