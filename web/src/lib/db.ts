// Lazy postgres-js client. Server-only — never import this from a client component.
//
// Reads SUPABASE_DB_URL, the same env var the Python pipeline and Streamlit dashboard
// use (see src/ai_sector_watch/storage/supabase_db.py). The value is supplied via
// `op run --env-file=.env.local --` per the repo conventions.
//
// The client is created on first query, not at module load, so `next build`
// doesn't fail when collecting page data without env access.

import "server-only";

import postgres from "postgres";

type Sql = ReturnType<typeof postgres>;

declare global {
  var __aisw_sql__: Sql | undefined;
}

function makeClient(): Sql {
  const url = process.env.SUPABASE_DB_URL;
  if (!url) {
    throw new Error(
      "SUPABASE_DB_URL is not set. Run with `op run --account my.1password.com " +
        "--env-file=.env.local -- npm run dev`.",
    );
  }
  return postgres(url, {
    ssl: "require",
    max: 4,
    idle_timeout: 20,
    connect_timeout: 10,
  });
}

function getSql(): Sql {
  if (!globalThis.__aisw_sql__) {
    globalThis.__aisw_sql__ = makeClient();
  }
  return globalThis.__aisw_sql__;
}

// Proxy that defers client creation to the first query. Target is a function
// so the proxy itself is callable (postgres-js uses sql as a tagged template).
const proxyTarget = function () {} as unknown as Sql;
export const sql = new Proxy(proxyTarget, {
  get(_target, prop) {
    const client = getSql() as unknown as Record<string | symbol, unknown>;
    const value = client[prop];
    return typeof value === "function"
      ? (value as (...args: unknown[]) => unknown).bind(client)
      : value;
  },
  apply(_target, _this, args) {
    return (getSql() as unknown as (...a: unknown[]) => unknown)(...args);
  },
}) as Sql;
