"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";

import { cn } from "@/lib/cn";

const NAV_ITEMS: { href: string; label: string }[] = [
  { href: "/map", label: "Map" },
  { href: "/companies", label: "Companies" },
  { href: "/news", label: "News" },
  { href: "/research", label: "Research" },
  { href: "/about", label: "About" },
];

export function Header() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    const onPointerDown = (event: MouseEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [menuOpen]);

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-3 px-4 sm:gap-6 sm:px-5">
        <Link
          href="/"
          className="group flex min-w-0 items-baseline gap-2 text-text"
          aria-label="AI Sector Watch home"
        >
          <span className="truncate text-[15px] font-semibold leading-none tracking-tight">
            AI <span className="text-accent">Sector</span> Watch
          </span>
          <span className="hidden sm:inline text-[10px] font-medium uppercase tracking-[0.14em] text-text-subtle">
            ANZ
          </span>
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-1 sm:flex">
          {NAV_ITEMS.map((item) => {
            const active =
              pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors",
                  "text-text-muted hover:text-text hover:bg-surface",
                  active && "text-accent bg-accent-soft hover:bg-accent-soft hover:text-accent",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden md:flex items-center gap-2 text-[11px] text-text-subtle">
          <span className="aisw-pulse inline-block h-1.5 w-1.5 rounded-full bg-success" />
          <span>Live, updated weekly</span>
        </div>

        <div className="relative sm:hidden" ref={panelRef}>
          <button
            type="button"
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
            className="grid h-10 w-10 place-items-center rounded-md border border-border bg-surface text-text-muted transition-colors hover:border-border-strong hover:text-text"
          >
            {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>

          {menuOpen && (
            <nav
              aria-label="Mobile primary"
              className="absolute right-0 top-12 w-[calc(100vw-2rem)] max-w-[280px] rounded-lg border border-border bg-surface p-1.5 shadow-2xl"
            >
              {NAV_ITEMS.map((item) => {
                const active =
                  pathname === item.href ||
                  (item.href !== "/" && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex min-h-11 items-center rounded-md px-3 text-[14px] font-medium transition-colors",
                      "text-text-muted hover:bg-surface-2 hover:text-text",
                      active &&
                        "bg-accent-soft text-accent hover:bg-accent-soft hover:text-accent",
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
              <div className="mt-1 flex min-h-10 items-center gap-2 border-t border-border px-3 pt-2 text-[11px] text-text-subtle">
                <span className="aisw-pulse inline-block h-1.5 w-1.5 rounded-full bg-success" />
                <span>Live, updated weekly</span>
              </div>
            </nav>
          )}
        </div>
      </div>
    </header>
  );
}
