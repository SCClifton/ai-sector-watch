// GET /api/companies  -  verified companies (mirrors SupabaseSource.list_companies).

import { NextResponse } from "next/server";

import { listVerifiedCompanies } from "@/lib/companies-server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  try {
    const companies = await listVerifiedCompanies();
    return NextResponse.json({ companies });
  } catch (err) {
    console.error("GET /api/companies failed", err);
    return NextResponse.json(
      { error: "failed to load companies", detail: String(err) },
      { status: 500 },
    );
  }
}
