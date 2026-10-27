#!/usr/bin/env bash
# Pruebas end-to-end (Playwright) contra un stack aislado y desechable.
#
#   scripts/e2e.sh            # levanta el stack desde cero, corre las pruebas y lo deja arriba
#   scripts/e2e.sh --down     # además lo baja al terminar
#   scripts/e2e.sh --down -g "historial"   # el resto de argumentos va a Playwright
#
# Usa su propio proyecto de Compose (planiq-e2e), su propia base y el puerto 8090: no toca el entorno
# de desarrollo ni la base `planiq`. Las imágenes son las de producción. Las claves se generan al
# azar en .env.e2e (ignorado por git).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE=".env.e2e"
PROJECT="planiq-e2e"
PORT="${E2E_HTTP_PORT:-8090}"

DOWN=0
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--down" ]; then DOWN=1; else ARGS+=("$arg"); fi
done

if [ ! -f "$ENV_FILE" ]; then
  rnd() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
  {
    APP_ENV=qa HTTP_PORT="$PORT" DB_HOST_PORT=14331 bash scripts/make-env.sh |
      sed -e "s/^AUTH_LOGIN_RATE_LIMIT=.*/AUTH_LOGIN_RATE_LIMIT=1000\/minute/"
    echo ""
    echo "# --- Solo pruebas end-to-end ---"
    echo "# QA sin HTTPS: la cookie de sesión no puede ser Secure."
    echo "AUTH_COOKIE_SECURE=false"
    echo "E2E_ADMIN_NEW_PASSWORD=Adm_$(rnd 16)"
    echo "E2E_USER_PASSWORD=Usr_$(rnd 16)"
  } >"$ENV_FILE"
  echo "Creado $ENV_FILE con claves aleatorias."
fi

val() { grep -E "^$1=" "$ROOT/$ENV_FILE" | head -1 | cut -d= -f2-; }

compose() {
  ENV_FILE="../$ENV_FILE" docker compose -p "$PROJECT" --env-file "$ENV_FILE" \
    -f infra/docker-compose.yml -f infra/docker-compose.db.yml "$@"
}

echo "Levantando el stack de pruebas desde cero (proyecto $PROJECT, puerto $PORT)..."
compose down -v --remove-orphans >/dev/null 2>&1 || true
compose up -d --build

echo "Esperando la API y el web en http://127.0.0.1:$PORT ..."
ready=0
for _ in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:$PORT/api/v1/health/ready" >/dev/null 2>&1 &&
    curl -fsS -o /dev/null "http://127.0.0.1:$PORT/login" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" != 1 ]; then
  echo "El stack no quedó listo a tiempo." >&2
  compose ps
  compose logs --tail 60 migrate api web
  exit 1
fi

status=0
(
  cd web
  E2E_BASE_URL="http://127.0.0.1:$PORT" \
  E2E_ADMIN_USERNAME="$(val INITIAL_ADMIN_USERNAME)" \
  E2E_ADMIN_PASSWORD="$(val INITIAL_ADMIN_PASSWORD)" \
  E2E_ADMIN_NEW_PASSWORD="$(val E2E_ADMIN_NEW_PASSWORD)" \
  E2E_USER_PASSWORD="$(val E2E_USER_PASSWORD)" \
    npx playwright test ${ARGS[@]+"${ARGS[@]}"}
) || status=$?

if [ "$DOWN" = 1 ]; then
  compose down -v --remove-orphans
fi
exit $status
