// GET /api/news?limit=100 — recent news items.

import { NextResponse } from "next/server";

import { listRecentNews } from "@/lib/news-server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limitParam = Number(url.searchParams.get("limit") ?? 100);
  const limit = Number.isFinite(limitParam) ? Math.min(Math.max(limitParam, 1), 500) : 100;

  try {
    const items = await listRecentNews(limit);
    return NextResponse.json({ items });
  } catch (err) {
    console.error("GET /api/news failed", err);
    return NextResponse.json(
      { error: "failed to load news", detail: String(err) },
      { status: 500 },
    );
  }
}
