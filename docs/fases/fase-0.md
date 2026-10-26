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
- `infra/docker-compose.yml`: `sqlserver` (2022, CU fijada, volumen persistente, ≥ 2 GB RAM, healthcheck), `api`, `worker`, `web`, `proxy`.
- Script de inicialización que crea la base `planiq` y el usuario de aplicación (no `sa`).
- `infra/docker-compose.dev.yml`: recarga en caliente de api/web y `C:\PlanIQ\cargaExcel` montado **solo lectura** en el worker.
- Proxy con límite de cuerpo de 300 MB ya configurado (se usa en la Fase 4).
- Dockerfiles multi-etapa de `api`, `worker` y `web` con versiones fijadas.

### F0.3 · Base del backend — `feature/f0-api-base`
- `api/pyproject.toml` con versiones exactas y lockfile; ruff + mypy.
- `core/`: configuración (pydantic-settings), logging estructurado JSON, formato único de error (`code`, `message`, `details`, `field_errors`), manejadores de excepción, paginación común.
- `db/`: engine `pyodbc` + ODBC Driver 18, sesión por request, base declarativa con mixins (`id`, auditoría, `is_active`, `rowversion`), tipo decimal serializado como string.
- Alembic con creación de esquemas `core`, `master`, `plan`, `actual`, `integration`.
- `GET /api/v1/health` (API + BD).
- Worker mínimo: proceso que arranca, lee `integration.jobs` y no hace nada aún (deja lista la cola).

### F0.4 · Autenticación y permisos — `feature/f0-auth`
- Tablas `core.users`, `core.roles`, `core.permissions`, `core.role_permissions`, `core.user_roles`, `core.user_plants`, `core.refresh_tokens`.
- Argon2, JWT de acceso corto, refresh rotativo en cookie httpOnly (revocable en BD), logout.
- Bloqueo tras 5 intentos fallidos, rate limiting en login, cambio de contraseña obligatorio en primer ingreso y tras restablecimiento.
- Arranque: administrador inicial desde variables de entorno y matriz base de permisos con los 4 roles (migración de datos idempotente).
- `require_permission(...)` y filtro de planta (`plant_id` validado contra `core.user_plants`).
- Endpoints `/auth/login`, `/refresh`, `/logout`, `/change-password`, `/me` (devuelve permisos y plantas).

### F0.5 · Auditoría central — `feature/f0-audit`
- `core.audit_log` y eventos de sesión de SQLAlchemy (insert, update con diferencias campo a campo, desactivación).
- `GET /{entidad}/{id}/history` genérico.

### F0.6 · Patrón de mantenedor en backend — `feature/f0-maintainer-api`
- Servicio/repositorio base: listado paginado del servidor con búsqueda y filtros, crear, `PATCH` con `rowversion` (409 si no coincide), activar/desactivar, historial, exportación a Excel, códigos únicos.

### F0.7 · Mantenedores de administración (API) — `feature/f0-admin-api`
- **Usuarios**: CRUD, roles, plantas, estado, último ingreso, restablecer contraseña (clave temporal), desbloquear.
- **Roles y permisos**: matriz editable, roles nuevos.
- **Plantas**: código, nombre, tipo (propia/maquila), ubicación, zona horaria (por defecto `America/Santiago`), activa. Ninguna planta precargada.
- **Turnos**: validación en `app/domain/shifts.py` (función pura): sin traslapes, cruce de medianoche calculado, cobertura de 24 h si el parámetro de la planta lo exige.
- **Parámetros**: clave, tipo, unidad, valor, vigencia; alcance global o por planta (ver decisión abierta 3).
- `app/domain/productive_date.py`: fecha productiva según turno (incluido el nocturno), con tests; la usan turnos ahora y el plan en la Fase 1.

### F0.8 · Base del frontend — `feature/f0-web-base`
- Next.js 16 + TypeScript estricto + Tailwind 4 con los tokens de la paleta; ESLint.
- Cliente API tipado desde el OpenAPI; TanStack Query; manejo de sesión con refresh.
- Grupos `(auth)` (login, cambio de contraseña) y `(app)` (layout con barra superior, selector de planta / fecha productiva / turno en la URL, navegación lateral en escritorio e inferior en celular, campana con contador vacío por ahora).
- `lib/`: formato chileno (miles con punto, coma decimal, `dd-mm-aaaa`), permisos, fechas productivas.
- Componentes UI base: botón, input numérico con coma, tarjeta, panel lateral, skeleton, estado vacío, tabla.

### F0.9 · Mantenedor genérico y pantallas — `feature/f0-maintainer-web`
- `components/maintainer`: recibe una definición (columnas, filtros, campos, esquema Zod, permisos) y entrega listado, búsqueda, panel de edición (pantalla completa en celular), activar/desactivar, exportar e historial; tarjetas en 360 px.
- Pantallas de usuarios, roles y permisos (matriz), plantas, turnos y parámetros.

### F0.10 · Tests y CI — `feature/f0-ci`
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
