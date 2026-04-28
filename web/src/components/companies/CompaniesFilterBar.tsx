"use client";

import { SECTORS, STAGE_LABELS, STAGES } from "@/lib/taxonomy";
import {
  EMPTY_FILTERS,
  type FilterMeta,
  type FilterState,
  isFilterActive,
} from "@/lib/filters";
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
}

export function CompaniesFilterBar({ state, meta, onChange }: Props) {
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

      <YearRange
        meta={meta}
        min={state.foundedMin}
        max={state.foundedMax}
        onChange={(foundedMin, foundedMax) =>
          onChange({ ...state, foundedMin, foundedMax })
        }
      />

      {isFilterActive(state) && (
        <div className="ml-auto">
          <ResetButton onClick={() => onChange(EMPTY_FILTERS)} />
        </div>
      )}
    </div>
  );
}
