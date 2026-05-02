# syntax=docker/dockerfile:1.7
#
# Phase 3 cutover: this image serves the Next.js app under web/, not the
# Streamlit dashboard under dashboard/. The Streamlit code stays in the repo
# for one cooling-off release. For rollback, see docs/deployment.md - the
# last known-good Streamlit image is in GHCR at the SHA tag for commit
# f8f2aaefba1d6417b3be7ae32c71d9bf98ea0cb4 (it can also be retagged
# :streamlit-final from any machine with docker access).
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
    PORT=8000 \
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
COPY --chown=node-app:node-app data/research_briefs ./data/research_briefs

USER node-app

# Port contract with Azure App Service for Linux:
# - WEBSITES_PORT (App Service config) tells Azure's reverse proxy which
#   port to route inbound traffic to. The Streamlit-era App Service has
#   WEBSITES_PORT=8000.
# - Azure does NOT inject WEBSITES_PORT into the container env.
# - The container must therefore listen on the port WEBSITES_PORT names.
# We pin PORT=8000 above so Next.js standalone (which reads PORT) listens
# on the same port Azure routes to. If WEBSITES_PORT is ever changed, this
# ENV needs to follow.
EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "server.js"]
