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
  return (
    <div className="absolute left-3 right-3 top-3 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface/95 px-3 py-2 shadow-lg backdrop-blur-md md:right-auto md:max-w-[760px]">
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
        {isFilterActive(state) && <ResetButton onClick={() => onChange(EMPTY_FILTERS)} />}
      </div>
    </div>
  );
}
