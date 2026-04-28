// Singleton postgres-js client. Server-only — never import this from a client component.
//
// Reads SUPABASE_DB_URL, the same env var the Python pipeline and Streamlit dashboard
// use (see src/ai_sector_watch/storage/supabase_db.py). The value is supplied via
// `op run --env-file=.env.local --` per the repo conventions.

import "server-only";

import postgres from "postgres";

declare global {
  // eslint-disable-next-line no-var
  var __aisw_sql__: ReturnType<typeof postgres> | undefined;
}

function makeClient() {
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

export const sql = globalThis.__aisw_sql__ ?? makeClient();

if (process.env.NODE_ENV !== "production") {
  globalThis.__aisw_sql__ = sql;
}
