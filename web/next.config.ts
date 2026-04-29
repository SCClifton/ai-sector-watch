import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produce a self-contained server bundle that runs `node server.js`.
  // The container Dockerfile copies the .next/standalone directory.
  // https://nextjs.org/docs/app/api-reference/config/next-config-js/output
  output: "standalone",
  turbopack: {
    root: path.resolve(__dirname),
  },
  // Compat shim: the previous Streamlit container served /_stcore/health,
  // which the Azure App Service health-check path may still target. Map it
  // to /api/health so the cutover does not require an immediate Azure
  // config change. New deployments should point health checks at
  // /api/health directly.
  async rewrites() {
    return [
      { source: "/_stcore/health", destination: "/api/health" },
    ];
  },
  // Streamlit served the admin page at /Admin (derived from 90_Admin.py).
  // Next.js routes are case-sensitive. Redirect anyone with the old URL
  // bookmarked or in muscle memory to the canonical lowercase route.
  async redirects() {
    return [
      { source: "/Admin", destination: "/admin", permanent: false },
      { source: "/Admin/:path*", destination: "/admin/:path*", permanent: false },
    ];
  },
};

export default nextConfig;
