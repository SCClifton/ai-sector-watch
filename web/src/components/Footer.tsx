"use client";

import { usePathname } from "next/navigation";

export function Footer() {
  const pathname = usePathname();

  if (pathname === "/map") return null;

  return (
    <footer className="border-t border-border bg-bg">
      <div className="mx-auto flex max-w-[1400px] flex-col items-center justify-between gap-2 px-5 py-4 text-center text-[11px] text-text-subtle sm:flex-row sm:text-left">
        <p className="max-w-[34rem] sm:max-w-none">
          AI Sector Watch &middot; Independent ANZ AI ecosystem map &middot; Updated weekly by an
          automated pipeline
        </p>
        <p className="text-text-muted">
          Prototype build &middot;{" "}
          <span className="font-mono text-text-subtle">v0.1 spike</span>
        </p>
      </div>
    </footer>
  );
}
