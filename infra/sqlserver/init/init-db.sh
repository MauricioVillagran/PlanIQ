#!/bin/bash
# Crea la base de la aplicación y su login. Idempotente: se ejecuta en cada arranque del entorno de desarrollo.
set -euo pipefail

SQLCMD=/opt/mssql-tools18/bin/sqlcmd

"$SQLCMD" -C -b -S sqlserver -U sa -P "$MSSQL_SA_PASSWORD" \
  -v DB_NAME="$DB_NAME" DB_USER="$DB_USER" DB_PASSWORD="$DB_PASSWORD" \
  -i /init/01-create-database.sql

echo "Base '$DB_NAME' y login '$DB_USER' listos."
