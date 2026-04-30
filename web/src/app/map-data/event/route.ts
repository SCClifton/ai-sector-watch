import { NextRequest, NextResponse } from "next/server";

const PLAUSIBLE_EVENT_ENDPOINT = "https://plausible.io/api/event";

function forwardedHeaders(request: NextRequest): HeadersInit {
  const headers = new Headers({
    "Content-Type": request.headers.get("content-type") ?? "text/plain",
  });

  for (const name of [
    "user-agent",
    "x-forwarded-for",
    "x-real-ip",
    "x-forwarded-host",
    "x-forwarded-proto",
  ]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  return headers;
}

export async function POST(request: NextRequest) {
  const response = await fetch(PLAUSIBLE_EVENT_ENDPOINT, {
    method: "POST",
    headers: forwardedHeaders(request),
    body: await request.text(),
    cache: "no-store",
  });

  return new NextResponse(await response.text(), {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "text/plain",
      "X-Plausible-Dropped": response.headers.get("x-plausible-dropped") ?? "0",
    },
  });
}
