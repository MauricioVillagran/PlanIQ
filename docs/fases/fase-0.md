# Fase 0 — Fundación y administración (propuesta de tareas)

Estado: **aprobada el 26-10-2026**, con las propuestas de las decisiones abiertas (registradas en [ADR 0001](../adr/0001-decisiones-iniciales.md)).

Objetivo (sección 14 de la especificación): monorepo, Docker Compose con SQL Server 2022, base nueva con Alembic, autenticación propia, auditoría central, layout responsive con la paleta, componente reutilizable de mantenedor y mantenedores de usuarios, roles y permisos, plantas, turnos y parámetros. CI funcionando.

Cada bloque es una rama `feature/f0-<tema>` desde `develop`, cerrada con PR.

---

## Bloques de trabajo

### F0.1 · Repositorio — `feature/f0-repo`
- Convertir `C:\PlanIQ` en clon de `origin` (el remoto ya tiene `main`, `qa` y `develop` con la especificación en `docs/`, `README.md` y `.gitignore`): `git init`, agregar `origin`, traer `develop` y revisar ese commit antes de agregar los archivos locales.
- Ampliar `.gitignore` (`cargaExcel/`, `.env`, almacenamiento local, artefactos de Python/Node/Playwright), agregar `.env.example` y `.gitattributes` (finales de línea LF para scripts que corren en Linux), actualizar `README.md`.
- La especificación ya está en `docs/PROMPT_Sistema_Planificacion.md`; se elimina la copia idéntica que estaba en la raíz local.
- `docs/adr/0001-decisiones-iniciales.md` con las decisiones cerradas antes de la fase y las de la Fase 0.
- Verificar que nada de `cargaExcel/` ni `.env` quede en el índice.

### F0.2 · Infraestructura — `feature/f0-infra`
- `infra/docker-compose.yml`: `api`, `worker`, `web`, `proxy` (base común a todos los entornos; la base de datos es externa).
- `infra/docker-compose.dev.yml`: `sqlserver` (2022-CU27, volumen persistente, 2 GB para el motor, healthcheck, solo en `127.0.0.1:14330`), `db-init` idempotente que crea la base `planiq` y el login de aplicación (no `sa`), recarga en caliente de api/web y `C:\PlanIQ\cargaExcel` montado **solo lectura** únicamente en el worker.
- `compose.yaml` en la raíz para que `docker compose up` levante el entorno de desarrollo completo.
- Proxy Caddy con límite de cuerpo de 300 MB (`UPLOAD_MAX_SIZE_MB`).
- Dockerfiles multi-etapa en `infra/docker/`: `python.Dockerfile` (targets `api` y `worker`, con ODBC Driver 18, usuario no root) y `web.Dockerfile` (targets `dev` y `runner` standalone).
- Workspace de uv en la raíz (`pyproject.toml` + `uv.lock`) con `api` y `worker`.
- Esqueletos mínimos para verificar la cadena completa: `/api/v1/health` y `/api/v1/health/ready` en la API, worker que se conecta y registra actividad, página provisoria del web que consulta la API. F0.3 y F0.8 los reemplazan.
- **Pendiente de verificar en la Fase 4:** el rechazo con 413 de una subida mayor a 300 MB. Caddy aplica el límite al leer el cuerpo, y todavía no existe un endpoint que lo lea.

### F0.3 · Base del backend — `feature/f0-api-base`
- Dependencias con versión exacta y `uv.lock`; ruff y mypy estricto configurados en el `pyproject.toml` raíz; grupo dev (pytest, httpx2, ruff, mypy) instalado solo en la imagen de desarrollo.
- `core/`: configuración (pydantic-settings), logging estructurado JSON con `request_id`, middleware de acceso, formato único de error (`code`, `message`, `details`, `field_errors`) con mensajes de validación en español, paginación común (`page`, `page_size`, `total`), tipo decimal serializado como string.
- `db/`: engine `pyodbc` + ODBC Driver 18, sesión por request, base declarativa con convención de nombres, mixins (`id` BIGINT identity, auditoría, `is_active`, `rowversion` con detección de conflictos → 409), tipo `UtcDateTime`.
- Alembic: `0001` crea los esquemas `core`, `master`, `plan`, `actual`, `integration`; `0002` crea `integration.jobs`. Servicio `migrate` en Compose que corre antes de api y worker.
- Cola de trabajos: encolar, tomar con `UPDLOCK, READPAST` (varios workers sin choques), progreso, reintentos con espera exponencial, fallos permanentes y reencolado de trabajos sin latido. Worker con apagado ordenado y trabajo de prueba `system.noop`.
- `GET /api/v1/health` (liveness) y `GET /api/v1/health/ready` (base y revisión del esquema).
- Base de pruebas `planiq_test` creada por `db-init`; pruebas unitarias y de integración.
- Desviación: SQLAlchemy 2.1 (estable vigente) en lugar de 2.0; mismo estilo tipado.

### F0.4 · Autenticación y permisos — `feature/f0-auth` (hecho; decisiones en [ADR 0002](../adr/0002-autenticacion-y-permisos.md))
- Además de lo previsto: se crea `master.plants` (la necesita `core.user_plants`) y el permiso `plants.all`.
- Tablas `core.users`, `core.roles`, `core.permissions`, `core.role_permissions`, `core.user_roles`, `core.user_plants`, `core.refresh_tokens`.
- Argon2, JWT de acceso corto, refresh rotativo en cookie httpOnly (revocable en BD), logout.
- Bloqueo tras 5 intentos fallidos, rate limiting en login, cambio de contraseña obligatorio en primer ingreso y tras restablecimiento.
- Arranque: administrador inicial desde variables de entorno y matriz base de permisos con los 4 roles (migración de datos idempotente).
- `require_permission(...)` y filtro de planta (`plant_id` validado contra `core.user_plants`).
- Endpoints `/auth/login`, `/refresh`, `/logout`, `/change-password`, `/me` (devuelve permisos y plantas).

### F0.5 · Auditoría central — `feature/f0-audit` (hecho)
- `core.audit_log` (migración `0005`) y eventos de sesión de SQLAlchemy: alta con valores iniciales, modificación con diferencias campo a campo, desactivación y reactivación como acciones propias, borrado con últimos valores, cambios en relaciones (roles y plantas de un usuario, permisos de un rol) registrados en el registro padre.
- `created_by` / `updated_by` se completan solos con el usuario de la sesión; cada entrada guarda el `request_id`.
- Excluidos: cola de trabajos, refresh tokens, tablas de asociación (se auditan en el padre), `last_login_at` y `failed_login_count`. La contraseña se registra como cambiada, nunca su valor. El bloqueo de cuenta sí queda auditado, como acción del sistema.
- `GET /api/v1/audit` (permiso `audit.view`) con filtros por entidad, registro, usuario, acción y fechas; respeta el acceso por planta. `record_history` queda listo para el `GET /{recurso}/{id}/history` de cada mantenedor (F0.6).

### F0.6 · Patrón de mantenedor en backend — `feature/f0-maintainer-api` (hecho)
- `app.core.maintainer`: especificación declarativa, servicio base con ganchos y fábrica de router. Endpoints uniformes: listado paginado con búsqueda (`q`), estado, filtros y orden; detalle; alta; `PATCH` parcial con `row_version` (409 con los datos vigentes); activar/desactivar; historial; `export.xlsx` con los mismos filtros.
- Validaciones comunes: campos únicos (422 por campo), obligatorios que un `PATCH` no puede vaciar, campos desconocidos rechazados, espacios recortados, acceso por planta (404 fuera de alcance).
- **Adelantado de F0.7:** el mantenedor de plantas (API) se construyó aquí como implementación de referencia y para probar el patrón.

### F0.7 · Mantenedores de administración (API) — `feature/f0-admin-api` (hecho; decisiones en [ADR 0003](../adr/0003-mantenedores-de-administracion.md))
- Entregado: usuarios (clave temporal, restablecer, desbloquear, protección del último administrador), roles y catálogo de permisos, turnos (`/shifts`, traslapes, `/shifts/coverage`), parámetros (alcance global o por planta, vigencias). Migración `0006`.
- `app.domain.shifts`: cruce de medianoche, traslapes, huecos y fecha productiva, con pruebas del turno nocturno en horario de verano e invierno.

Plan original:
- **Usuarios**: CRUD, roles, plantas, estado, último ingreso, restablecer contraseña (clave temporal), desbloquear.
- **Roles y permisos**: matriz editable, roles nuevos.
- **Plantas**: código, nombre, tipo (propia/maquila), ubicación, zona horaria (por defecto `America/Santiago`), activa. Ninguna planta precargada.
- **Turnos**: validación en `app/domain/shifts.py` (función pura): sin traslapes, cruce de medianoche calculado, cobertura de 24 h si el parámetro de la planta lo exige.
- **Parámetros**: clave, tipo, unidad, valor, vigencia; alcance global o por planta (ver decisión abierta 3).
- `app/domain/productive_date.py`: fecha productiva según turno (incluido el nocturno), con tests; la usan turnos ahora y el plan en la Fase 1.

### F0.8 · Base del frontend — `feature/f0-web-base` (hecho; decisiones en [ADR 0004](../adr/0004-base-del-frontend.md))
- Entregado: ingreso, cambio de contraseña obligatorio, sesión con refresco, layout con navegación inferior (celular) y lateral (escritorio), selector de planta/fecha/turno en la URL, campana, inicio y perfil, componentes base y formato chileno. Seed de desarrollo (`python -m app.seed`). Verificado en 360 px y escritorio.
- Corregido al probar con datos reales del seed: el listado de usuarios fallaba con 500 cuando un usuario tenía roles o plantas.

Plan original:
- Next.js 16 + TypeScript estricto + Tailwind 4 con los tokens de la paleta; ESLint.
- Cliente API tipado desde el OpenAPI; TanStack Query; manejo de sesión con refresh.
- Grupos `(auth)` (login, cambio de contraseña) y `(app)` (layout con barra superior, selector de planta / fecha productiva / turno en la URL, navegación lateral en escritorio e inferior en celular, campana con contador vacío por ahora).
- `lib/`: formato chileno (miles con punto, coma decimal, `dd-mm-aaaa`), permisos, fechas productivas.
- Componentes UI base: botón, input numérico con coma, tarjeta, panel lateral, skeleton, estado vacío, tabla.

### F0.9 · Mantenedor genérico y pantallas — `feature/f0-maintainer-web` (hecho)
- Entregado: `MaintainerPage` genérico y las pantallas de usuarios (clave temporal, restablecer, desbloquear), roles (permisos por módulo), plantas, turnos (de la planta del contexto, con cobertura de 24 h) y parámetros (alcance y vigencia). Sección Configuración en el menú. Verificado en el navegador a 360 px y en escritorio: alta, error por campo, edición, conflicto 409, historial y desactivación.

Plan original:
- `components/maintainer`: recibe una definición (columnas, filtros, campos, esquema Zod, permisos) y entrega listado, búsqueda, panel de edición (pantalla completa en celular), activar/desactivar, exportar e historial; tarjetas en 360 px.
- Pantallas de usuarios, roles y permisos (matriz), plantas, turnos y parámetros.

### F0.10 · Tests y CI — `feature/f0-ci` (hecho)
- Playwright (`web/e2e`) con los criterios de aceptación en 360 px y escritorio contra un stack aislado con imágenes de producción (`scripts/e2e.sh`); Vitest para formato chileno, fechas y redirecciones; GitHub Actions con tres trabajos (backend, frontend, e2e).
- SQL Server pasó a `infra/docker-compose.db.yml` para reutilizarlo en desarrollo, e2e y CI.
- Corregido: una planta recién creada no aparecía en el selector de contexto hasta volver a ingresar.

Plan original:
- pytest: dominio (turnos, fecha productiva), auth (bloqueo, refresh, cambio obligatorio), permisos y filtro de planta, auditoría, concurrencia 409. Integración contra SQL Server en contenedor.
- Playwright: primer ingreso con cambio de contraseña, crear planta y turnos, crear usuario por rol, bloqueo por 5 intentos; en 360 px y escritorio.
- GitHub Actions en cada PR: ruff, mypy, ESLint, `tsc`, pytest (con SQL Server como servicio), Playwright, build de imágenes.

### F0.11 · Cierre de fase — `feature/f0-docs`
- README para levantar todo desde cero en Windows con Docker Desktop.
- Completar la sección "Comandos" de `CLAUDE.md`.
- `docs/fases/fase-0-entrega.md`: criterios de aceptación con evidencia, y lo pendiente.

---

## Criterios de aceptación (de la especificación) y cómo se verifican

| Criterio | Evidencia prevista |
|---|---|
| `docker compose up` levanta todo desde cero siguiendo solo el README | Ejecución en limpio documentada |
| Admin inicial entra y se le exige cambiar contraseña | Playwright |
| Crea Planta Victoria Sur con turnos, incluido uno que cruza medianoche | Playwright + test de dominio |
| Crea un usuario de cada rol y le asigna plantas | Playwright |
| Cada usuario ve solo lo que su rol permite | Tests de API por permiso + Playwright |
| Cinco intentos fallidos bloquean la cuenta | pytest + Playwright |
| Todo cambio aparece en el historial del registro | pytest de auditoría |
| Mantenedores funcionan en 360 px y escritorio | Playwright con ambos viewports + capturas |
| CI de GitHub Actions funcionando | PR con CI en verde |

---

## Decisiones de la Fase 0 (cerradas)

Aprobadas tal como se propusieron; detalle en [ADR 0001](../adr/0001-decisiones-iniciales.md), decisiones 8 a 14.

1. **Reverse proxy**: Caddy.
2. **Gestores de paquetes**: `uv` para Python y `npm` para Node.
3. **Alcance de parámetros**: `plant_id` nulo = valor global; un valor por planta lo reemplaza.
4. **Desbloqueo de cuenta**: manual por Admin; automático opcional por parámetro, desactivado por defecto.
5. **Contraseñas y sesión**: mínimo 10 caracteres; acceso 15 min; refresh 12 h; todo configurable.
6. **Protección de ramas**: `main` y `qa` protegidas en GitHub; como `gh` no está instalado, la activa el responsable (pasos en el PR de F0.1) o se instala `gh`.
7. **Python local**: no requerido; el backend corre en Docker.
