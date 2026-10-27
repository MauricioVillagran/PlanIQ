# syntax=docker/dockerfile:1
# Imagen del frontend Next.js. Contexto de build: web/.
# Targets: `dev` (next dev con recarga) y `runner` (producción, salida standalone).

FROM node:24.22.1-bookworm-slim AS base
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

# --- Dependencias ----------------------------------------------------------------
FROM base AS deps
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

# --- Desarrollo ------------------------------------------------------------------
FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# --- Build -----------------------------------------------------------------------
FROM deps AS build
COPY . .
RUN npm run build

# --- Producción ------------------------------------------------------------------
FROM node:24.22.1-bookworm-slim AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /app
RUN useradd --create-home --uid 10001 planiq
COPY --from=build --chown=planiq:planiq /app/.next/standalone ./
COPY --from=build --chown=planiq:planiq /app/.next/static ./.next/static
USER planiq
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://localhost:3000/').then(r => process.exit(r.status < 500 ? 0 : 1)).catch(() => process.exit(1))"
CMD ["node", "server.js"]
