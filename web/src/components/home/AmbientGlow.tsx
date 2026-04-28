"use client";

import { useEffect, useRef } from "react";

export function AmbientGlow() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      el.style.setProperty("--aisw-mx", `${x}%`);
      el.style.setProperty("--aisw-my", `${y}%`);
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  return (
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10"
      style={{
        background: `
          radial-gradient(800px circle at var(--aisw-mx, 30%) var(--aisw-my, 20%), rgba(244,183,64,0.10), transparent 55%),
          radial-gradient(600px circle at 85% 12%, rgba(79,141,255,0.07), transparent 55%),
          radial-gradient(500px circle at 12% 85%, rgba(244,113,113,0.05), transparent 55%)
        `,
      }}
    />
  );
}
