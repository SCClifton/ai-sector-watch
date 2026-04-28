"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check, ExternalLink, LogOut, X } from "lucide-react";

import { sectorLabel } from "@/lib/taxonomy";

export interface PendingCompany {
  id: string;
  name: string;
  country: string | null;
  city: string | null;
  stage: string | null;
  founded_year: number | null;
  summary: string | null;
  sector_tags: string[];
  founders: string[];
  website: string | null;
  discovery_source: string | null;
  profile_sources: string[];
}

interface Props {
  pending: PendingCompany[];
  rejectedCount: number;
}

export function AdminQueue({ pending, rejectedCount }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(id: string, action: "promote" | "reject") {
    setBusy(`${id}:${action}`);
    setError(null);
    try {
      const res = await fetch(`/api/admin/companies/${id}/${action}`, { method: "POST" });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(data.error ?? `HTTP ${res.status}`);
      }
      router.refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(null);
    }
  }

  async function logout() {
    await fetch("/api/admin/logout", { method: "POST" });
    router.replace("/admin/login");
    router.refresh();
  }

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-subtle">
            Restricted - admin only
          </div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-text sm:text-4xl">
            Review queue
          </h1>
          <p className="mt-2 max-w-2xl text-[14px] text-text-muted">
            Auto-discovered candidates wait here for verification before they appear on the
            public map. Promote moves a row to verified; reject keeps it in the database but
            never surfaces it.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[12px] text-text-muted">
          <span>
            <span className="font-mono tabular-nums text-text">{pending.length}</span> pending
          </span>
          <span aria-hidden className="text-border-strong">
            ·
          </span>
          <span>
            <span className="font-mono tabular-nums">{rejectedCount}</span> rejected
          </span>
          <button
            type="button"
            onClick={logout}
            className="ml-2 inline-flex items-center gap-1 rounded-md border border-border-strong bg-surface px-2.5 py-1.5 text-[12px] font-medium text-text-muted transition-colors hover:border-accent hover:text-accent"
          >
            <LogOut className="h-3 w-3" />
            Sign out
          </button>
        </div>
      </header>

      {error && (
        <div
          role="alert"
          className="mt-5 rounded-md border border-error/40 bg-surface px-3 py-2 text-[13px] text-error"
        >
          {error}
        </div>
      )}

      {pending.length === 0 ? (
        <div className="mt-8 rounded-xl border border-border bg-surface p-8 text-center">
          <div className="text-[14px] font-semibold text-text">Queue is clear</div>
          <p className="mt-1 text-[13px] text-text-muted">
            New candidates will appear here after each weekly pipeline run.
          </p>
        </div>
      ) : (
        <ul className="mt-8 space-y-3">
          {pending.map((c) => (
            <li
              key={c.id}
              className="overflow-hidden rounded-xl border border-border bg-surface"
            >
              <div className="px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="text-[16px] font-semibold text-text">
                      {c.website ? (
                        <a
                          href={c.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 hover:text-accent"
                        >
                          {c.name}
                          <ExternalLink className="h-3 w-3 text-text-muted" />
                        </a>
                      ) : (
                        c.name
                      )}
                    </h2>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-text-muted">
                      {[c.city, c.country].filter(Boolean).join(", ") && (
                        <span>{[c.city, c.country].filter(Boolean).join(", ")}</span>
                      )}
                      {c.stage && <span>{c.stage}</span>}
                      {c.founded_year !== null && <span>Founded {c.founded_year}</span>}
                      {c.discovery_source && (
                        <span className="text-text-subtle">via {c.discovery_source}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => act(c.id, "reject")}
                      disabled={busy !== null}
                      className="inline-flex items-center gap-1 rounded-md border border-border-strong bg-surface px-3 py-1.5 text-[12px] font-medium text-text-muted transition-colors hover:border-error hover:text-error disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <X className="h-3 w-3" />
                      {busy === `${c.id}:reject` ? "..." : "Reject"}
                    </button>
                    <button
                      type="button"
                      onClick={() => act(c.id, "promote")}
                      disabled={busy !== null}
                      className="inline-flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-[12px] font-semibold text-bg transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <Check className="h-3 w-3" />
                      {busy === `${c.id}:promote` ? "..." : "Promote"}
                    </button>
                  </div>
                </div>

                {c.summary && (
                  <p className="mt-3 text-[13px] leading-relaxed text-text">{c.summary}</p>
                )}

                {c.sector_tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {c.sector_tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-muted"
                      >
                        {sectorLabel(tag)}
                      </span>
                    ))}
                  </div>
                )}

                {c.founders.length > 0 && (
                  <div className="mt-3 text-[12px] text-text-muted">
                    <span className="font-medium uppercase tracking-[0.1em] text-text-subtle">
                      Founders:
                    </span>{" "}
                    {c.founders.join(", ")}
                  </div>
                )}

                {c.profile_sources.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                    <span className="font-medium uppercase tracking-[0.1em] text-text-subtle">
                      Sources:
                    </span>
                    {c.profile_sources.slice(0, 5).map((src) => (
                      <a
                        key={src}
                        href={src}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-muted underline-offset-2 hover:text-accent hover:underline"
                      >
                        {prettyHostname(src)}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-8 text-[12px] text-text-subtle">
        <Link href="/" className="hover:text-text">
          Back to public site
        </Link>
      </div>
    </>
  );
}

function prettyHostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
