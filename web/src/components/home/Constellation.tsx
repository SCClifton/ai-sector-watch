"use client";

import Link from "next/link";
import { useState } from "react";

import type { Company } from "@/lib/types";

interface CityNode {
  key: string;
  label: string;
  country: "AU" | "NZ";
  x: number; // viewBox x in 0-800
  y: number; // viewBox y in 0-420
}

// Hand-tuned positions for visual balance  -  close to actual relative geography.
const CITIES: CityNode[] = [
  { key: "Perth", label: "Perth", country: "AU", x: 60, y: 220 },
  { key: "Adelaide", label: "Adelaide", country: "AU", x: 280, y: 260 },
  { key: "Melbourne", label: "Melbourne", country: "AU", x: 360, y: 300 },
  { key: "Hobart", label: "Hobart", country: "AU", x: 380, y: 380 },
  { key: "Canberra", label: "Canberra", country: "AU", x: 510, y: 270 },
  { key: "Sydney", label: "Sydney", country: "AU", x: 540, y: 220 },
  { key: "Brisbane", label: "Brisbane", country: "AU", x: 565, y: 140 },
  { key: "Auckland", label: "Auckland", country: "NZ", x: 720, y: 215 },
  { key: "Wellington", label: "Wellington", country: "NZ", x: 720, y: 290 },
  { key: "Christchurch", label: "Christchurch", country: "NZ", x: 695, y: 350 },
];

const CITY_BY_KEY = new Map(CITIES.map((c) => [c.key, c]));

// Constellation lines  -  visually pleasing, not geographically rigorous.
const EDGES: [string, string][] = [
  ["Perth", "Adelaide"],
  ["Adelaide", "Melbourne"],
  ["Melbourne", "Hobart"],
  ["Melbourne", "Canberra"],
  ["Canberra", "Sydney"],
  ["Sydney", "Brisbane"],
  ["Sydney", "Auckland"],
  ["Auckland", "Wellington"],
  ["Wellington", "Christchurch"],
];

interface Props {
  companies: Company[] | null;
}

export function Constellation({ companies }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);

  const counts = countByCity(companies);
  const maxCount = Math.max(1, ...Object.values(counts));

  return (
    <div className="relative mx-auto w-full max-w-[920px] overflow-hidden rounded-xl border border-border bg-surface/60 shadow-2xl">
      {/* Dotted grid background via repeating radial gradient. */}
      <div
        aria-hidden
        className="absolute inset-0 opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(230,237,243,0.07) 1px, transparent 1px)",
          backgroundSize: "22px 22px",
        }}
      />

      {/* Slow horizontal scan beam  -  the "high-tech" moment. */}
      <div aria-hidden className="aisw-scan pointer-events-none absolute inset-y-0 w-[180px]" />

      <svg
        viewBox="0 0 800 420"
        role="img"
        aria-label="Map of AI Sector Watch coverage across Australia and New Zealand"
        className="relative block w-full"
      >
        <defs>
          <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(244,183,64,0.55)" />
            <stop offset="100%" stopColor="rgba(244,183,64,0)" />
          </radialGradient>
          <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(244,183,64,0.10)" />
            <stop offset="50%" stopColor="rgba(244,183,64,0.32)" />
            <stop offset="100%" stopColor="rgba(244,183,64,0.10)" />
          </linearGradient>
        </defs>

        {/* Constellation edges */}
        <g>
          {EDGES.map(([aKey, bKey]) => {
            const a = CITY_BY_KEY.get(aKey);
            const b = CITY_BY_KEY.get(bKey);
            if (!a || !b) return null;
            const isCrossTasman =
              (a.country === "AU" && b.country === "NZ") ||
              (a.country === "NZ" && b.country === "AU");
            return (
              <line
                key={`${aKey}-${bKey}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="url(#lineGrad)"
                strokeWidth={isCrossTasman ? 0.6 : 0.9}
                strokeDasharray={isCrossTasman ? "3 4" : undefined}
                opacity={0.85}
              />
            );
          })}
        </g>

        {/* City nodes */}
        <g>
          {CITIES.map((city) => {
            const count = counts[city.label] ?? 0;
            const baseR = 4;
            const scaled = baseR + Math.sqrt(count / maxCount) * 8;
            const isHover = hovered === city.key;
            return (
              <g
                key={city.key}
                transform={`translate(${city.x} ${city.y})`}
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHovered(city.key)}
                onMouseLeave={() => setHovered(null)}
              >
                <circle r={scaled + 22} fill="url(#nodeGlow)" opacity={isHover ? 0.9 : 0.55} />
                <circle
                  r={scaled + 4}
                  fill="none"
                  stroke="rgba(244,183,64,0.55)"
                  strokeWidth={1}
                  className="aisw-pulse-ring"
                  style={{ animationDelay: `${(CITIES.indexOf(city) * 0.3) % 2.4}s` }}
                />
                <circle
                  r={scaled}
                  fill={count > 0 ? "#F4B740" : "#5C6675"}
                  stroke="#0B0F14"
                  strokeWidth={1.5}
                  style={{
                    filter: isHover
                      ? "drop-shadow(0 0 8px rgba(244,183,64,0.9))"
                      : "drop-shadow(0 0 0 transparent)",
                    transition: "filter 200ms ease",
                  }}
                />

                {/* Label appears on hover. Flips left when near the right edge. */}
                {isHover && (() => {
                  const lw = labelWidth(city.label, count);
                  const flipLeft = city.x + scaled + 10 + lw > 800 - 12;
                  const labelX = flipLeft ? -(scaled + 10 + lw) : scaled + 10;
                  const textX = labelX + 10;
                  return (
                    <g pointerEvents="none">
                      <rect
                        x={labelX}
                        y={-18}
                        width={lw}
                        height={36}
                        rx={6}
                        fill="rgba(18,24,33,0.96)"
                        stroke="rgba(244,183,64,0.45)"
                        strokeWidth={0.8}
                      />
                      <text
                        x={textX}
                        y={-2}
                        fill="#E6EDF3"
                        fontSize={11}
                        fontWeight={600}
                        style={{ letterSpacing: "0.01em" }}
                      >
                        {city.label}
                      </text>
                      <text
                        x={textX}
                        y={13}
                        fill="rgba(244,183,64,0.95)"
                        fontSize={10}
                        fontWeight={500}
                      >
                        {count} {count === 1 ? "company" : "companies"}
                      </text>
                    </g>
                  );
                })()}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Footer strip */}
      <div className="relative flex items-center justify-between gap-3 border-t border-border bg-bg/70 px-4 py-2.5 text-[11px] text-text-muted">
        <div className="flex items-center gap-2">
          <span className="aisw-pulse inline-block h-1.5 w-1.5 rounded-full bg-success" />
          Live, refreshed weekly from {Object.values(counts).reduce((a, b) => a + b, 0)} verified records
        </div>
        <Link
          href="/map"
          className="inline-flex items-center gap-1 font-medium text-accent transition-colors hover:text-accent-hover"
        >
          Explore the full map
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M5 12h14M13 5l7 7-7 7" />
          </svg>
        </Link>
      </div>
    </div>
  );
}

function countByCity(companies: Company[] | null): Record<string, number> {
  if (!companies) return {};
  const counts: Record<string, number> = {};
  for (const c of companies) {
    if (!c.city) continue;
    counts[c.city] = (counts[c.city] ?? 0) + 1;
  }
  return counts;
}

function labelWidth(name: string, count: number): number {
  const base = name.length * 6.5;
  const tail = String(count).length * 6.5 + 60;
  return Math.max(base, tail) + 18;
}
