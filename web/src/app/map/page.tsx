"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { Map } from "@/components/map/Map";
import { FilterBar } from "@/components/map/FilterBar";
import { CompanyDetail } from "@/components/map/CompanyDetail";
import {
  applyFilters,
  deriveMeta,
  filtersToParams,
  paramsToFilters,
} from "@/lib/filters";
import type { Company } from "@/lib/types";

export default function MapPage() {
  return (
    <Suspense fallback={<MapShell />}>
      <MapView />
    </Suspense>
  );
}

function MapShell() {
  return (
    <div className="relative flex flex-1 overflow-hidden">
      <div className="relative flex-1 bg-bg" />
    </div>
  );
}

function MapView() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Load companies once on mount.
  useEffect(() => {
    let cancelled = false;
    fetch("/api/companies")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return (await res.json()) as { companies: Company[] };
      })
      .then((data) => {
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
  const state = useMemo(
    () => paramsToFilters(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );

  const filtered = useMemo(
    () => applyFilters(companies ?? [], state),
    [companies, state],
  );

  const setState = useCallback(
    (next: Parameters<typeof filtersToParams>[0]) => {
      const params = filtersToParams(next);
      const qs = params.toString();
      router.replace(qs ? `/map?${qs}` : "/map", { scroll: false });
    },
    [router],
  );

  const selected = useMemo(
    () => (selectedId ? (companies ?? []).find((c) => c.id === selectedId) ?? null : null),
    [selectedId, companies],
  );

  return (
    <div className="relative flex flex-1 overflow-hidden">
      <div className="relative flex-1">
        <Map
          companies={filtered}
          selectedId={selectedId}
          onSelect={(id) => setSelectedId(id)}
        />

        <FilterBar
          state={state}
          meta={meta}
          onChange={setState}
          visibleCount={filtered.length}
          totalCount={companies?.length ?? 0}
        />

        {error && (
          <div className="pointer-events-auto absolute inset-x-0 bottom-3 mx-auto w-fit rounded-md border border-error/40 bg-surface px-3 py-2 text-[12px] text-error shadow-lg">
            Failed to load companies: {error}
          </div>
        )}
        {!error && companies === null && <LoadingOverlay />}
        {!error && companies !== null && companies.length === 0 && (
          <div className="absolute inset-x-0 bottom-3 mx-auto w-fit rounded-md border border-border bg-surface px-3 py-2 text-[12px] text-text-muted shadow-lg">
            No verified companies returned.
          </div>
        )}
        {!error &&
          companies !== null &&
          companies.length > 0 &&
          filtered.length === 0 && (
            <div className="pointer-events-none absolute inset-0 grid place-items-center">
              <div className="pointer-events-auto rounded-xl border border-border bg-surface/95 px-5 py-4 text-center shadow-2xl backdrop-blur-md">
                <div className="text-[13px] font-semibold text-text">No companies match</div>
                <p className="mt-1 max-w-[260px] text-[12px] text-text-muted">
                  Try clearing a filter, or hit Reset to see all {companies.length} verified
                  companies.
                </p>
              </div>
            </div>
          )}

        <CompanyDetail company={selected} onClose={() => setSelectedId(null)} />
      </div>
    </div>
  );
}

function LoadingOverlay() {
  return (
    <div className="pointer-events-none absolute inset-0 grid place-items-center bg-bg/60 backdrop-blur-sm">
      <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-[12px] text-text-muted">
        <span className="aisw-pulse h-1.5 w-1.5 rounded-full bg-accent" />
        Loading companies...
      </div>
    </div>
  );
}
