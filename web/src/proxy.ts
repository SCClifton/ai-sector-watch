import { NextResponse, type NextRequest } from "next/server";

const CANONICAL_HOST = "aimap.cliftonfamily.co";

function forwardedProtocol(request: NextRequest): string | null {
  return request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ?? null;
}

function shouldRedirectToHttps(request: NextRequest): boolean {
  const host = request.headers.get("host")?.split(":")[0]?.toLowerCase();
  if (host !== CANONICAL_HOST) return false;

  return forwardedProtocol(request) === "http" || request.nextUrl.protocol === "http:";
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (shouldRedirectToHttps(request)) {
    const url = request.nextUrl.clone();
    url.protocol = "https:";
    url.hostname = CANONICAL_HOST;
    url.port = "";
    return NextResponse.redirect(url, 308);
  }

  if (pathname !== "/Admin" && !pathname.startsWith("/Admin/")) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = `/admin${pathname.slice("/Admin".length)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
