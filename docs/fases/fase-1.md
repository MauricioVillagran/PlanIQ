# Fase 1 — Planificación de cosecha (plan de tareas)

Estado: **aprobada el 27-10-2026** con las propuestas de las 10 decisiones (registradas en [ADR 0005](../adr/0005-planificacion-de-cosecha.md)).

Objetivo (sección 14): mantenedores de centros, jaulas y jaulas de acopio; plan de cosecha diario con cálculos, validaciones, orden de faena, copia del día anterior, vista semanal, estados Borrador → Publicado → Cerrado con tablas temporales, comparador de versiones y notificaciones internas.

Criterios de aceptación:
1. Planificación arma el plan de un día con varias jaulas en ambos turnos, desde el celular y desde el escritorio.
2. Los totales de peces, biomasa y WFE coinciden con un cálculo manual de control.
3. Las validaciones de capacidad de acopio y de peso plausible bloquean; la jaula repetida advierte.
4. Al publicar, los demás roles lo ven y reciben aviso.
5. Una modificación posterior exige motivo, crea versión y el comparador muestra exactamente qué cambió.
6. Dos usuarios editando a la vez reciben conflicto en vez de pisarse.
7. Un plan cerrado no se puede editar.
8. Las pruebas de dominio cubren biomasa, WFE y fecha productiva con turno nocturno.

---

## Decisiones abiertas

Cada una trae mi propuesta. Las marcadas ⚠️ cambian el diseño; el resto son detalles con un valor por defecto razonable.

### ⚠️ D1. Cómo se calcula el WFE sin productos

**Contradicción en la especificación.** La sección 4 define el WFE convirtiendo los kilos de cada **producto** planificado a pescado entero, con un factor por producto y planta. Pero los productos y el plan de producción llegan en la Fase 3, y el criterio 2 de la Fase 1 exige que el WFE de la cosecha ya cuadre.

**Propuesta:** en la Fase 1, el WFE proyectado de la cosecha es `biomasa × factor` con un parámetro por planta `harvest.wfe_factor` (sin valor inventado: lo carga Administración). Si no está definido, el plan muestra la biomasa y la advertencia "WFE sin factor configurado", y el total de WFE aparece vacío. En la Fase 3 se suma el WFE por producto con sus propios factores, como dice la especificación.

**Alternativas:** (a) WFE = biomasa (factor 1) hasta la Fase 3; (b) no mostrar WFE hasta la Fase 3, aunque así el criterio 2 no se cumpliría en esta fase.

### ⚠️ D2. Modificar un plan publicado: cambios en lote o línea por línea

La sección 6 pide que cada modificación de un plan publicado genere una versión con motivo y aviso. Si cada línea guardada fuera una versión, cambiar tres jaulas produciría tres versiones y tres avisos.

**Propuesta:** en Borrador se edita línea por línea, sin versiones ni avisos. En Publicado, los cambios se acumulan en pantalla y se envían juntos con **un motivo**, lo que produce **una versión y un aviso**. Los demás ven el plan vigente hasta que se guarda el lote. La primera publicación es la versión 1.

### ⚠️ D3. Capacidad de la jaula de acopio

La especificación dice "capacidad en peces" pero no en qué ventana de tiempo se mide.

**Propuesta:** la suma de peces asignados a una jaula de acopio **por turno** no puede superar su capacidad. El turno es la ventana en que los peces esperan proceso.

**Alternativas:** por día completo, o por línea (cada línea sola contra la capacidad).

### D4. ¿La jaula de acopio es obligatoria en cada línea?

**Propuesta:** sí. La sección 5.2 la lista como dato de cada línea y la validación de capacidad depende de ella. Si hay cosechas que van directo a proceso sin acopio, sería opcional (avísame).

### D5. Rango de peso promedio plausible sin configurar

**Propuesta:** parámetros por planta `harvest.avg_weight_kg.min` y `harvest.avg_weight_kg.max` (los carga Administración; no invento valores). Si no están definidos, esa validación no se aplica y el plan muestra la advertencia "Rango de peso plausible no configurado". Si están definidos, un peso fuera de rango **bloquea** el guardado.

### D6. Centros y jaulas: ¿globales o por planta? ¿Quién los mantiene?

**Propuesta:**
- **Centros y jaulas son globales**: un centro puede despachar a varias plantas. Las jaulas de acopio son por planta.
- Código de centro único en el sistema y código de jaula único dentro de su centro.
- Permiso nuevo `farms.edit` (centros, jaulas y acopios) para Planificación y Admin. Así Planificación da de alta una jaula nueva sin esperar a Administración. Hoy solo Admin tiene `masters.edit`.

### D7. Vínculo con Innova (preparar la Fase 2)

**Propuesta:** en la Fase 1 solo se garantizan códigos estables y únicos de centro y jaula. La equivalencia con los códigos de Innova irá en la tabla de mapeo genérica `integration.code_mappings` de la Fase 2, editable sin tocar código. No se agregan columnas "código Innova" a los maestros.

### D8. Cierre del plan

**Propuesta:** manual, con el permiso `plan.close`. Solo se habilita cuando terminó la fecha productiva, es decir, después del fin del último turno. Un plan cerrado es inmutable y no se reabre. El cierre automático queda para más adelante si se necesita.

### D9. Quién recibe los avisos

**Propuesta:** al publicar o modificar, avisa a todos los usuarios activos con `plan.view` y acceso a esa planta, excepto quien hizo el cambio. El aviso llega a la campana, con contador y "marcar como leído". Se guarda como evento (`plan.change_events`) para poder agregar correo después sin rediseñar.

### D10. Detalles con valor por defecto

| Tema | Propuesta |
|---|---|
| Crear el plan | Vacío o copiando el día anterior (todas sus líneas, como Borrador). Si la planta exige cobertura de 24 h y sus turnos tienen huecos, no se puede crear (ADR 0001, decisión 7). |
| Vista semanal | Los 7 días desde la fecha del contexto: estado, versión y totales por día. Solo lectura. |
| Unidades | Peso promedio en kg con 3 decimales; biomasa en kg en la grilla y en toneladas en los totales destacados. |
| Jaula repetida en el día | Advertencia visible en la línea y en el resumen; no bloquea (sección 5.2). |
| Orden de faena | Un número por línea en el día. Se reordena arrastrando en escritorio o con botones subir/bajar en celular. Al reordenar en Publicado también se pide motivo (es una modificación). |
| Tablas temporales | `plan.daily_plans` y `plan.harvest_entries`, con historial en el esquema `plan_history` y retención configurable (ADR 0001, decisión 4). |
| Comparador | Entre dos versiones cualesquiera: líneas agregadas, eliminadas y modificadas, campo a campo, con los nombres de centro, jaula y turno. |

---

## Plan de tareas

Cada bloque es una rama `feature/f1-<tema>` desde `develop`, cerrada con PR y el CI en verde.

### F1.1 · Maestros de cultivo — `feature/f1-farms` (hecho)
- Entregado: `master.farm_centers`, `master.cages`, `master.holding_cages` (migración `0007`, con el permiso `farms.edit` para Planificación y Admin); API `/farm-centers`, `/cages?farm_center_id=`, `/holding-cages?plant_id=`; pantallas en Configuración › Cultivo; seed con 2 centros, 7 jaulas y 3 acopios ficticios para la Planta Demo.

Plan original:
- Tablas `master.farm_centers` (código, nombre, zona o barrio), `master.cages` (centro, código) y `master.holding_cages` (planta, código, capacidad en peces), con migración.
- Permiso `farms.edit` (D6), con migración.
- API con el patrón de mantenedor. Pantallas en **Configuración › Cultivo**: centros, jaulas (filtradas por centro) y acopios (de la planta del contexto).

### F1.2 · Dominio del plan — `feature/f1-domain`
- Funciones puras en `app/domain/harvest.py`: biomasa por línea, WFE con factor (D1), totales por día, turno y centro; validaciones de capacidad (D3), peso plausible (D5) y jaula repetida; diferencias entre dos versiones.
- Pruebas con casos de control calculados a mano, y fecha productiva con turno nocturno (reutiliza `app/domain/shifts.py`).

### F1.3 · Modelo del plan y tablas temporales — `feature/f1-plan-model`
- `plan.daily_plans` (planta, fecha productiva única por planta, estado, versión vigente, publicación y cierre), `plan.harvest_entries` (centro, jaula, acopio, peces, peso promedio, turno, orden, observaciones) y `plan.daily_plan_versions` (número, usuario, motivo, fecha).
- Versionado de sistema con SQL explícito en la migración (`SYSTEM_VERSIONING`, columnas de período ocultas para el ORM), `rowversion` y auditoría.
- Prueba de que el historial temporal reconstruye el plan "tal como estaba" en una versión.

### F1.4 · API del plan en Borrador — `feature/f1-plan-api`
- `/plants/{id}/daily-plans/{fecha}`: consultar y crear (vacío o `copy_from`); `/plants/{id}/daily-plans?from=&to=`: vista semanal.
- `/daily-plans/{id}/harvest-entries`: alta, edición y baja de líneas con validaciones. La respuesta trae las advertencias aparte de los errores.
- `PUT .../harvest-entries/order` (orden de faena) y `GET /daily-plans/{id}/summary` (totales y advertencias).
- Permisos `plan.view` y `plan.edit`, y acceso por planta.

### F1.5 · Publicación, versiones y cierre — `feature/f1-plan-flow`
- `POST /daily-plans/{id}/publish` (versión 1; bloquea si hay errores).
- `POST /daily-plans/{id}/changes`: lote de cambios con motivo sobre un plan publicado (D2), que produce una versión nueva.
- `POST /daily-plans/{id}/close` (D8).
- `GET /daily-plans/{id}/versions` y `/versions/compare?a=&b=` sobre las tablas temporales.
- Concurrencia: `rowversion` del plan y de cada línea (409 con los datos vigentes).

### F1.6 · Notificaciones internas — `feature/f1-notifications`
- `plan.change_events` y `plan.notifications`; destinatarios según D9.
- `GET /notifications`, `POST /notifications/{id}/read` y `/read-all`.
- La campana muestra el contador con polling (intervalo por parámetro) y la lista con enlace al plan.

### F1.7 · Pantalla del plan — `feature/f1-plan-web`
- **Planificación › Plan de cosecha** de la fecha y planta del contexto:
  - escritorio: grilla editable con totales fijos arriba;
  - celular: tarjetas agrupadas por centro;
  - advertencias en línea, orden de faena (arrastrar o subir/bajar), crear vacío o copiar el día anterior.
- Publicar; modificar un plan publicado con motivo (D2); cerrar.
- Vista semanal; historial y comparador de versiones.
- Inicio según el rol: Planificación ve el plan de hoy y mañana con sus alertas.
- Para quien no edita (Producción, Calidad), el plan publicado en solo lectura.

### F1.8 · Pruebas y cierre — `feature/f1-cierre`
- Playwright con los 8 criterios en 360 px y escritorio. Incluye un cálculo de control a mano de peces, biomasa y WFE, y dos usuarios editando a la vez.
- Seed de datos ficticios: centros, jaulas, acopios y un plan de ejemplo.
- Nota de entrega con evidencia por criterio.

---

## Fuera de esta fase (para no adelantar)
- Columna real al lado de la planificada y cumplimiento: Fase 2 (Innova).
- Carga de la cosecha desde Excel: cuando exista su tarjeta (Fase 4 en adelante).
- Mezcla de calidad por jaula y asignación de programas de grader: Fase 4.
- Correo para los avisos: fuera de esta versión (sección 6); el diseño de eventos lo deja preparado.
