// GET /api/spend-summary  -  last 4 weeks of weekly_run LLM cost.

import { NextResponse } from "next/server";

import { getSpendSummary } from "@/lib/news-server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  try {
    const summary = await getSpendSummary();
    return NextResponse.json({ summary });
  } catch (err) {
    console.error("GET /api/spend-summary failed", err);
    return NextResponse.json(
      { error: "failed to load spend summary", detail: String(err) },
      { status: 500 },
    );
  }
}
