#!/bin/bash
# Crea la base de la aplicación, la base de pruebas (<DB_NAME>_test) y su login.
# Idempotente: se ejecuta en cada arranque del entorno de desarrollo.
set -euo pipefail

SQLCMD=/opt/mssql-tools18/bin/sqlcmd

for db in "$DB_NAME" "${DB_NAME}_test"; do
  "$SQLCMD" -C -b -S sqlserver -U sa -P "$MSSQL_SA_PASSWORD" \
    -v DB_NAME="$db" DB_USER="$DB_USER" DB_PASSWORD="$DB_PASSWORD" \
    -i /init/01-create-database.sql
  echo "Base '$db' lista para el login '$DB_USER'."
done
