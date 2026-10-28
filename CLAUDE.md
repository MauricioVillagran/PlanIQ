# PlanIQ — Reglas permanentes del proyecto

Sistema web de planificación productiva para plantas de proceso de salmón: un único plan diario versionado por planta y fecha productiva, avance real casi en línea y cumplimiento contra plan.

- Especificación completa: [`docs/PROMPT_Sistema_Planificacion.md`](docs/PROMPT_Sistema_Planificacion.md). Ante cualquier duda funcional, manda ese documento.
- Decisiones de arquitectura: `docs/adr/`. Una decisión nueva o un cambio a la especificación se registra como ADR.
- Idioma: interfaz, documentación y commits en **español**. Código, tablas, columnas, variables y endpoints en **inglés**.

---

## 1. Forma de trabajar

1. **Una fase a la vez** (sección 14 de la especificación). Al inicio de cada fase, listar las decisiones abiertas y preguntar antes de asumir. Una fase no empieza hasta que la anterior cumple sus criterios de aceptación.
2. **No inventar reglas de negocio.** Si un cálculo, rango, umbral o prioridad no está definido, se deja como parámetro configurable (`master.parameters`) y se señala.
3. **Si la especificación se contradice** con lo que aparece al implementar, o una decisión resulta técnicamente mala, decirlo con argumento y alternativa antes de seguir. Nunca desviarse en silencio.
4. Toda pantalla se prueba en **360 px y en escritorio** antes de darse por terminada.
5. Al cerrar una fase, revisar uno por uno los criterios de aceptación con evidencia (test, captura o paso reproducible) e informar lo que se cumple y lo que no.

---

## 2. Stack

Versiones **estables vigentes, fijadas a versión exacta** en `pyproject.toml`, `package.json`, lockfiles e imágenes Docker. Nunca `latest` ni rangos abiertos. No hay Python instalado en el equipo de desarrollo: el backend se ejecuta y prueba dentro de Docker.

| Capa | Tecnología |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.1 (estilo tipado `Mapped[]`), Pydantic v2, pydantic-settings, Alembic |
| Base de datos | SQL Server 2022 (imagen `mcr.microsoft.com/mssql/server:2022-CU<n>-ubuntu-22.04`, CU fijada), `pyodbc` + ODBC Driver 18. Base `planiq`. Réplicas Innova por conexión separada **solo lectura** |
| Frontend | Next.js 16 (App Router), React 19, TypeScript estricto, Tailwind CSS 4, TanStack Query, TanStack Table, React Hook Form + Zod, Apache ECharts |
| Worker | Proceso Python separado; cola persistida en `integration.jobs` (sin Redis) |
| Infra | Docker Compose: `sqlserver` (solo dev), `api`, `worker`, `web`, `proxy` (Caddy) |
| Paquetes | `uv` (Python, con `uv.lock`) y `npm` (Node, con `package-lock.json`) |
| Tests | pytest (dominio, motor de reglas, importación, integración API+BD) y Playwright (flujos críticos) |
| CI | GitHub Actions: lint, type-check, tests backend y frontend, build de imágenes en cada PR |

No usar Power BI. No WebSockets: seguimiento por polling (`refetchInterval`, 1–5 min, parametrizable). No app nativa: web responsive mobile-first, PWA opcional sin offline.

---

## 3. Estructura del repositorio

```
api/        FastAPI. app/{core,db,modules/<módulo>,domain}, migrations/, tests/
worker/     cargas Excel, sincronización Innova, recálculos
web/        Next.js. src/{app/(auth),app/(app),components/ui,components/maintainer,features,lib}, e2e/
infra/      docker-compose.yml, docker-compose.dev.yml, docker/ (Dockerfiles), sqlserver/init/, proxy/ (Caddy)
compose.yaml  entrada de desarrollo en la raíz (incluye los dos compose de infra/)
pyproject.toml + uv.lock  workspace de uv con api y worker (el worker importa `app` de la API)
docs/       especificación, adr/, manual por rol, notas de fase
.github/workflows/
```

### Backend
- Cada módulo: `router.py` (HTTP, validación de entrada, permisos) → `service.py` (casos de uso, transacciones) → `repository.py` (consultas) + `models.py` + `schemas.py`.
- **Routers sin lógica de negocio.**
- Cálculos (biomasa, WFE, cobertura, cumplimiento, fecha productiva, motor de reglas, simulación de grader) en `app/domain/` como **funciones puras**: sin BD, sin FastAPI, testeables de forma aislada.
- Reglas de negocio validadas **siempre en el backend** (fuente de verdad); Zod en el frontend es solo comodidad.

### Frontend
- Estado global de planta, fecha productiva y turno **en la URL** (un enlace compartido abre la misma vista): leerlo y cambiarlo con `useAppContext()`; los enlaces internos usan `href(path)` para conservarlo.
- Llamadas a la API solo con el cliente tipado `api` de `src/lib/api/client.ts` + `unwrap()` dentro de TanStack Query; tras cambiar endpoints, `npm run api:types`. El token de acceso vive solo en memoria (ADR 0004).
- Colores solo con los tokens de la paleta (`bg-teal`, `text-navy`, `text-coral`...), nunca hex sueltos; cifras con la clase `num` (DM Mono). Componentes base en `src/components/ui`.
- Formato: `formatNumber`, `formatDate`, `formatDateTime` y `parseDecimalInput` de `src/lib/format.ts`; fechas por defecto con `todayIn()` (zona de la planta, no del navegador).
- Un módulo nuevo se agrega al menú en `src/lib/navigation.ts` con el permiso que lo habilita.
- Componente genérico de mantenedor (`components/maintainer`): una pantalla de mantenedor es `<MaintainerPage definition={...} />` con un `MaintainerDefinition` en `src/features/<módulo>/` (columnas, tarjeta para celular, filtros, formulario con React Hook Form + Zod, permisos). Entrega listado paginado del servidor, búsqueda, orden, panel lateral (pantalla completa en celular), conflicto 409 con "Cargar datos actuales", activar/desactivar, exportar a Excel e historial. Referencia: [plants.tsx](web/src/features/plants/plants.tsx).
  - En el formulario, enviar con `submitWithApiErrors` para que los errores de la API aparezcan bajo cada campo.
  - Campos que no cambian tras el alta (código, usuario, clave): mostrarlos como texto en edición, no como input deshabilitado.
  - Paneles y diálogos se dibujan con portal al `body` (un ancestro con `transform` rompería `position: fixed`).
- Los permisos ocultan acciones en la UI, pero la API los valida siempre.

---

## 4. Convenciones de API

- Todo bajo `/api/v1`, documentado en OpenAPI con ejemplos; el cliente del frontend se tipa desde el OpenAPI.
- El plan diario se expone como **`/daily-plans/{planId}`**, con sub-recursos (`/harvest-entries`, `/allocations`, `/frozen-requirements`, `/simulations`, `/versions`...). Creación y consulta por planta y fecha: `/plants/{id}/daily-plans/{date}`. *(Cambia las rutas `/harvest-plans` de la especificación; ver ADR.)*
- Error único: `{ code, message, details, field_errors }`.
- Paginación: `page`, `page_size`, `total`. Filtros por query string.
- Fechas productivas `YYYY-MM-DD`; marcas de tiempo ISO 8601 con zona.
- Pesos, kilos y montos como **string decimal** en JSON.
- Concurrencia optimista: cada edición envía el `rowversion`; si no coincide → **409** con los datos actuales.
- Permisos con la dependencia `require_permission("plan.publish")` (`app.modules.auth.dependencies`); permisos granulares asignados a roles, nunca `if role == ...`. Un permiso nuevo se agrega con una migración que lo inserta en `core.permissions` y lo asigna a los roles base que correspondan.
- **Ninguna consulta operacional sin `plant_id` validado contra las plantas del usuario**: `ensure_plant_access(user, plant_id)` en cada endpoint por planta; en listados, filtrar por `user.plant_ids` (None = todas, permiso `plants.all`).
- `CurrentUserDep` bloquea a quien debe cambiar su contraseña; solo `/auth/*` usa la variante que lo permite.
- Transacciones: el servicio confirma con `session.commit()` al terminar el caso de uso; la sesión llega por `SessionDep`.
- Auditoría automática (`app.modules.audit.listener`): toda escritura por objetos del ORM queda en `core.audit_log` con usuario, `request_id` y diferencias campo a campo, y completa `created_by`/`updated_by`. Por eso **las escrituras de negocio se hacen con objetos del ORM, no con `update()`/`insert()` masivos** (estos no se auditan; solo se usan en tablas excluidas o en cargas auditadas por lote).
  - Excluir un modelo: `__audit__ = False`. Excluir campos ruidosos: `__audit_exclude__`. Ocultar valores sensibles: `__audit_mask__`.
  - Procesos sin usuario (worker, arranque) quedan como acción del sistema (`user_id` nulo). Un proceso nuevo debe llamar a `register_audit_listeners()` al iniciar.
  - Historial de un registro para los mantenedores: `app.modules.audit.service.record_history`.
  - Pantalla Configuración › Auditoría (`audit.view`). Una tabla auditada nueva agrega su nombre en español en `app/modules/audit/labels.py` y sus nombres de campo en `FIELD_LABELS` de `web/src/features/audit/audit-page.tsx`.
- Decisiones de autenticación y matriz de permisos: [ADR 0002](docs/adr/0002-autenticacion-y-permisos.md).

### Mantenedores (API)
Todo mantenedor se arma con `app.core.maintainer`, nunca con endpoints escritos a mano. Referencia: [plants/router.py](api/app/modules/plants/router.py).
- Esquemas: `XxxCreate(StrictInput)`, `XxxUpdate(VersionedUpdate)` con todos los campos opcionales, `XxxOut(MaintainerOut)`.
- Un `MaintainerSpec` declara modelo, permisos de ver y editar, búsqueda, filtros, orden, campos únicos, `plant_field` y columnas de exportación; `build_maintainer_router(spec)` genera listado, detalle, alta, edición con `row_version` (409 con `details.current`), activar/desactivar, historial y `export.xlsx`.
- Reglas propias: heredar `MaintainerService` y redefinir `apply`, `validate` o `before_set_active`; pasar la clase a `build_maintainer_router(spec, XxxService)`.
- Un registro fuera de las plantas del usuario responde 404 (no se revela que existe).
- Rutas propias de un mantenedor (por ejemplo `/shifts/coverage`, `/users/{id}/reset-password`) se agregan al router devuelto por la fábrica; las rutas genéricas usan `{item_id:int}` y no las tapan.
- Parámetros de negocio: leerlos con `app.modules.parameters.values.get_parameter(session, key, plant_id)`; nunca constantes en código. Decisiones de usuarios, roles, turnos y parámetros: [ADR 0003](docs/adr/0003-mantenedores-de-administracion.md).

---

## 5. Base de datos

- Esquemas: `core`, `master`, `plan`, `actual`, `integration`.
- PK `id BIGINT IDENTITY`. `plant_id` en toda tabla operacional. Auditoría `created_at`, `created_by`, `updated_at`, `updated_by`. Borrado lógico con `is_active` cuando el registro tiene historia. Reglas con `valid_from`/`valid_to` y `version`.
- Pesos y cantidades en `DECIMAL(10,3)` (u otra precisión `DECIMAL` justificada). **Nunca `FLOAT`** para kilos, cajas o piezas.
- Fechas y horas almacenadas en **UTC**; se interpretan en la zona de la planta (por defecto `America/Santiago`).
- `rowversion` en toda tabla editable.
- **Tablas temporales (system-versioned)** en las tablas editables del plan (`plan.daily_plans`, `plan.harvest_entries`, `plan.harvest_entry_quality_mix`, `plan.grader_program_assignments`, `plan.shift_production_plans`, `plan.commercial_allocations`, `plan.frozen_requirements`) y en `master.grading_rules` y `master.downgrade_rules`. **No** llevan: `plan.grader_simulations`, `plan.grader_simulation_results` (versionadas por ejecución), `plan.notifications`, `plan.change_events`, ni `actual.*`. Definir `HISTORY_RETENTION_PERIOD`.
- Alembic crea tablas temporales, triggers y columnstore con **SQL explícito** (`op.execute`), con su `downgrade` correspondiente.
- `actual.grader_piece_records`: índice **columnstore agrupado**, sin tabla temporal; trazabilidad por `import_batch_id`.
- Vistas indexadas solo cuando una medición lo justifique.
- El diseño debe funcionar en **SQL Server Express** (dev/QA): 10 GB por base. Vigilar el crecimiento de `actual.*` y del historial temporal.

### Rangos (calibre, peso, puertas de grader)
- Todos los rangos son **semiabiertos `[min, max)`**: `min` incluido, `max` excluido. `0–1,8` y `1,8–2,8` son contiguos, sin hueco ni traslape; 1,8 pertenece al segundo. Un tramo final abierto se modela con `max` nulo ("6-Up").
- Validación en dos capas: servicio del backend (mensaje claro) y respaldo en la BD (`CHECK (min < max)` + trigger `AFTER INSERT, UPDATE`).
- El traslape es error **solo entre registros activos del mismo tipo de producto cuyos periodos de vigencia se cruzan**. Una versión nueva con vigencia posterior no choca con la anterior.
- En programas de grader, que varias puertas compartan rango es **válido** (reparto de clientes).

### Parámetros
- `master.parameters` con clave, tipo, unidad, valor y vigencia. `plant_id` nulo = valor global; un valor de la planta lo reemplaza para esa planta.

### Turnos y fecha productiva
- La producción se imputa a la **fecha productiva del inicio del turno**, aunque el turno cruce medianoche.
- Los turnos de una planta nunca se traslapan. Si el parámetro de planta de cobertura completa está activo, deben cubrir 24 h sin huecos; por defecto se permiten huecos.

---

## 6. Auditoría

- Mecanismo central con eventos de sesión de SQLAlchemy → `core.audit_log` (usuario, fecha, entidad, id, diferencias) para toda inserción, modificación y desactivación hecha por el ORM.
- **Excepción explícita:** las cargas masivas (staging con `fast_executemany` + `INSERT ... SELECT`) no se auditan fila a fila; se auditan **a nivel de lote** en `integration.import_batches` (usuario, fecha, archivo original, versión del perfil, filas, resultado, errores). Anular un lote es una acción auditada.
- Las tablas temporales complementan la auditoría en plan y reglas.

---

## 7. Datos y seguridad

- **`cargaExcel/` contiene datos reales de producción**: está en `.gitignore`, nunca se sube, nunca se usa en seeds ni tests. Para tests se generan archivos ficticios con la misma estructura y valores inventados.
- No inventar el significado de las columnas de los archivos de grader: inspeccionarlos, informar la estructura y confirmar con el usuario (sobre todo peso de entrada/salida y unidades). El archivo se configura como **perfil de carga desde la aplicación**; no se escribe un lector específico en código.
- Seeds siempre con datos ficticios. Ninguna planta, centro ni maestro escrito en código: todo se crea desde los mantenedores. El primer arranque solo trae el administrador inicial (credenciales por variable de entorno, cambio obligatorio al primer ingreso) y la matriz de permisos base.
- Toda credencial por variable de entorno. Solo `.env.example` versionado; `.env` en `.gitignore`.
- Contraseñas Argon2 (mínimo 10 caracteres); JWT de acceso de 15 min + refresh rotativo de 12 h en cookie httpOnly, revocable en BD; bloqueo tras 5 intentos fallidos, desbloqueo manual por Admin (automático solo si se activa por parámetro); rate limiting en login. Todos estos valores son configurables.

---

## 8. Git

- Repositorio: `https://github.com/MauricioVillagran/PlanIQ.git` (`origin`). Raíz local: `C:\PlanIQ`.
- Ramas: `main` (producción) ← `qa` ← `develop`. `main` y `qa` protegidas, solo por PR con CI en verde.
- Trabajo diario en `feature/<fase>-<tema>` desde `develop` (ej. `feature/f0-auth`), integrado por PR hacia `develop`.
- Commits pequeños, uno por cambio lógico, **en español**, en modo imperativo (ej. `Agrega mantenedor de plantas`).
- **Antes de cada commit**: verificar que no se incluyan `.env`, credenciales ni nada de `cargaExcel/`.

---

## 9. UX

- Mobile-first desde **360 px**. Navegación inferior en celular, lateral en escritorio. Nunca scroll horizontal de página.
- Objetivos táctiles ≥ 44 px. Inputs numéricos con teclado numérico y coma decimal.
- Formato chileno: miles con punto, decimales con coma, fechas `dd-mm-aaaa`.
- Selector de planta, fecha productiva y turno siempre visible. Indicador de "última actualización" en pantallas con polling.
- Skeletons al cargar; estados vacíos con acción sugerida.
- Paleta ThemeDaaS: teal `#0096A0` (cumplimiento, acciones primarias), azul oscuro `#324664` (texto y títulos), coral `#FA6E5A` (solo alertas y desvíos), gris claro `#D2D2CD`, teal claro `#80CAD0`, coral claro `#FCB7AC`, azul medio `#6F8CB7`, fondo `#EDEDEB`, tarjetas `#FFFFFF`.

---

## 10. Comandos

Desde la raíz del repositorio (`C:\PlanIQ`):

| Acción | Comando |
|---|---|
| Levantar desarrollo | `docker compose up -d --build` |
| Estado y logs | `docker compose ps` · `docker compose logs -f api` |
| Detener (conserva datos) | `docker compose down` |
| Borrar también la base | `docker compose down -v` (destructivo: pedir confirmación) |
| Regenerar `uv.lock` (sin Python local) | `docker run --rm -v "C:\PlanIQ:/w" -w /w python:3.13.18-slim-bookworm sh -c "pip install -q uv==0.13.5 && uv lock"` |
| Tests del backend | `docker compose exec -w /workspace/api api pytest` (solo unitarios: `-m "not integration"`) |
| Lint y formato | `docker compose exec -w /workspace api ruff check api worker/worker` · `ruff format api worker/worker` |
| Tipos | `docker compose exec -w /workspace api mypy api/app api/tests worker/worker` |
| Aplicar migraciones | `docker compose run --rm migrate` (también corre solo en cada `up`) |
| Nueva migración | `docker compose exec -w /workspace/api api alembic revision --autogenerate -m "<descripción>"`; revisarla siempre a mano (tablas temporales, triggers y columnstore van con `op.execute`) |
| Datos ficticios de desarrollo | `docker compose exec -w /workspace/api api python -m app.seed` (usuarios `demo.*` con `DEV_SEED_PASSWORD`) |
| Frontend: lint, tipos y pruebas | `cd web && npm run lint && npm run typecheck && npm test` (Node local; Vitest) |
| Pruebas end-to-end | `bash scripts/e2e.sh` (stack aislado `planiq-e2e` en el puerto 8090, imágenes de producción, base nueva; `--down` lo baja al terminar; otros argumentos van a Playwright, por ejemplo `-g "historial"`) |
| Frontend: regenerar tipos de la API | `cd web && npm run api:types` (con la API arriba; `API_OPENAPI_URL` cambia el origen) |
| Frontend: dependencias nuevas | `cd web && npm install <paquete>@<versión exacta>` y luego `docker compose up -d --build web` |
| QA / producción | `docker compose --env-file .env -f infra/docker-compose.yml up -d --build` |

En Git Bash, anteponer `MSYS_NO_PATHCONV=1` a los comandos con `-w /workspace...` para que no convierta la ruta.

- URL de desarrollo: `http://localhost:<HTTP_PORT>` (8080 por defecto); API en `/api/v1`, OpenAPI en `/api/docs`. SQL Server en `localhost,14330`.
- Puertos 1433, 8000 y 80 están ocupados por otros proyectos en este equipo; no usarlos.
- Con Docker Desktop + WSL, publicar puertos en `127.0.0.1` (`HTTP_BIND`): publicar en `0.0.0.0` deja `localhost` colgado por el reenvío IPv6 de WSL.
- En desarrollo el web usa `next dev --webpack` con polling: Turbopack no detecta cambios en volúmenes montados desde Windows.

- Pruebas de integración contra `planiq_test` (la crea `db-init`): migración una vez por sesión y cada prueba dentro de una transacción que se revierte. Nunca contra `planiq`.
- Migraciones numeradas a mano (`0001`, `0002`...), con `downgrade`. La prueba `test_migrations_match_models` falla si los modelos y las migraciones divergen.
- Trabajos en segundo plano: encolar con `app.modules.jobs.repository.enqueue`; registrar el handler en `worker/worker/handlers.py`. `PermanentJobError` para errores que no se resuelven reintentando.

- Compose en capas: `infra/docker-compose.yml` (común) + `docker-compose.db.yml` (SQL Server en contenedor: desarrollo, e2e y CI) + `docker-compose.dev.yml` (recarga en caliente) o `docker-compose.ci.yml` (imagen de la API con herramientas de prueba). `ENV_FILE` elige el archivo de entorno de los servicios.
- Pruebas end-to-end en `web/e2e`: los criterios de aceptación se prueban en dos proyectos de Playwright, `escritorio` (1280 px) y `movil` (360 px), después de `primer-ingreso`. Cada proyecto crea sus propios datos (sufijo `e` o `m`). Nunca correrlas contra la base de desarrollo.
- CI (`.github/workflows/ci.yml`): backend (ruff, mypy, pytest con SQL Server), frontend (lint, tipos, Vitest, build) y e2e en cada pull request. Un cambio no se fusiona con el CI en rojo.
