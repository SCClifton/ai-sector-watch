"use client";

import { useState } from "react";
import { SlidersHorizontal } from "lucide-react";

import { SECTORS, STAGE_LABELS, STAGES } from "@/lib/taxonomy";
import {
  EMPTY_FILTERS,
  type FilterMeta,
  type FilterState,
  isFilterActive,
} from "@/lib/filters";
import { FRESHNESS_OPTIONS, type FreshnessFlag } from "@/lib/freshness";
import {
  MobileCheckboxGroup,
  MobileFilterSheet,
  MobileYearFields,
  MultiSelect,
  ResetButton,
  SearchInput,
  YearRange,
} from "@/components/filters/primitives";

interface Props {
  state: FilterState;
  meta: FilterMeta;
  onChange: (next: FilterState) => void;
  visibleCount: number;
  totalCount: number;
}

export function FilterBar({ state, meta, onChange, visibleCount, totalCount }: Props) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const active = isFilterActive(state);

  return (
    <>
      <div className="absolute left-3 right-3 top-3 z-10 hidden flex-wrap items-center gap-2 rounded-xl border border-border bg-surface/95 px-3 py-2 shadow-lg backdrop-blur-md md:right-auto md:flex md:max-w-[860px]">
        <SearchInput
          value={state.nameQuery}
          onChange={(nameQuery) => onChange({ ...state, nameQuery })}
        />

        <MultiSelect
          label="Sector"
          options={SECTORS.map((s) => ({ value: s.tag, label: s.label }))}
          selected={state.sectors}
          onChange={(sectors) => onChange({ ...state, sectors })}
        />

        <MultiSelect
          label="Stage"
          options={STAGES.map((s) => ({ value: s, label: STAGE_LABELS[s] }))}
          selected={state.stages}
          onChange={(stages) => onChange({ ...state, stages })}
        />

        <MultiSelect
          label="Country"
          options={meta.countries.map((c) => ({ value: c, label: c }))}
          selected={state.countries}
          onChange={(countries) => onChange({ ...state, countries })}
        />

        <MultiSelect
          label="Freshness"
          options={FRESHNESS_OPTIONS}
          selected={state.freshness}
          onChange={(values) =>
            onChange({ ...state, freshness: values as FreshnessFlag[] })
          }
        />

        <YearRange
          meta={meta}
          min={state.foundedMin}
          max={state.foundedMax}
          onChange={(foundedMin, foundedMax) =>
            onChange({ ...state, foundedMin, foundedMax })
          }
        />

        <div className="ml-auto flex items-center gap-2 pl-2">
          <span className="hidden text-[11px] text-text-muted sm:inline">
            <span className="font-semibold text-text">{visibleCount}</span>
            <span> of {totalCount}</span>
          </span>
          {active && <ResetButton onClick={() => onChange(EMPTY_FILTERS)} />}
        </div>
      </div>

      <div className="absolute inset-x-3 top-3 z-10 md:hidden">
        <SearchInput
          value={state.nameQuery}
          onChange={(nameQuery) => onChange({ ...state, nameQuery })}
          className="min-h-11 min-w-0 rounded-lg bg-surface/95 shadow-lg backdrop-blur-md"
        />
      </div>

      <div className="absolute inset-x-3 bottom-3 z-10 flex items-center gap-2 rounded-xl border border-border bg-surface/95 p-2 shadow-2xl backdrop-blur-md md:hidden">
        <div className="min-w-0 flex-1 px-1">
          <div className="font-mono text-[15px] font-semibold tabular-nums text-text">
            {visibleCount}
          </div>
          <div className="truncate text-[11px] text-text-muted">of {totalCount} companies</div>
        </div>
        {active && (
          <ResetButton
            onClick={() => onChange(EMPTY_FILTERS)}
            className="min-h-10 px-3"
          />
        )}
        <button
          type="button"
          onClick={() => setFiltersOpen(true)}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-md bg-accent px-3 text-[13px] font-semibold text-bg transition-colors hover:bg-accent-hover"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          Filters
        </button>
      </div>

      <MobileFilterSheet
        open={filtersOpen}
        title="Map filters"
        summary={`${visibleCount} of ${totalCount} companies visible`}
        onClose={() => setFiltersOpen(false)}
      >
        <MobileCheckboxGroup
          label="Sector"
          options={SECTORS.map((s) => ({ value: s.tag, label: s.label }))}
          selected={state.sectors}
          onChange={(sectors) => onChange({ ...state, sectors })}
        />

        <MobileCheckboxGroup
          label="Stage"
          options={STAGES.map((s) => ({ value: s, label: STAGE_LABELS[s] }))}
          selected={state.stages}
          onChange={(stages) => onChange({ ...state, stages })}
        />

        <MobileCheckboxGroup
          label="Country"
          options={meta.countries.map((c) => ({ value: c, label: c }))}
          selected={state.countries}
          onChange={(countries) => onChange({ ...state, countries })}
        />

        <MobileCheckboxGroup
          label="Freshness"
          options={FRESHNESS_OPTIONS}
          selected={state.freshness}
          onChange={(values) =>
            onChange({ ...state, freshness: values as FreshnessFlag[] })
          }
        />

        <MobileYearFields
          meta={meta}
          min={state.foundedMin}
          max={state.foundedMax}
          onChange={(foundedMin, foundedMax) =>
            onChange({ ...state, foundedMin, foundedMax })
          }
        />
      </MobileFilterSheet>
    </>
  );
}
