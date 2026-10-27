# ADR 0005 — Planificación de cosecha (Fase 1)

- **Estado:** aceptada
- **Fecha:** 27-10-2026
- **Contexto:** decisiones abiertas de la Fase 1, aprobadas con las propuestas de [fase-1.md](../fases/fase-1.md). Donde una decisión modifica la especificación, prevalece este ADR.

## 1. WFE de la cosecha sin productos

La sección 4 define el WFE a partir de los kilos de cada producto, pero los productos llegan en la Fase 3 y el criterio de aceptación de la Fase 1 ya exige el WFE. En la Fase 1: **WFE proyectado = biomasa × `harvest.wfe_factor`** (parámetro por planta, sin valor por defecto). Si falta, el plan lo advierte y el WFE queda vacío. En la Fase 3 se agrega el WFE por producto con sus propios factores.

## 2. Modificación de un plan publicado

En Borrador se edita línea por línea, sin versiones. En Publicado, los cambios se envían juntos con **un motivo** y producen **una versión y un aviso**. La primera publicación es la versión 1.

## 3. Capacidad de la jaula de acopio

La suma de peces asignados a una jaula de acopio **por turno** no puede superar su capacidad.

## 4. Jaula de acopio obligatoria

Toda línea del plan de cosecha tiene jaula de acopio.

## 5. Rango de peso promedio plausible

Parámetros por planta `harvest.avg_weight_kg.min` y `harvest.avg_weight_kg.max`, sin valores inventados. Sin configurar: se advierte y no se valida. Configurados: un peso fuera de rango bloquea.

## 6. Centros, jaulas y jaulas de acopio

- Centros y jaulas son **globales** (un centro puede despachar a varias plantas); las jaulas de acopio son **por planta**.
- Código de centro único; código de jaula único dentro de su centro; código de acopio único dentro de su planta.
- Permiso nuevo **`farms.edit`** para Planificación y Admin.
- Igual que los turnos (ADR 0003), los recursos van planos: `/cages?farm_center_id=` y `/holding-cages?plant_id=` en vez de `/farm-centers/{id}/cages` y `/plants/{id}/holding-cages`.

## 7. Vínculo con Innova

Solo códigos estables en la Fase 1. La equivalencia con los códigos de Innova irá en `integration.code_mappings` (Fase 2), sin columnas propias en los maestros.

## 8. Cierre

Manual con `plan.close`, habilitado cuando terminó la fecha productiva. Un plan cerrado es inmutable y no se reabre.

## 9. Avisos

Al publicar o modificar: todos los usuarios activos con `plan.view` y acceso a la planta, excepto el autor. Se guardan como eventos (`plan.change_events`) para poder agregar correo después.

## 10. Detalles

Copia del día anterior como Borrador; no se crea el plan si la planta exige cobertura de 24 h y los turnos tienen huecos. Vista semanal de 7 días. Peso promedio en kg con 3 decimales y biomasa en kg (toneladas en los totales destacados). Jaula repetida en el día: advertencia. Reordenar en Publicado también pide motivo. Tablas temporales en `plan.daily_plans` y `plan.harvest_entries`, con historial en el esquema `plan_history`.
