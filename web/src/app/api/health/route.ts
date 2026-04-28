// GET /api/health
// Lightweight liveness probe for Azure App Service health checks and uptime
// monitoring. Returns 200 with a small JSON payload. Does NOT touch the
// database — keep it fast and dependency-free.

import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  return NextResponse.json({
    ok: true,
    service: "ai-sector-watch-web",
    ts: new Date().toISOString(),
  });
}
