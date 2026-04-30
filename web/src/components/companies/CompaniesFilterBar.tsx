"use client";

import { SECTORS, STAGE_LABELS, STAGES } from "@/lib/taxonomy";
import {
  EMPTY_FILTERS,
  type FilterMeta,
  type FilterState,
  isFilterActive,
} from "@/lib/filters";
import { FRESHNESS_OPTIONS, type FreshnessFlag } from "@/lib/freshness";
import {
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
  const sortValue = `${sortKey}:${sortDir}`;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface/60 px-3 py-2.5">
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

      {isFilterActive(state) && (
        <div className="ml-auto">
          <ResetButton onClick={() => onChange(EMPTY_FILTERS)} />
        </div>
      )}
    </div>
  );
}
