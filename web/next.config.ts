import path from "node:path";
import type { NextConfig } from "next";

const securityHeaders = [
  {
    key: "Strict-Transport-Security",
    value: "max-age=15552000; includeSubDomains",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://tiles.openfreemap.org",
      "font-src 'self' https://tiles.openfreemap.org",
      "connect-src 'self' blob: https://tiles.openfreemap.org",
      "worker-src 'self' blob:",
      "upgrade-insecure-requests",
    ].join("; "),
  },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Produce a self-contained server bundle that runs `node server.js`.
  // The container Dockerfile copies the .next/standalone directory.
  // https://nextjs.org/docs/app/api-reference/config/next-config-js/output
  output: "standalone",
  turbopack: {
    root: path.resolve(__dirname),
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
  // Compat shim: the previous Streamlit container served /_stcore/health,
  // which the Azure App Service health-check path may still target. Map it
  // to /api/health so the cutover does not require an immediate Azure
  // config change. New deployments should point health checks at
  // /api/health directly.
  async rewrites() {
    return [
      { source: "/_stcore/health", destination: "/api/health" },
      {
        source: "/map-data/script.js",
        destination: "https://plausible.io/js/pa-y14so16JDPotlwE9pZNzK.js",
      },
    ];
  },
};

export default nextConfig;
