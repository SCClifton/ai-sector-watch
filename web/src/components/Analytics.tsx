"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";

const PLAUSIBLE_DOMAIN = "aimap.cliftonfamily.co";
const PLAUSIBLE_SCRIPT_SRC = "/_asset/map.js";
const PLAUSIBLE_EVENT_ENDPOINT = "/_asset/event";

function isAdminPath(pathname: string): boolean {
  return pathname === "/admin" || pathname.startsWith("/admin/");
}

export function Analytics() {
  const pathname = usePathname();

  if (process.env.NODE_ENV !== "production" || isAdminPath(pathname)) return null;

  return (
    <Script
      id="plausible-analytics"
      strategy="afterInteractive"
      data-domain={PLAUSIBLE_DOMAIN}
      data-api={PLAUSIBLE_EVENT_ENDPOINT}
      src={PLAUSIBLE_SCRIPT_SRC}
    />
  );
}
