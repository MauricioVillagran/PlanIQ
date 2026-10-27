# PlanIQ

Sistema web de planificación productiva para plantas de proceso de salmón: planificación de cosecha, simulación de graders, real versus plan, distribución comercial y seguimiento, usable en escritorio y celular.

- Alcance, arquitectura y fases: [docs/PROMPT_Sistema_Planificacion.md](docs/PROMPT_Sistema_Planificacion.md)
- Reglas permanentes del proyecto: [CLAUDE.md](CLAUDE.md)
- Decisiones de arquitectura: [docs/adr/](docs/adr/)
- Plan y entrega por fase: [docs/fases/](docs/fases/)

## Estado

Fase 0 (fundación y administración) en curso. Estas instrucciones se completan al cerrar la fase.

## Levantar el entorno de desarrollo

Requisito: Docker Desktop con WSL2 (al menos 6 GB de memoria disponibles para Docker).

1. Copiar `.env.example` a `.env` y cambiar las claves (`MSSQL_SA_PASSWORD`, `DB_PASSWORD`, `JWT_SECRET`, `INITIAL_ADMIN_PASSWORD`).
2. Desde la raíz del repositorio:

   ```bash
   docker compose up -d --build
   ```

3. Abrir http://localhost:8080 (o el puerto de `HTTP_PORT`). La página muestra si la API y la base responden. La documentación de la API está en http://localhost:8080/api/docs.

Servicios: `sqlserver` (SQL Server 2022 Express, accesible desde SSMS en `localhost,14330`), `db-init` (crea la base `planiq` y su login), `api`, `worker`, `web` y `proxy` (Caddy). En desarrollo, la API y el web recargan solos al guardar cambios.

Para QA o producción, con la base en un servidor externo: `docker compose --env-file .env -f infra/docker-compose.yml up -d --build`.

Si `http://localhost:8080` queda cargando sin responder, revisar que `HTTP_BIND=127.0.0.1` esté en `.env` (ver el comentario en `.env.example`) o usar http://127.0.0.1:8080.

## Estructura

```
api/         backend FastAPI
worker/      procesos en segundo plano (cargas Excel, sincronización Innova)
web/         frontend Next.js
infra/       Docker Compose, Dockerfiles, SQL Server de desarrollo y reverse proxy
docs/        especificación, ADR, manuales
compose.yaml entorno de desarrollo completo (incluye infra/docker-compose.yml + .dev.yml)
```

## Datos

La carpeta `cargaExcel/` contiene archivos reales de producción y **no se versiona**. Copiar `.env.example` a `.env` y completar los valores; `.env` tampoco se versiona.

## Ramas

`main` (producción) ← `qa` ← `develop` ← `feature/<fase>-<tema>`. Todo cambio entra por pull request con el CI en verde.
