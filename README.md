# PlanIQ

Sistema web de planificación productiva para plantas de proceso de salmón: un único plan diario versionado por planta y fecha productiva, avance real casi en línea y cumplimiento contra el plan. Funciona en el escritorio de Planificación y en el celular de un supervisor en planta.

- Alcance, arquitectura y fases: [docs/PROMPT_Sistema_Planificacion.md](docs/PROMPT_Sistema_Planificacion.md)
- Reglas permanentes del proyecto: [CLAUDE.md](CLAUDE.md)
- Decisiones de arquitectura: [docs/adr/](docs/adr/)
- Plan y entrega por fase: [docs/fases/](docs/fases/) · Operación y respaldos: [docs/operacion.md](docs/operacion.md)

## Estado

**Fase 0 — Fundación y administración: entregada** ([nota de entrega](docs/fases/fase-0-entrega.md)). Incluye autenticación propia, permisos por rol y planta, auditoría, y los mantenedores de usuarios, roles, plantas, turnos y parámetros. Siguiente: Fase 1, planificación de cosecha.

## Levantar el entorno desde cero (Windows)

**Requisitos:** Docker Desktop con WSL2 (al menos 6 GB de memoria para Docker) y Git para Windows. Node.js 24 solo hace falta para trabajar en el frontend fuera de Docker.

1. Clonar el repositorio:

   ```bash
   git clone https://github.com/MauricioVillagran/PlanIQ.git
   ```

2. Crear el `.env` con claves aleatorias, desde la carpeta del repositorio en Git Bash:

   ```bash
   bash scripts/make-env.sh > .env
   ```

   También se puede copiar `.env.example` a `.env` y cambiar a mano `MSSQL_SA_PASSWORD`, `DB_PASSWORD`, `JWT_SECRET`, `INITIAL_ADMIN_PASSWORD` y `DEV_SEED_PASSWORD`. Las dos primeras deben cumplir la política de SQL Server: 8 o más caracteres con mayúsculas, minúsculas, números y símbolos.

3. Levantar todo:

   ```bash
   docker compose up -d --build
   ```

   La primera vez tarda unos minutos (descarga SQL Server y construye las imágenes). Se crea la base `planiq`, se aplican las migraciones y se crea el administrador inicial.

4. Abrir http://localhost:8080 e ingresar con el usuario `admin` y la contraseña `INITIAL_ADMIN_PASSWORD` de `.env`. El sistema exige cambiarla en el primer ingreso.

5. En **Configuración** crear la planta, sus turnos y los usuarios. No hay ninguna planta precargada.

**Opcional, datos ficticios** para probar: `docker compose exec -w /workspace/api api python -m app.seed` crea la "Planta Demo" con turnos día y noche y los usuarios `demo.admin`, `demo.planificacion`, `demo.produccion` y `demo.calidad`, con la contraseña `DEV_SEED_PASSWORD` de `.env`. Solo funciona con `APP_ENV=development`.

### Qué queda corriendo

| Servicio | Para qué |
|---|---|
| `proxy` (Caddy) | Única entrada: http://localhost:8080 (web) y `/api/v1` (API) |
| `web` | Frontend Next.js (recarga en caliente en desarrollo) |
| `api` | API FastAPI; documentación en http://localhost:8080/api/docs |
| `worker` | Trabajos en segundo plano (cola en SQL Server) |
| `sqlserver` | SQL Server 2022 Express; desde SSMS: `localhost,14330`, usuario `planiq_app` |
| `db-init`, `migrate` | Se ejecutan y terminan: crean las bases y aplican las migraciones |

Comandos diarios (logs, pruebas, migraciones, regenerar tipos de la API): ver la sección **Comandos** de [CLAUDE.md](CLAUDE.md).

### Problemas frecuentes

- **`http://localhost:8080` queda cargando sin responder:** revisar que `.env` tenga `HTTP_BIND=127.0.0.1`. Con `0.0.0.0`, WSL crea un reenvío IPv6 que se cuelga. Si el puerto quedó tomado por un reenvío antiguo, reiniciar Docker Desktop o usar otro `HTTP_PORT`.
- **Puerto ocupado** (80, 1433, 8000 u 8080 por otros proyectos): cambiar `HTTP_PORT` o `DB_HOST_PORT` en `.env` y volver a ejecutar `docker compose up -d`.
- **Una segunda copia del repositorio en el mismo equipo:** agregar `COMPOSE_PROJECT_NAME=planiq2` (y otros puertos) a su `.env`, o compartirá contenedores y base con la primera.
- **Empezar con la base vacía:** `docker compose down -v` borra los datos de desarrollo. Es irreversible: respaldar antes si hace falta ([docs/operacion.md](docs/operacion.md)).

## Pruebas

| Qué | Cómo |
|---|---|
| Backend (pytest, ruff, mypy) | `docker compose exec -w /workspace/api api pytest` |
| Frontend (ESLint, tipos, Vitest) | `cd web && npm ci && npm run lint && npm run typecheck && npm test` |
| End-to-end (Playwright, 360 px y escritorio) | `bash scripts/e2e.sh --down`: stack aislado en el puerto 8090 con base nueva, sin tocar la de desarrollo |

El CI de GitHub Actions corre las tres en cada pull request y en cada push a `develop`, `qa` y `main`.

## QA y producción

Con la base en un servidor SQL Server externo (sin el contenedor de desarrollo):

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

En ese `.env`: `APP_ENV=qa` o `production`, `DB_HOST` del servidor, claves propias y `DB_TRUST_SERVER_CERTIFICATE=no` con un certificado válido. Sin HTTPS (por ejemplo, un QA interno), agregar `AUTH_COOKIE_SECURE=false`. El servidor definitivo (on-premise o nube) está pendiente; ver [docs/operacion.md](docs/operacion.md).

## Estructura

```
api/          backend FastAPI (app/core, app/db, app/modules, app/domain), migraciones y pruebas
worker/       procesos en segundo plano (cargas Excel, sincronización Innova)
web/          frontend Next.js (src/app, src/components, src/features, src/lib) y pruebas e2e
infra/        Docker Compose en capas, Dockerfiles, SQL Server de desarrollo y Caddy
scripts/      make-env.sh (genera .env), e2e.sh (pruebas end-to-end)
docs/         especificación, ADR, plan y entrega por fase, operación
compose.yaml  entorno de desarrollo completo
```

## Datos

La carpeta `cargaExcel/` contiene archivos reales de producción y **no se versiona** ni se usa en pruebas. `.env` y `.env.*` tampoco se versionan; solo `.env.example`.

## Ramas

`main` (producción) ← `qa` ← `develop` ← `feature/<fase>-<tema>`. Todo cambio entra por pull request con el CI en verde.
