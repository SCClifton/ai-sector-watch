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
      { source: "/_asset/map.js", destination: "https://plausible.io/js/script.js" },
      { source: "/_asset/event", destination: "https://plausible.io/api/event" },
    ];
  },
};

export default nextConfig;
