// Server-side admin auth. Never import from client code.
//
// Session cookie format: `<expMs>.<HMAC-SHA256(ADMIN_PASSWORD, expMs).hex>`
// On each request we recompute the HMAC and compare in constant time.
// The seed is ADMIN_PASSWORD itself, so rotating the password invalidates
// every session for free.

import "server-only";

import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

export const SESSION_COOKIE = "aisw_admin";
const SESSION_TTL_MS = 12 * 60 * 60 * 1000; // 12 hours

function getPassword(): string {
  const pw = process.env.ADMIN_PASSWORD;
  if (!pw) {
    throw new Error("ADMIN_PASSWORD is not set; admin auth disabled.");
  }
  return pw;
}

function sign(expMs: number, password: string): string {
  return createHmac("sha256", password).update(String(expMs)).digest("hex");
}

export function makeSessionValue(): string {
  const expMs = Date.now() + SESSION_TTL_MS;
  return `${expMs}.${sign(expMs, getPassword())}`;
}

export function isValidSession(value: string | undefined | null): boolean {
  if (!value) return false;
  const dot = value.indexOf(".");
  if (dot < 0) return false;
  const expStr = value.slice(0, dot);
  const sig = value.slice(dot + 1);
  const expMs = Number(expStr);
  if (!Number.isFinite(expMs) || expMs < Date.now()) return false;

  let pw: string;
  try {
    pw = getPassword();
  } catch {
    return false;
  }

  const expected = sign(expMs, pw);
  if (sig.length !== expected.length) return false;
  try {
    return timingSafeEqual(Buffer.from(sig, "hex"), Buffer.from(expected, "hex"));
  } catch {
    return false;
  }
}

export function checkPassword(attempt: string): boolean {
  let pw: string;
  try {
    pw = getPassword();
  } catch {
    return false;
  }
  if (attempt.length !== pw.length) return false;
  try {
    return timingSafeEqual(Buffer.from(attempt, "utf8"), Buffer.from(pw, "utf8"));
  } catch {
    return false;
  }
}

export async function isAdminAuthenticated(): Promise<boolean> {
  const store = await cookies();
  const value = store.get(SESSION_COOKIE)?.value;
  return isValidSession(value);
}

export const SESSION_TTL_SECONDS = Math.floor(SESSION_TTL_MS / 1000);
