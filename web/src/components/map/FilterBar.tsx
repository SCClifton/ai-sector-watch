"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, RotateCcw, Search } from "lucide-react";

import { cn } from "@/lib/cn";
import { SECTORS, STAGE_LABELS, STAGES } from "@/lib/taxonomy";
import {
  EMPTY_FILTERS,
  type FilterMeta,
  type FilterState,
  isFilterActive,
} from "@/lib/filters";

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
        {isFilterActive(state) && (
          <button
            type="button"
            onClick={() => onChange(EMPTY_FILTERS)}
            className="inline-flex items-center gap-1 rounded-md border border-border-strong bg-surface-2 px-2.5 py-1.5 text-[12px] font-medium text-text-muted transition-colors hover:border-accent hover:text-accent"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
        )}
      </div>
    </div>
  );
}

function SearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="flex min-w-[200px] flex-1 items-center gap-2 rounded-md border border-border bg-surface-2 px-2.5 py-1.5 focus-within:border-accent">
      <Search className="h-3.5 w-3.5 text-text-subtle" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search by name..."
        className="w-full bg-transparent text-[13px] text-text outline-none placeholder:text-text-subtle"
      />
    </label>
  );
}

interface Option {
  value: string;
  label: string;
}

function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((s) => s !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  const summary =
    selected.length === 0
      ? label
      : selected.length === 1
        ? (options.find((o) => o.value === selected[0])?.label ?? selected[0])
        : `${label}: ${selected.length}`;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[13px] font-medium transition-colors",
          selected.length > 0
            ? "border-accent bg-accent-soft text-accent"
            : "border-border bg-surface-2 text-text-muted hover:border-border-strong hover:text-text",
        )}
      >
        {summary}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>

      {open && options.length > 0 && (
        <div className="aisw-scroll absolute left-0 top-full z-20 mt-1 max-h-[280px] w-[260px] overflow-y-auto rounded-md border border-border bg-surface shadow-2xl">
          <ul role="listbox" aria-multiselectable="true" className="py-1">
            {options.map((opt) => {
              const checked = selected.includes(opt.value);
              return (
                <li key={opt.value}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={checked}
                    onClick={() => toggle(opt.value)}
                    className={cn(
                      "flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left text-[13px] transition-colors",
                      checked
                        ? "text-accent hover:bg-accent-soft"
                        : "text-text hover:bg-surface-2",
                    )}
                  >
                    <span className="truncate">{opt.label}</span>
                    {checked && <Check className="h-3.5 w-3.5 shrink-0" />}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

function YearRange({
  meta,
  min,
  max,
  onChange,
}: {
  meta: FilterMeta;
  min: number | null;
  max: number | null;
  onChange: (min: number | null, max: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const active = min !== null || max !== null;
  const summary = active ? `Founded: ${min ?? meta.foundedMin} - ${max ?? meta.foundedMax}` : "Founded";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[13px] font-medium transition-colors",
          active
            ? "border-accent bg-accent-soft text-accent"
            : "border-border bg-surface-2 text-text-muted hover:border-border-strong hover:text-text",
        )}
      >
        {summary}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 w-[260px] rounded-md border border-border bg-surface p-3 shadow-2xl">
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="From"
              value={min ?? meta.foundedMin}
              min={meta.foundedMin}
              max={meta.foundedMax}
              onChange={(v) => onChange(v, max)}
            />
            <NumberField
              label="To"
              value={max ?? meta.foundedMax}
              min={meta.foundedMin}
              max={meta.foundedMax}
              onChange={(v) => onChange(min, v)}
            />
          </div>
          {active && (
            <button
              type="button"
              onClick={() => onChange(null, null)}
              className="mt-2 inline-flex items-center gap-1 text-[12px] text-text-muted hover:text-accent"
            >
              <RotateCcw className="h-3 w-3" />
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (next: number | null) => void;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-subtle">
        {label}
      </span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const n = Number(e.target.value);
          onChange(Number.isFinite(n) ? n : null);
        }}
        className="mt-1 w-full rounded-md border border-border bg-surface-2 px-2 py-1 text-[13px] text-text outline-none focus:border-accent"
      />
    </label>
  );
}
