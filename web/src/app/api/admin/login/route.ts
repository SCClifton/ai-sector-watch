// POST /api/admin/login
// Body: { password: string }
// Sets an HttpOnly session cookie if the password matches ADMIN_PASSWORD.

import { NextResponse } from "next/server";

import {
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  checkPassword,
  makeSessionValue,
} from "@/lib/admin-auth";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: { password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const password = (body.password ?? "").toString();
  if (!password) {
    return NextResponse.json({ error: "Password is required" }, { status: 400 });
  }

  if (!checkPassword(password)) {
    return NextResponse.json({ error: "Wrong password" }, { status: 401 });
  }

  const value = makeSessionValue();
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, value, {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
  return res;
}
