# syntax=docker/dockerfile:1.7
#
# Phase 3 cutover: this image now serves the Next.js app under web/, not the
# Streamlit dashboard under dashboard/. The Streamlit code stays in the repo
# for one cooling-off release; the previous image lives at GHCR
# `ghcr.io/scclifton/ai-sector-watch/ai-sector-watch:streamlit-final` for
# rollback.
#
# Multi-stage:
#   1. deps   - install npm deps once
#   2. build  - run `next build` to produce .next/standalone
#   3. runner - copy the standalone output into a slim node runtime

# ---------- 1. deps ----------
FROM node:20-slim AS deps
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---------- 2. build ----------
FROM node:20-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY web/ ./

# Standalone output writes everything we need into .next/standalone and
# .next/static. The build does not need DB access (db.ts is lazy).
RUN npm run build

# ---------- 3. runner ----------
FROM node:20-slim AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Run as non-root.
RUN addgroup --system --gid 1001 node-app \
 && adduser --system --uid 1001 --gid 1001 node-app \
 && apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

# Standalone server + static assets + public/.
COPY --from=build --chown=node-app:node-app /app/.next/standalone ./
COPY --from=build --chown=node-app:node-app /app/.next/static ./.next/static
COPY --from=build --chown=node-app:node-app /app/public ./public

USER node-app

# Azure App Service for Linux maps the inbound port via WEBSITES_PORT, which
# the platform exposes to the container as PORT. Next.js standalone reads
# PORT directly. EXPOSE is informational; the actual port is whatever PORT
# resolves to at runtime (3000 by default; 8000 if WEBSITES_PORT is still
# set to 8000 from the previous Streamlit container).
EXPOSE 3000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "server.js"]
