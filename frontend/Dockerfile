# syntax=docker/dockerfile:1.7
# Numo9 frontend image. Build context: repository root (pnpm workspace + root lockfile)
#   docker build -f frontend/Dockerfile --target dev     -t numo9-frontend:dev .
#   docker build -f frontend/Dockerfile --target runtime -t numo9-frontend .

ARG PNPM_VERSION=10.30.0

# ---- base: node + pnpm via corepack ------------------------------------------
# Base images pinned in the FROM lines so Dependabot can update them (S-01-T16).
FROM node:22.23.4-alpine AS base
ARG PNPM_VERSION
ENV NEXT_TELEMETRY_DISABLED=1 \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@${PNPM_VERSION} --activate
WORKDIR /repo

# ---- deps: install the frontend workspace from the root lockfile -------------
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json frontend/package.json
COPY mobile/package.json mobile/package.json
RUN pnpm install --frozen-lockfile --filter @numo9/frontend...

# ---- dev: next dev, source bind-mounted by compose ---------------------------
FROM deps AS dev
COPY frontend frontend
WORKDIR /repo/frontend
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=10 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1
CMD ["pnpm", "exec", "next", "dev", "--hostname", "0.0.0.0", "--port", "3000"]

# ---- builder: production build (standalone output) ---------------------------
FROM deps AS builder
COPY frontend frontend
ENV NEXT_OUTPUT=standalone
RUN pnpm --filter @numo9/frontend run build

# ---- runtime: minimal production image, non-root ------------------------------
FROM node:22.23.4-alpine AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /app
# The runtime only executes `node`. Remove the package managers bundled with the base image
# (npm, npx, corepack, yarn): unused here, and their vendored deps carry HIGH CVEs (Trivy).
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack /opt/yarn-* \
        /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg \
    && addgroup -S -g 10001 numo9 && adduser -S -u 10001 -G numo9 -h /app numo9
COPY --from=builder --chown=numo9:numo9 /repo/frontend/.next/standalone ./
COPY --from=builder --chown=numo9:numo9 /repo/frontend/.next/static ./frontend/.next/static
USER numo9
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1
CMD ["node", "frontend/server.js"]
