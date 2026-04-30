"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";

const PLAUSIBLE_DOMAIN = "aimap.cliftonfamily.co";
const PLAUSIBLE_SCRIPT_SRC = "https://plausible.io/js/script.js";

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
      src={PLAUSIBLE_SCRIPT_SRC}
    />
  );
}
