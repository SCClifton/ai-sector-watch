// POST /api/admin/companies/[id]/reject
// Auth: requires valid admin session cookie.

import { NextResponse } from "next/server";

import { isAdminAuthenticated } from "@/lib/admin-auth";
import { logAdminAction, setCompanyStatus } from "@/lib/admin-companies";

export const dynamic = "force-dynamic";

interface Params {
  params: Promise<{ id: string }>;
}

export async function POST(_request: Request, { params }: Params) {
  if (!(await isAdminAuthenticated())) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { id } = await params;
  if (!id) {
    return NextResponse.json({ error: "Missing company id" }, { status: 400 });
  }
  try {
    await setCompanyStatus(id, "rejected");
    await logAdminAction(id, "rejected").catch(() => {
      // Audit log is best-effort; do not block the action on its failure.
    });
    return NextResponse.json({ ok: true, id, status: "rejected" });
  } catch (err) {
    console.error("POST /api/admin/companies/[id]/reject failed", err);
    return NextResponse.json(
      { error: "reject failed", detail: String(err) },
      { status: 500 },
    );
  }
}
