"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/cn";

const NAV_ITEMS: { href: string; label: string }[] = [
  { href: "/map", label: "Map" },
  { href: "/companies", label: "Companies" },
  { href: "/news", label: "News" },
  { href: "/about", label: "About" },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-6 px-5">
        <Link
          href="/"
          className="group flex items-baseline gap-2 text-text"
          aria-label="AI Sector Watch home"
        >
          <span className="text-[15px] font-semibold leading-none tracking-tight">
            AI <span className="text-accent">Sector</span> Watch
          </span>
          <span className="hidden sm:inline text-[10px] font-medium uppercase tracking-[0.14em] text-text-subtle">
            ANZ
          </span>
        </Link>

        <nav aria-label="Primary" className="flex items-center gap-1">
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
      </div>
    </header>
  );
}
