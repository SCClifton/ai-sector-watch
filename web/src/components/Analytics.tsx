"use client";

import Script from "next/script";
import { usePathname } from "next/navigation";

const PLAUSIBLE_SCRIPT_SRC = "/map-data/script.js";
const PLAUSIBLE_EVENT_ENDPOINT = "/map-data/event";

function isAdminPath(pathname: string): boolean {
  return pathname === "/admin" || pathname.startsWith("/admin/");
}

export function Analytics() {
  const pathname = usePathname();

  if (process.env.NODE_ENV !== "production" || isAdminPath(pathname)) return null;

  return (
    <>
      <Script
        id="plausible-init"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
window.plausible=window.plausible||function(){(plausible.q=plausible.q||[]).push(arguments)};
plausible.init=plausible.init||function(i){plausible.o=i||{}};
plausible.init({ endpoint: "${PLAUSIBLE_EVENT_ENDPOINT}" });
          `.trim(),
        }}
      />
      <Script id="plausible-analytics" strategy="afterInteractive" src={PLAUSIBLE_SCRIPT_SRC} />
    </>
  );
}
