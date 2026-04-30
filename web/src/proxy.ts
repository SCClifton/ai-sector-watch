import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname !== "/Admin" && !pathname.startsWith("/Admin/")) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = `/admin${pathname.slice("/Admin".length)}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/Admin", "/Admin/:path*"],
};
