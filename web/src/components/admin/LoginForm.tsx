"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogIn } from "lucide-react";

export function LoginForm() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        router.replace("/admin");
        router.refresh();
        return;
      }
      const data = (await res.json().catch(() => ({}))) as { error?: string };
      setError(data.error ?? `Sign-in failed (${res.status})`);
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <label className="block">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-subtle">
          Password
        </span>
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="mt-1 block w-full rounded-md border border-border bg-surface-2 px-3 py-2 text-[13px] text-text outline-none focus:border-accent"
          autoFocus
        />
      </label>
      {error && (
        <div
          role="alert"
          className="rounded-md border border-error/40 bg-surface px-3 py-2 text-[12px] text-error"
        >
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={submitting || !password}
        className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-[13px] font-semibold text-bg transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
      >
        <LogIn className="h-3.5 w-3.5" />
        {submitting ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}
