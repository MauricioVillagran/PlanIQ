# Operación y respaldos

Guía de operación del entorno de PlanIQ. Los comandos se ejecutan desde la raíz del repositorio en Git Bash. Para QA o producción, reemplazar `docker compose` por `docker compose --env-file .env -f infra/docker-compose.yml`.

## Estado del sistema

| Qué | Cómo |
|---|---|
| Servicios y salud | `docker compose ps` (api y sqlserver deben decir `healthy`) |
| La API y la base responden | http://localhost:8080/api/v1/health/ready → `{"status":"ok","database":"ok","schema_revision":"…"}` |
| Logs (JSON, una línea por evento) | `docker compose logs -f api` · `worker` · `proxy` |
| Revisión del esquema | `schema_revision` en `/health/ready` debe coincidir con la última migración de `api/migrations/versions` |

## Respaldos de la base (desarrollo y QA con el contenedor)

El procedimiento se probó el 27-10-2026: respaldo con `CHECKSUM`, `RESTORE VERIFYONLY`, restauración en una base aparte, conteo de usuarios y revisión del esquema.

**Respaldar:**

```bash
F=planiq-$(date +%Y%m%d-%H%M).bak
MSYS_NO_PATHCONV=1 docker compose exec -T sqlserver bash -c "mkdir -p /var/opt/mssql/backup && \
  /opt/mssql-tools18/bin/sqlcmd -C -b -S localhost -U sa -P \"\$MSSQL_SA_PASSWORD\" \
  -Q \"BACKUP DATABASE [planiq] TO DISK = N'/var/opt/mssql/backup/$F' WITH INIT, CHECKSUM; \
       RESTORE VERIFYONLY FROM DISK = N'/var/opt/mssql/backup/$F' WITH CHECKSUM\""
docker compose cp "sqlserver:/var/opt/mssql/backup/$F" ./respaldos/
```

- El respaldo queda dentro del volumen de SQL Server **y** se copia a `./respaldos/`. Guardar esa copia **fuera del equipo**: un respaldo en el mismo disco no protege de una falla del disco.
- SQL Server Express no comprime respaldos; una base de Fase 0 pesa pocos MB.
- `./respaldos/` no se versiona: contiene datos de la planta.

**Restaurar** (reemplaza la base `planiq`; detener antes la API y el worker):

```bash
docker compose stop api worker
MSYS_NO_PATHCONV=1 docker compose exec -T sqlserver bash -c "/opt/mssql-tools18/bin/sqlcmd -C -b -S localhost -U sa -P \"\$MSSQL_SA_PASSWORD\" \
  -Q \"ALTER DATABASE [planiq] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; \
       RESTORE DATABASE [planiq] FROM DISK = N'/var/opt/mssql/backup/<archivo>.bak' WITH REPLACE, CHECKSUM; \
       ALTER DATABASE [planiq] SET MULTI_USER\""
docker compose up -d
```

Para revisar un respaldo sin tocar la base vigente, restaurarlo con otro nombre (`RESTORE DATABASE [planiq_restore_test] ... WITH MOVE 'planiq' TO '/var/opt/mssql/data/planiq_restore_test.mdf', MOVE 'planiq_log' TO '/var/opt/mssql/data/planiq_restore_test_log.ldf'`) y borrarlo después.

## Producción: pendiente de definir

Se decide junto con el servidor (on-premise o nube):

- **Política de respaldo:** frecuencia (completo diario y de log cada N minutos, con modelo de recuperación `FULL`), retención y destino fuera del servidor, con prueba de restauración periódica.
- **Edición de SQL Server:** Express limita cada base a 10 GB. Antes de producción hay que estimar el crecimiento de `actual.*` (piezas de grader, Fase 4) y del historial de las tablas temporales, y pasar a Standard si se supera (sección 8 de la especificación).
- **HTTPS** en el proxy y `AUTH_COOKIE_SECURE` en su valor por defecto (cookies `Secure`).
- **Usuario de base separado** para migraciones (`db_owner`) y para la aplicación (permisos mínimos); en desarrollo es uno solo.
- **Retención de archivos subidos** (Fase 4) y de `core.audit_log`.

## Rotación de claves

- `JWT_SECRET`: cambiarlo invalida todas las sesiones abiertas (todos deben volver a ingresar). Reiniciar `api` después de cambiarlo.
- `DB_PASSWORD`: en desarrollo, `db-init` la vuelve a aplicar al login en cada `docker compose up`.
- Contraseñas de usuarios: el administrador las restablece desde **Configuración › Usuarios** (clave temporal; el usuario debe cambiarla al ingresar).
