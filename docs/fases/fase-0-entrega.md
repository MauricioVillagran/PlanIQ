# Fase 0 — Nota de entrega

- **Fecha:** 27-10-2026
- **Estado:** criterios de aceptación cumplidos (9 de 9), con la evidencia de abajo.
- **Rama:** `develop` (PR #1 a #12 y el de cierre). Falta promover a `qa` y `main`.

## Qué se entregó

| Bloque | Contenido | PR |
|---|---|---|
| F0.1 Repositorio | Reglas del proyecto (`CLAUDE.md`), `.gitignore`, ADR 0001 | #1 |
| F0.2 Infraestructura | Docker Compose, SQL Server 2022, Caddy, Dockerfiles | #2 |
| F0.3 Base del backend | Configuración, logs JSON, errores únicos, SQLAlchemy con `rowversion`, Alembic, cola de trabajos y worker | #3 |
| F0.4 Autenticación | Usuarios, roles, permisos, JWT con refresco rotativo, bloqueo, cambio obligatorio, acceso por planta, admin inicial (ADR 0002) | #4 |
| F0.5 Auditoría | `core.audit_log` automático con diferencias campo a campo, `GET /audit` | #5 |
| F0.6 Patrón de mantenedor (API) | Listado, alta, edición con 409, activar, historial, Excel; API de plantas | #6 |
| F0.7 Mantenedores (API) | Usuarios, roles y permisos, turnos (fecha productiva), parámetros (ADR 0003) | #7 |
| F0.8 Base del frontend | Ingreso, sesión, layout responsive, selector de planta/fecha/turno, componentes, formato chileno (ADR 0004) | #8 |
| F0.9 Pantallas | Mantenedor genérico y pantallas de Configuración | #9 |
| F0.10 Pruebas y CI | Playwright 360 px y escritorio, Vitest, GitHub Actions | #10, #11, #12 |
| F0.11 Cierre | README final, guía de operación y respaldos, esta nota | — |

**Pruebas:** 170 de backend (pytest, contra SQL Server), 29 unitarias de frontend (Vitest) y 13 end-to-end (Playwright: primer ingreso más 6 flujos en escritorio y 6 en celular, uno de ellos solo para celular). CI en verde en `develop`: [corrida 40602560671](https://github.com/MauricioVillagran/PlanIQ/actions/runs/40602560671).

## Criterios de aceptación (sección 14)

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | `docker compose up` levanta todo desde cero en Windows con Docker Desktop siguiendo solo el README | ✅ | Clon nuevo de `develop` en este equipo (Windows 11, Docker Desktop 29.4) siguiendo el README paso a paso: listo en 69 s, todos los servicios sanos, `schema_revision` 0006, ingreso disponible, admin con cambio obligatorio y la API sin token responde 401. Las imágenes base ya estaban descargadas; en un equipo nuevo se suma la descarga de SQL Server. Además, el job e2e del CI construye y levanta el stack desde cero en un runner limpio en cada PR. |
| 2 | El administrador inicial entra y se le exige cambiar la contraseña | ✅ | e2e `first-login.setup.ts` (fuerza el cambio, bloquea el resto del sistema mientras tanto, la clave inicial deja de servir); pytest `test_first_login_requires_password_change`, `test_initial_admin_is_created_once_and_must_change_password` |
| 3 | Crea la Planta Victoria Sur con sus turnos, incluido uno que cruza medianoche | ✅ | e2e `crea la planta y sus turnos día y noche (cruza medianoche)` en escritorio y 360 px: crea VS, Día 08–20 y Noche 20–08, verifica la cobertura de 24 h y rechaza código repetido y turno traslapado. Dominio: 18 pruebas de `app.domain.shifts`, incluida la fecha productiva del turno noche en verano (UTC-3) e invierno (UTC-4) |
| 4 | Crea un usuario de cada rol y le asigna plantas | ✅ | e2e `crea un usuario de cada rol con acceso a la planta` (4 roles, clave temporal leída del diálogo); pytest `test_create_user_returns_temporary_password_once` |
| 5 | Cada usuario ve solo lo que su rol permite | ✅ | e2e `cada usuario cambia su clave temporal y ve solo lo que su rol permite` (menú, botones de edición y "Sin acceso" por URL directa); pytest `test_permissions.py` (matriz, `require_permission`, acceso por planta, rol desactivado) y `test_users_require_users_admin` |
| 6 | Cinco intentos fallidos bloquean la cuenta | ✅ | e2e `cinco intentos fallidos bloquean la cuenta y el administrador la desbloquea`; pytest `test_five_failed_attempts_lock_the_account`, `test_unlock_after_failed_attempts` |
| 7 | Todo cambio aparece en el historial del registro | ✅ | e2e `todo cambio queda en el historial del registro`; pytest `test_audit.py` (alta, modificación, desactivación, relaciones, contraseña enmascarada, `request_id`) y `test_history_lists_audited_changes` |
| 8 | Los mantenedores funcionan en 360 px y en escritorio | ✅ | Todos los flujos e2e corren en los proyectos `escritorio` (1280 px) y `movil` (360 px); `sin scroll horizontal y con objetivos táctiles de 44 px` recorre las 5 pantallas. Revisión manual en el navegador durante F0.8 y F0.9 |
| 9 | CI de GitHub Actions funcionando | ✅ | `.github/workflows/ci.yml`: backend, frontend y e2e en cada PR y push a `develop`/`qa`/`main`; corridas en verde en los PR #11 y #12 y en `develop` |

Requisitos de cierre de fase (sección 14): migraciones aplicadas (0001–0006, verificadas contra los modelos por `test_migrations_match_models`), pruebas en verde, datos ficticios cargables (`python -m app.seed`), documentación en `/docs` y esta nota.

## Desviaciones de la especificación (todas registradas)

| Tema | Especificación | Implementado | Dónde |
|---|---|---|---|
| Versiones | Next.js 15, Python 3.12, SQLAlchemy 2.0 | Next.js 16, Python 3.13, SQLAlchemy 2.1 (estables vigentes); TypeScript 5.9 y ESLint 9 por compatibilidad | ADR 0001 (5), ADR 0004 (1) |
| Plan diario en la API | `/harvest-plans/{id}` | `/daily-plans/{id}` (aún no implementado; rige desde la Fase 1) | ADR 0001 (6) |
| Turnos en la API | `/plants/{id}/shifts` | `/shifts?plant_id=` | ADR 0003 (1) |
| Tablas temporales | Todo `plan.*` | Solo las tablas editables del plan y las reglas | ADR 0001 (4) |
| Auditoría | Toda escritura | Las cargas masivas se auditan por lote | ADR 0001 (3) |

## Pendiente

**De tu lado:**
- Proteger `main`, `qa` y `develop` en GitHub exigiendo los checks *Backend*, *Frontend* y *End-to-end*. El PR #10 se fusionó antes de que terminara su CI.
- Promover la Fase 0 de `develop` a `qa` y luego a `main` con un PR.
- Definir el servidor de QA y producción (on-premise o nube): de eso dependen HTTPS, la política de respaldos y la edición de SQL Server ([operacion.md](../operacion.md)).

**Técnico, ya agendado:**
- El rechazo de una subida mayor a 300 MB (413) se verifica en la Fase 4, cuando exista el endpoint de carga; el límite ya está configurado en Caddy.
- Actualizar a ESLint 10 cuando los plugins de Next lo declaren compatible.
- El límite de intentos de ingreso por IP vive en memoria: correcto con una réplica de la API; con varias, moverlo a SQL Server (ADR 0002).
- La política de contraseñas solo exige largo mínimo y que sea distinta del usuario y de la actual; reglas adicionales (complejidad, vencimiento) están por definir.
- La campana de notificaciones queda sin contenido hasta la Fase 1; la PWA y el manual por rol son de la Fase 6.

**Datos de desarrollo:** la base local tiene la Planta Demo y los usuarios `demo.*` del seed, más registros de prueba desactivados (planta `PRU`, usuarios `demo.nuevo` y `demo.prueba`). El usuario `admin` real sigue con su clave inicial y cambio obligatorio.
