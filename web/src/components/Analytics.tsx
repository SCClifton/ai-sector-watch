"use client";

import { useEffect } from "react";
import Script from "next/script";
import { usePathname } from "next/navigation";

const PLAUSIBLE_SCRIPT_SRC = "/map-data/script.js";
const PLAUSIBLE_EVENT_ENDPOINT = "/map-data/event";

function isAdminPath(pathname: string): boolean {
  return pathname === "/admin" || pathname.startsWith("/admin/");
}

type PlausibleFunction = {
  (eventName: string, options?: { url?: string }): void;
  q?: unknown[][];
  init?: (options?: Record<string, unknown>) => void;
  o?: Record<string, unknown>;
};

declare global {
  interface Window {
    plausible?: PlausibleFunction;
  }
}

function queuePageview(): void {
  window.plausible =
    window.plausible ||
    ((...args: unknown[]) => {
      const plausible = window.plausible;
      if (!plausible) return;
      plausible.q = plausible.q || [];
      plausible.q.push(args);
    });
  window.plausible("pageview", { url: window.location.href });
}

export function Analytics() {
  const pathname = usePathname();
  const shouldTrack = process.env.NODE_ENV === "production" && !isAdminPath(pathname);

  useEffect(() => {
    if (shouldTrack) queuePageview();
  }, [shouldTrack, pathname]);

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
plausible.init({ endpoint: "${PLAUSIBLE_EVENT_ENDPOINT}", autoCapturePageviews: false });
          `.trim(),
        }}
      />
      <Script id="plausible-analytics" strategy="afterInteractive" src={PLAUSIBLE_SCRIPT_SRC} />
    </>
  );
}
