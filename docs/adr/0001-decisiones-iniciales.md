# ADR 0001 — Decisiones iniciales antes de la Fase 0

- **Estado:** aceptada
- **Fecha:** 26-10-2026
- **Contexto:** al revisar la especificación (`docs/PROMPT_Sistema_Planificacion.md`) aparecieron puntos ambiguos o técnicamente débiles. Se resolvieron con el responsable del proyecto antes de escribir código. Donde una decisión modifica la especificación, prevalece este ADR.

---

## 1. Rangos semiabiertos `[min, max)`

**Problema.** La especificación exige que los calibres no se traslapen ni dejen huecos, pero usa rangos como `0–1,8 / 1,8–2,8` sin decir a cuál pertenece el borde.

**Decisión.** Todos los rangos del sistema (calibres, matriz de calibrado, reglas de degradación, puertas de programas de grader, tramos de la simulación) son semiabiertos: `min` incluido, `max` excluido. Un tramo final abierto ("6-Up") se modela con `max` nulo.

**Consecuencia.** `0–1,8` y `1,8–2,8` son contiguos y válidos. El validador detecta huecos y traslapes con una sola regla.

## 2. Traslapes de calibre según vigencia

**Problema.** Las reglas tienen `valid_from`, `valid_to` y versión. Un trigger que compare todos los registros haría chocar cada versión nueva con la anterior.

**Decisión.** Un traslape es error solo entre registros **activos** del **mismo tipo de producto** cuyos **periodos de vigencia se cruzan**. Se valida en el servicio del backend (mensaje claro) y, como respaldo, con `CHECK (min < max)` y un trigger `AFTER INSERT, UPDATE`.

## 3. Auditoría de cargas masivas por lote

**Problema.** "Auditoría de toda escritura" no es compatible con la carga masiva de piezas (`fast_executemany` + `INSERT ... SELECT`), que no pasa por los eventos del ORM y generaría millones de filas de auditoría.

**Decisión.** La auditoría central (eventos de SQLAlchemy → `core.audit_log`) cubre todo lo editable. Las cargas masivas se auditan a nivel de lote en `integration.import_batches` (usuario, fecha, archivo original, versión del perfil, filas, resultado y errores). Anular un lote es una acción auditada.

## 4. Alcance de las tablas temporales

**Problema.** La especificación pide tablas temporales en todo `plan.*`. En resultados de simulación y notificaciones no aportan y hacen crecer el historial, lo que pesa con el límite de 10 GB de SQL Server Express.

**Decisión.** Llevan versionado de sistema solo las tablas editables del plan (`daily_plans`, `harvest_entries`, `harvest_entry_quality_mix`, `grader_program_assignments`, `shift_production_plans`, `commercial_allocations`, `frozen_requirements`) y las reglas (`master.grading_rules`, `master.downgrade_rules`). Se excluyen `plan.grader_simulations` y `plan.grader_simulation_results` (ya versionadas por ejecución), `plan.notifications`, `plan.change_events` y `actual.*`. Se define `HISTORY_RETENTION_PERIOD`.

## 5. Versiones del stack

**Problema.** La especificación fija Next.js 15, Python 3.12 y la imagen `mssql/server:2022-latest`. Hay versiones estables más nuevas, y `latest` no es reproducible.

**Decisión.** Se usan las versiones estables vigentes al instalar (Next.js 16, React 19, Python 3.13), fijadas a versión exacta con lockfile. SQL Server se mantiene en **2022**, con la imagen fijada a una CU concreta (`2022-CU<n>-ubuntu-22.04`).

## 6. Recurso `daily-plans`

**Problema.** El modelo usa `plan.daily_plans` como unidad central (cosecha, producción, comercial, congelados), pero la API lo expone como `/harvest-plans/{planId}`.

**Decisión.** El recurso es `/daily-plans/{planId}`, con sub-recursos (`/harvest-entries`, `/allocations`, `/frozen-requirements`, `/simulations`, `/versions`...). Se crea y consulta por planta y fecha en `/plants/{id}/daily-plans/{date}`. Reemplaza las rutas `/harvest-plans` de la sección 12.

## 7. Cobertura de turnos

**Problema.** "Los turnos ... cubran el día según se configure" no define qué se configura.

**Decisión.** Los turnos de una planta nunca se traslapan. Un parámetro por planta ("cobertura completa") exige además que sumen 24 h sin huecos; por defecto está desactivado.

---

## Decisiones de la Fase 0

| # | Tema | Decisión |
|---|---|---|
| 8 | Reverse proxy | Caddy |
| 9 | Gestores de paquetes | `uv` (Python) y `npm` (Node) |
| 10 | Alcance de parámetros | `plant_id` nulo = valor global; un valor por planta lo reemplaza |
| 11 | Desbloqueo de cuentas | Manual por Admin; desbloqueo automático opcional por parámetro, desactivado por defecto |
| 12 | Contraseñas y sesión | Mínimo 10 caracteres; token de acceso 15 min; refresh 12 h; configurables |
| 13 | Protección de ramas | `main` y `qa` protegidas en GitHub (la configura el responsable o se instala `gh`) |
| 14 | Python local | No requerido en la Fase 0: todo corre en Docker |
