"use client";

import { useState } from "react";
import { Check, SlidersHorizontal } from "lucide-react";

import { cn } from "@/lib/cn";
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
  SingleSelect,
  YearRange,
} from "@/components/filters/primitives";

type DirectorySortKey = "name" | "founded" | "verified" | "funded";
type SortDir = "asc" | "desc";

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "name:asc", label: "Name A to Z" },
  { value: "name:desc", label: "Name Z to A" },
  { value: "founded:desc", label: "Newest founded" },
  { value: "founded:asc", label: "Oldest founded" },
  { value: "verified:desc", label: "Recently verified" },
  { value: "funded:desc", label: "Recently funded" },
];

interface Props {
  state: FilterState;
  meta: FilterMeta;
  onChange: (next: FilterState) => void;
  sortKey: DirectorySortKey;
  sortDir: SortDir;
  onSortChange: (key: DirectorySortKey, dir: SortDir) => void;
}

export function CompaniesFilterBar({
  state,
  meta,
  onChange,
  sortKey,
  sortDir,
  onSortChange,
}: Props) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const sortValue = `${sortKey}:${sortDir}`;
  const active = isFilterActive(state);

  return (
    <>
      <div className="hidden flex-wrap items-center gap-2 rounded-xl border border-border bg-surface/60 px-3 py-2.5 md:flex">
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

        <SingleSelect
          label="Sort"
          value={sortValue}
          options={SORT_OPTIONS}
          onChange={(value) => {
            const [key, dir] = value.split(":") as [DirectorySortKey, SortDir];
            onSortChange(key, dir);
          }}
        />

        {active && (
          <div className="ml-auto">
            <ResetButton onClick={() => onChange(EMPTY_FILTERS)} />
          </div>
        )}
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 md:hidden">
        <SearchInput
          value={state.nameQuery}
          onChange={(nameQuery) => onChange({ ...state, nameQuery })}
          className="min-h-11 min-w-0"
        />
        <button
          type="button"
          onClick={() => setFiltersOpen(true)}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-md border border-border-strong bg-surface px-3 text-[13px] font-semibold text-text transition-colors hover:border-accent hover:text-accent"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          Filters
        </button>
        <div className="col-span-2 flex flex-wrap items-center gap-2">
          <MobileSortChoices
            value={sortValue}
            onChange={(value) => {
              const [key, dir] = value.split(":") as [DirectorySortKey, SortDir];
              onSortChange(key, dir);
            }}
          />
          {active && (
            <ResetButton
              onClick={() => onChange(EMPTY_FILTERS)}
              className="min-h-10"
            />
          )}
        </div>
      </div>

      <MobileFilterSheet
        open={filtersOpen}
        title="Company filters"
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

function MobileSortChoices({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="aisw-scroll -mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
      {SORT_OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              "inline-flex min-h-10 shrink-0 items-center gap-1 rounded-md border px-3 text-[12px] font-medium transition-colors",
              active
                ? "border-accent bg-accent-soft text-accent"
                : "border-border bg-surface text-text-muted hover:border-border-strong hover:text-text",
            )}
          >
            {active && <Check className="h-3 w-3" />}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
