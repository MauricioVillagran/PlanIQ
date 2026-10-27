# syntax=docker/dockerfile:1
# Imagen de api y worker (targets `api` y `worker`). Contexto de build: raíz del repositorio.

FROM ghcr.io/astral-sh/uv:0.13.5 AS uv

# --- Base: Python + ODBC Driver 18 para SQL Server -----------------------------
FROM python:3.13.18-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/workspace/.venv \
    PATH="/workspace/.venv/bin:$PATH"

# Instalar msodbcsql18 requiere aceptar la licencia de Microsoft (ACCEPT_EULA=Y).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
 && apt-get purge -y gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /bin/

RUN useradd --create-home --uid 10001 planiq \
 && mkdir -p /workspace /data/storage \
 && chown -R planiq:planiq /workspace /data/storage

WORKDIR /workspace

# --- Dependencias (capa cacheable: solo cambia con los pyproject o el lock) ----
FROM base AS deps
COPY pyproject.toml uv.lock ./
COPY api/pyproject.toml api/pyproject.toml
COPY worker/pyproject.toml worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-packages --no-install-workspace

# --- API -------------------------------------------------------------------------
FROM deps AS api
# true en desarrollo: agrega pytest, ruff y mypy (grupo dev) para correr pruebas dentro del contenedor.
ARG DEV_DEPS=false
COPY api/ api/
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$DEV_DEPS" = "true" ]; then uv sync --frozen --package planiq-api; \
    else uv sync --frozen --no-dev --package planiq-api; fi \
 && chown -R planiq:planiq /workspace
USER planiq
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

# --- Worker ----------------------------------------------------------------------
FROM deps AS worker
COPY api/ api/
COPY worker/ worker/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package planiq-worker \
 && chown -R planiq:planiq /workspace
USER planiq
CMD ["python", "-m", "worker.main"]
