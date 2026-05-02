// GET /api/research?limit=30  -  published research brief runs.

import { NextResponse } from "next/server";

import { listResearchRuns } from "@/lib/research-server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limitParam = Number(url.searchParams.get("limit") ?? 30);
  const normalisedLimit = Number.isFinite(limitParam) ? Math.trunc(limitParam) : 30;
  const limit = Math.min(Math.max(normalisedLimit, 1), 100);

  try {
    const runs = await listResearchRuns(limit);
    return NextResponse.json({ runs });
  } catch (err) {
    console.error("GET /api/research failed", err);
    return NextResponse.json(
      { error: "failed to load research", detail: String(err) },
      { status: 500 },
    );
  }
}
