"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { Check, ChevronDown, RotateCcw, Search, X } from "lucide-react";

import { cn } from "@/lib/cn";
import type { FilterMeta } from "@/lib/filters";

export interface Option {
  value: string;
  label: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search by name...",
  className,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <label
      className={cn(
        "flex min-w-[200px] flex-1 items-center gap-2 rounded-md border border-border bg-surface-2 px-2.5 py-1.5 focus-within:border-accent",
        className,
      )}
    >
      <Search className="h-3.5 w-3.5 text-text-subtle" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent text-[13px] text-text outline-none placeholder:text-text-subtle"
      />
    </label>
  );
}

export function MobileFilterSheet({
  open,
  title,
  summary,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  summary?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 md:hidden" role="presentation">
      <button
        type="button"
        aria-label="Close filters"
        onClick={onClose}
        className="absolute inset-0 bg-bg/65 backdrop-blur-sm"
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="aisw-scroll absolute inset-x-0 bottom-0 max-h-[82dvh] overflow-y-auto rounded-t-xl border-t border-border bg-surface shadow-2xl"
      >
        <div className="sticky top-0 z-10 border-b border-border bg-surface px-4 py-3">
          <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border-strong" aria-hidden />
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-[15px] font-semibold text-text">{title}</h2>
              {summary && <p className="mt-0.5 text-[12px] text-text-muted">{summary}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-md text-text-muted transition-colors hover:bg-surface-2 hover:text-text"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="space-y-5 px-4 py-4">{children}</div>
        <div className="sticky bottom-0 border-t border-border bg-surface px-4 py-3">
          <button
            type="button"
            onClick={onClose}
            className="h-11 w-full rounded-md bg-accent text-[14px] font-semibold text-bg transition-colors hover:bg-accent-hover"
          >
            Done
          </button>
        </div>
      </section>
    </div>
  );
}

export function MobileCheckboxGroup({
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
  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((item) => item !== value));
      return;
    }
    onChange([...selected, value]);
  };

  return (
    <fieldset>
      <legend className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        {label}
      </legend>
      <div className="mt-2 grid grid-cols-1 gap-2">
        {options.map((option) => {
          const checked = selected.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={checked}
              onClick={() => toggle(option.value)}
              className={cn(
                "flex min-h-11 w-full items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-[13px] transition-colors",
                checked
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-border bg-surface-2 text-text hover:border-border-strong",
              )}
            >
              <span className="min-w-0 break-words">{option.label}</span>
              {checked && <Check className="h-4 w-4 shrink-0" />}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export function MobileYearFields({
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
  const active = min !== null || max !== null;

  return (
    <fieldset>
      <legend className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
        Founded
      </legend>
      <div className="mt-2 grid grid-cols-2 gap-2">
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
          className="mt-2 inline-flex min-h-10 items-center gap-1 text-[12px] text-text-muted hover:text-accent"
        >
          <RotateCcw className="h-3 w-3" />
          Clear founded years
        </button>
      )}
    </fieldset>
  );
}

export function MultiSelect({
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

export function SingleSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Option[];
  onChange: (next: string) => void;
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

  const current = options.find((o) => o.value === value);
  const summary = current ? `${label}: ${current.label}` : label;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[13px] font-medium transition-colors",
          "border-border bg-surface-2 text-text-muted hover:border-border-strong hover:text-text",
        )}
      >
        {summary}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>

      {open && options.length > 0 && (
        <div className="aisw-scroll absolute right-0 top-full z-20 mt-1 max-h-[280px] w-[220px] overflow-y-auto rounded-md border border-border bg-surface shadow-2xl">
          <ul role="listbox" className="py-1">
            {options.map((opt) => {
              const checked = opt.value === value;
              return (
                <li key={opt.value}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={checked}
                    onClick={() => {
                      onChange(opt.value);
                      setOpen(false);
                    }}
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

export function YearRange({
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
  const summary = active
    ? `Founded: ${min ?? meta.foundedMin} - ${max ?? meta.foundedMax}`
    : "Founded";

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

export function ResetButton({
  onClick,
  className,
}: {
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-border-strong bg-surface-2 px-2.5 py-1.5 text-[12px] font-medium text-text-muted transition-colors hover:border-accent hover:text-accent",
        className,
      )}
    >
      <RotateCcw className="h-3 w-3" />
      Reset
    </button>
  );
}
