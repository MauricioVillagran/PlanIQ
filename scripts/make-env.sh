#!/usr/bin/env bash
# Genera un .env a partir de .env.example con claves aleatorias (CI y pruebas end-to-end).
#   scripts/make-env.sh > .env
# Variables opcionales: APP_ENV, HTTP_PORT, DB_HOST_PORT.
set -euo pipefail
cd "$(dirname "$0")/.."

# Lee un bloque acotado de /dev/urandom: con lectura infinita, `tr` termina con "Broken pipe".
rnd() { head -c 512 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | head -c "$1"; }

sed \
  -e "s/^APP_ENV=.*/APP_ENV=${APP_ENV:-development}/" \
  -e "s/^HTTP_PORT=.*/HTTP_PORT=${HTTP_PORT:-8080}/" \
  -e "s/^DB_HOST_PORT=.*/DB_HOST_PORT=${DB_HOST_PORT:-14330}/" \
  -e "s/^MSSQL_SA_PASSWORD=.*/MSSQL_SA_PASSWORD=Sa_$(rnd 20)9/" \
  -e "s/^DB_PASSWORD=.*/DB_PASSWORD=Db_$(rnd 20)9/" \
  -e "s/^JWT_SECRET=.*/JWT_SECRET=$(rnd 48)/" \
  -e "s/^INITIAL_ADMIN_PASSWORD=.*/INITIAL_ADMIN_PASSWORD=Ini_$(rnd 16)/" \
  -e "s/^DEV_SEED_PASSWORD=.*/DEV_SEED_PASSWORD=Demo_$(rnd 16)/" \
  .env.example
