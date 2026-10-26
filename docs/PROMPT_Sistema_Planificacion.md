# PROMPT — Sistema Web de Planificación Productiva (nombre provisional: PlanIQ)

> Usar este documento como instrucción inicial para Claude Code y como base del `CLAUDE.md` del proyecto. La interfaz y la documentación van en español; el código, nombres de tablas, variables y endpoints, en inglés.

---

## 0. Entorno de trabajo

El proyecto se desarrolla en Windows, en la ruta **`C:\PlanIQ`**, que es la raíz del repositorio (monorepo con `/api`, `/web`, `/worker`, `/infra`, `/docs`).

**Repositorio:** todo lo que se cree (código, migraciones, configuración, documentación, `CLAUDE.md` y este prompt en `/docs`) se versiona y se sube a **https://github.com/MauricioVillagran/PlanIQ.git**. `C:\PlanIQ` es el clon local de ese repositorio (`origin`). Ramas: `main` (producción), `qa` y `develop`; el trabajo diario va en ramas `feature/<fase>-<tema>` creadas desde `develop` y se integra por pull request. Commits pequeños y descriptivos en español, uno por cambio lógico; nunca subir secretos (`.env` en `.gitignore`, solo `.env.example` versionado) ni datos reales.

Los archivos reales de grader pieza a pieza están en **`C:\PlanIQ\cargaExcel`**. Con ellos se conoce el peso de entrada y de salida de cada pieza, que es la base del histórico de distribución de pesos, de la mezcla de calidad por centro y del cálculo de rendimiento entre entrada y salida.

Reglas sobre esa carpeta:

- Es la **fuente para conocer la estructura** del archivo pieza a pieza. Antes de configurar la tarjeta de carga, Claude Code debe inspeccionar los archivos (hojas, columnas, tipos, unidades, cantidad de filas y tamaño) y presentar un informe de la estructura encontrada, confirmando conmigo qué significa cada columna, en particular cuáles son el peso de entrada y el de salida y en qué unidad vienen. No asumir el significado de una columna por su nombre.
- Esa estructura se usa para **configurar el perfil de carga desde la aplicación**, no para escribir un lector específico en el código.
- Son **datos reales de producción**: la carpeta `cargaExcel/` va en `.gitignore`, nunca se sube al repositorio ni se usa en seeds o tests. Para tests se generan archivos ficticios con la misma estructura y valores inventados.
- Con Docker Desktop sobre WSL2, montar `C:\PlanIQ\cargaExcel` como volumen de solo lectura en el worker solo en desarrollo, para pruebas de carga reales; en producción los archivos llegan exclusivamente por la tarjeta de carga.

---

## 1. Contexto y objetivo

Hoy la planificación diaria de planta circula por correo: cosecha del día, plan por turno, prioridades comerciales, formatos de etiqueta, reglas de calibrado y degradación, y requerimientos de congelado. Cada área arma su propia versión y no existe un registro único de qué se planificó, qué cambió y qué se cumplió.

El objetivo es construir un **sistema web independiente**, con su propia base de datos, donde Planificación, Producción, Frigorífico, Calidad y Control de Gestión trabajen sobre un único plan diario versionado, vean el avance real de producción casi en línea y midan cumplimiento contra el plan. El sistema debe funcionar igual de bien en escritorio (Planificación) que en el celular de un supervisor en planta, sin ser una app nativa: es una web responsive, mobile-first.

No se usa Power BI. Todos los dashboards viven dentro de la aplicación.

El sistema es independiente de ProcessIQ, pero se construye con el mismo stack y expone una API versionada para integrarse con él en una etapa posterior.

---

## 2. Decisiones de arquitectura (cerradas)

| Tema | Decisión |
|---|---|
| Tipo de aplicación | Web responsive mobile-first. Sin app nativa. PWA instalable opcional (manifest + íconos), sin modo offline en esta versión. |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (estilo tipado `Mapped[]`), Pydantic v2, Alembic para migraciones. |
| Frontend | Next.js 15 (App Router), React 19, TypeScript estricto, Tailwind CSS 4, TanStack Query, React Hook Form + Zod, TanStack Table, Apache ECharts para gráficos. |
| Base de datos | SQL Server nativo (2022), nueva base dedicada (`planiq`), conexión vía `pyodbc` + ODBC Driver 18. Las réplicas de Innova se leen desde una conexión separada, solo lectura. Aprovechar funciones nativas del motor: tablas temporales para historial, `rowversion` para concurrencia, vistas indexadas para dashboards. |
| Autenticación | Usuarios propios del sistema. Contraseñas con Argon2, JWT de acceso corto + refresh token en cookie httpOnly, bloqueo por intentos fallidos, cambio de contraseña obligatorio en primer ingreso. |
| Organización | Una empresa, multi-planta. Ninguna planta viene precargada ni escrita en el código: todas se crean desde el mantenedor de plantas. La primera en operar será **Planta Victoria Sur**, creada por el administrador como cualquier otra. Toda tabla operacional lleva `plant_id`. |
| Asignación comercial | Propuesta por simulación, ajustada por el usuario: la simulación de grader (sección 5.11) propone el reparto por calibre y prioridad de cliente; el planificador lo corrige y el sistema valida cobertura, disponibilidad y reglas. |
| Graders | El sistema simula y recomienda; no envía programas ni controla la grader Marel. Compara la simulación contra lo que la grader realmente clasificó (vía Innova). |
| Flujo del plan | Estados Borrador → Publicado → Cerrado, con versionado completo de cada cambio. |
| Actualización en planta | Polling cada 1 a 5 minutos (configurable por pantalla) vía `refetchInterval` de TanStack Query. Sin WebSockets en esta versión. |
| Fuentes de datos | Ingreso manual; cargas Excel configurables (sección 7), entre ellas la carga pieza a pieza de grader que alimenta el histórico de los centros; y réplicas de Innova (producción real, rendimientos, calibres, calidad). |
| Despliegue | Docker Compose (api, web, worker de sincronización, reverse proxy). Agnóstico a on-premise o nube; la decisión se toma después. |
| Integración futura | API REST `/api/v1`, documentada con OpenAPI, autenticable con API keys de servicio para ProcessIQ. |

**Paleta (ThemeDaaS)**: teal `#0096A0`, azul oscuro `#324664`, coral `#FA6E5A`, gris claro `#D2D2CD`, teal claro `#80CAD0`, coral claro `#FCB7AC`, azul medio `#6F8CB7`, fondo `#EDEDEB`, tarjetas `#FFFFFF`, texto y títulos `#324664`. Coral se reserva para alertas y desvíos; teal para cumplimiento y acciones primarias.

---

## 3. Roles y permisos

**Planificación**: crea y edita la cosecha del día, el plan de producción por turno, la distribución comercial y el plan de congelados. Publica y cierra el plan. Puede importar Excel.

**Producción / Frigorífico**: consulta el plan publicado, ve el avance real y la cobertura, registra observaciones y cumplimiento manual cuando no exista dato en réplica (por ejemplo, cajas paletizadas de un pedido). No edita el plan.

**Calidad**: administra la matriz de calibrado, las reglas de degradación y las calidades. Consulta el plan.

**Control de Gestión / Admin**: administra usuarios, plantas, maestros, parámetros, plantillas de importación y conexión a réplicas. Accede a todos los dashboards y a la auditoría.

Los permisos se modelan como permisos granulares (`plan.edit`, `plan.publish`, `rules.edit`, `masters.edit`, `users.admin`, etc.) asignados a roles, no como `if role == ...` disperso en el código. Un usuario puede tener acceso a una o varias plantas.

---

## 4. Conceptos de dominio que el sistema debe respetar

**Fecha productiva y turnos.** El turno noche cruza la medianoche. Cada planta define sus turnos (nombre, hora inicio, hora fin) y la regla es que la producción se imputa a la fecha productiva del inicio del turno, no a la fecha calendario del registro. Toda fecha se maneja en `America/Santiago` y se almacena en UTC.

**Biomasa y WFE.** Biomasa estimada = peces × peso promedio. El WFE (Whole Fish Equivalent) proyectado se calcula convirtiendo los kilos de cada producto planificado a pescado entero con un factor de rendimiento configurable por producto y planta. Los factores son parámetros, no constantes en código.

**Calibres.** Los rangos de calibre son configurables por tipo de producto (no son iguales para entero, HON y filete). El sistema valida que los rangos de un mismo tipo no se traslapen ni dejen huecos. Nota: en la especificación original aparecen rangos inconsistentes entre la tabla de calibres y la matriz (por ejemplo `4,5–5,45` contra el calibre `4,1–5,45`, o `0–2,7` contra `0–1,8 / 1,8–2,8`); el validador debe detectar este tipo de error al guardar.

**Plan diario.** Es la unidad central. Una planta tiene un plan por fecha productiva, que contiene cosecha, plan por turno, asignación comercial y requerimientos de congelado. Se versiona completo.

---

## 5. Módulos funcionales

### 5.1 Mantenedores (sistema nuevo, se parte desde cero)

El sistema arranca limpio: no hereda usuarios, plantas ni maestros de ningún otro sistema. Todo se crea desde sus propios mantenedores, y el primer arranque solo trae un usuario administrador inicial (credenciales por variable de entorno, cambio obligatorio al primer ingreso) y la matriz de permisos base.

Todos los mantenedores comparten el mismo patrón, construido una vez como componente reutilizable: listado con búsqueda, filtros y paginación del lado del servidor; crear y editar en un panel lateral (en celular, pantalla completa); activar y desactivar en vez de borrar cuando el registro tiene historia; exportar a Excel; pestaña de historial con quién cambió qué y cuándo; códigos únicos validados. En celular el listado se muestra como tarjetas.

**Administración (Fase 0)**

- *Usuarios*: nombre, correo, nombre de usuario, rol o roles, plantas a las que tiene acceso, estado, último ingreso. Acciones: crear, editar, desactivar, restablecer contraseña (genera clave temporal), desbloquear.
- *Roles y permisos*: los cuatro roles base (Planificación, Producción/Frigorífico, Calidad, Control de Gestión/Admin) con su matriz de permisos editable por Admin. Se pueden crear roles nuevos.
- *Plantas*: código, nombre, tipo (propia o maquila), ubicación, zona horaria (por defecto `America/Santiago`), activa.
- *Turnos*: planta, nombre, hora de inicio, hora de término, si cruza medianoche (calculado), orden. El sistema valida que los turnos de una planta no se traslapen y cubran el día según se configure.
- *Parámetros*: valores por planta con tipo, unidad y vigencia (factores WFE, umbrales de cobertura, intervalo de refresco, rango de peso promedio plausible, etc.).

**Planificación de cosecha (Fase 1)**

- *Centros de cultivo*: código, nombre, zona o barrio, activo.
- *Jaulas*: centro, código, activa.
- *Jaulas de acopio*: planta, código, capacidad en peces, activa.

**Producción y comercial (fases posteriores)**

Procesos (eviscerado, filete fresco, HON, etc.), productos (familia: entero, HON, filete; condición: fresco o congelado; kg por caja, piezas por caja o peso promedio por pieza, factor WFE), clientes (país, mercado, tipo de producto), mercados, calidades (Premium, Standard, Heridas, Madurez, configurables), calibres por tipo de producto, líneas, impresoras, formatos de etiqueta, y graders con sus puertas y programas de clasificación (sección 5.11). Se construyen con el mismo componente cuando su fase lo requiera.

### 5.2 Planificación de cosecha (núcleo del sistema)

Es el primer módulo de valor y el centro del sistema; todo lo demás se apoya en él.

Para cada planta y fecha productiva existe un plan de cosecha. Cada línea registra centro, jaula, jaula de acopio, cantidad de peces, peso promedio (kg), biomasa estimada (calculada), turno asignado, orden de faena y observaciones.

El sistema muestra en vivo los totales del día (peces, biomasa, WFE proyectado) y su distribución por turno y por centro. Valida al guardar: capacidad de la jaula de acopio, peso promedio dentro del rango plausible definido en parámetros, y advierte (sin bloquear) si una misma jaula aparece dos veces en el día.

Funciones de trabajo diario: crear el plan vacío o copiando el del día anterior, reordenar la orden de faena (arrastrar en escritorio, botones subir/bajar en celular), vista semanal de solo lectura con los próximos días planificados, y el flujo Borrador → Publicado → Cerrado con versionado descrito en la sección 6. En celular se muestra como tarjetas agrupadas por centro; en escritorio como grilla editable.

**Plan versus real (Fase 2):** cuando se conecte Innova, cada línea de cosecha se compara contra lo realmente recibido y procesado (peces, peso promedio real, biomasa real, turno en que efectivamente se faenó). La pantalla del plan muestra la columna real al lado de la planificada con el desvío en cantidad y porcentaje, y el cumplimiento del día por turno y por centro. El modelo de datos de la Fase 1 debe dejar preparado el vínculo (código de centro y jaula mapeable a Innova) para que esta fase no obligue a rehacer tablas.

### 5.3 Plan de producción por turno
Para cada turno (día y noche), cantidades planificadas por proceso: eviscerado, filete fresco, filete congelado, HON fresco, HON congelado, aletas y scraps. La lista de procesos es configurable. El sistema compara el plan contra la biomasa disponible de la cosecha y alerta si lo planificado excede lo cosechado (considerando factores de rendimiento).

### 5.4 Distribución comercial (propuesta por simulación, ajustada por el usuario)
Por familia de producto (entero fresco, filete fresco, congelado), el planificador define la prioridad de clientes y sus requerimientos. La simulación de grader (sección 5.11) genera una propuesta de reparto por calibre y prioridad; el planificador puede aceptarla, corregir cantidades o mover asignaciones entre clientes, y cada ajuste manual queda marcado como tal frente a lo propuesto. El sistema muestra en todo momento:

- disponible por calibre y calidad según la cosecha y las reglas de calibrado,
- asignado por cliente y saldo sin asignar,
- alertas cuando se asigna más de lo disponible, cuando un cliente prioritario queda bajo un umbral de cobertura o cuando se asigna un calibre que la matriz no destina a ese producto.

Las prioridades por defecto se guardan como plantilla por planta y se precargan en cada plan nuevo.

### 5.5 Formatos de etiqueta
Catálogo cliente + producto → código de etiqueta, formato, línea e impresora asociada. Al asignar una orden o pedido, la pantalla muestra automáticamente esta información. Si una combinación cliente-producto no tiene etiqueta definida, se marca como alerta bloqueante para publicar el plan.

### 5.6 Matriz de calibrado
Reglas editables por Calidad sin intervención de TI: tipo de producto + calidad + rango de calibre → destino (por ejemplo, Premium 2,8–4,1 → TD Fresh; Heridas en calibre bajo → IQF). Las reglas tienen prioridad, vigencia (desde/hasta) y versión; un cambio no altera planes ya cerrados.

### 5.7 Motor de degradación
Reglas parametrizables que, dados tipo de producto, calidad, calibre y condición (por ejemplo, exceso de sellado), determinan destino, cliente sugerido y formato. Ejemplos: HON 0–1,8 → IQF; HON 6-Up → IQF; filete con degradación → Superior; exceso de sellado → IQF.

Implementación: tabla de reglas con condiciones estructuradas (no código ni expresiones libres), evaluadas por prioridad con "primer match gana". Incluir un **simulador** donde el usuario ingresa calidad y calibre y ve qué regla se aplica y por qué. Toda evaluación del motor queda trazable (qué regla y qué versión decidió).

### 5.8 Planificación de congelados
Requerimientos por cliente, producto, calibre, orden de producción (OP) y cajas requeridas. Estado de cada línea: Pendiente, En proceso, Cumplido, con avance calculado desde réplicas o registro manual de Frigorífico.

### 5.9 Programación y cobertura
Por cada requerimiento: piezas requeridas (cajas × piezas por caja, o cajas × kg por caja ÷ peso promedio por pieza, según cómo esté definido el producto), piezas disponibles según cosecha y calibrado, rendimiento esperado y cobertura (disponible ÷ requerido). Ejemplo: Sam's Club, 500 cajas → 4.000 piezas requeridas; 4.500 disponibles → cobertura 112%. Cobertura bajo 100% se marca en coral; entre 100% y un umbral configurable, en amarillo.

### 5.10 Seguimiento y dashboards (nativos)
**Vista supervisor (celular):** avance del turno actual contra plan por proceso, cumplimiento por cliente prioritario, cobertura de congelados y alertas activas. Pocas cifras grandes, sin tablas anchas, refresco automático con indicador de "última actualización".

**Vista planificación (escritorio):** plan vs real del día y de la semana, por turno, por cliente y por producto; peces cosechados, biomasa, WFE, rendimiento; distribución fresco por mercado (China, Brasil, USA, Nacional) y congelado por cliente; degradación por calidad (Premium, Standard, Heridas, Madurez).

**Vista gestión:** tendencias de cumplimiento, desvíos recurrentes, comparación entre plantas cuando haya más de una.

Todo dashboard permite filtrar por planta, fecha y turno, y exportar a Excel.

### 5.11 Graders y simulación pieza a pieza

Objetivo: a partir de la cosecha planificada (peces y peso medio por jaula), la matriz de calibrado y las prioridades de clientes, proyectar cuántas piezas irán a cada puerta de cada grader, con qué producto y para qué cliente, detectar a tiempo qué clientes no quedarán cubiertos y, una vez procesado, comparar contra lo que la grader realmente clasificó. El sistema **no controla la grader**: el resultado es una recomendación que el operador lleva a la configuración de la Marel.

**Configuración (mantenedores, rol Calidad y Admin)**

- *Graders*: planta, código, nombre, línea, tipo de pieza que clasifica (entero, HON u otro) y factor de conversión desde peso vivo/entero cuando corresponda. Una planta puede tener varias.
- *Puertas*: cada grader se crea con 14 puertas por defecto; se pueden agregar, renombrar o desactivar sin límite fijo. Una puerta desactivada no se usa en simulaciones nuevas, pero se conserva en el historial.
- *Programas de clasificación*: cada grader tiene sus propios programas (su matriz). Un programa define, para cada puerta, la o las calidades que acepta, el rango de peso, el producto de destino y el cliente o la lista de clientes que puede abastecer. Además define dos puertas obligatorias: **fuera de rango** (piezas que no calzan en ninguna regla) y **excedente** (piezas que sobran cuando los clientes de su calibre ya están cubiertos, por ejemplo stock o IQF). Los programas tienen versión y vigencia, y se pueden clonar para crear variantes.
- *Asignación de programa*: en el plan de cosecha se elige qué programa usa cada grader por turno, con la opción de sobrescribirlo para una jaula específica. La regla es: programa de la jaula si existe, si no el del turno.

Validaciones al guardar un programa: rangos con mínimo menor que máximo, puertas fuera de rango y excedente definidas, y advertencia de huecos (combinaciones de calidad y peso que caerían directo a fuera de rango). Que varias puertas compartan el mismo rango es válido, porque así se reparten clientes de un mismo calibre.

**Insumos de la simulación**

- *Peces y peso medio* de cada jaula, desde el plan de cosecha.
- *Distribución de pesos*: se usa la dispersión real de cosechas anteriores del mismo centro, construida a partir de las **cargas Excel de grader pieza a pieza** (sección 7) y, cuando esté conectado, de Innova (perfil de distribución relativo al peso medio, escalado al peso medio planificado). Si no hay historia suficiente (umbral configurable de piezas), se usa una curva normal con coeficiente de variación configurable por centro, con valor por defecto global en parámetros. La pantalla indica qué fuente se usó en cada jaula.
- *Mezcla de calidad*: se precarga el porcentaje histórico de cada calidad (Premium, Standard, Heridas, Madurez) por centro, calculado desde las mismas cargas pieza a pieza o desde Innova, y Planificación o Calidad puede ajustarlo por jaula. Los porcentajes deben sumar 100%.
- *Requerimientos y prioridades de clientes* por producto, en piezas, kilos o cajas (convertidos a piezas con los datos del maestro de productos).

**Lógica de cálculo**

1. Por jaula, se calcula el número esperado de piezas por calidad y por tramo de peso (tramos finos configurables, por ejemplo de 50 g), combinando peces, mezcla de calidad y distribución de pesos. El cálculo es determinístico (valores esperados, no aleatorio), para que la misma entrada dé siempre el mismo resultado.
2. Las jaulas se procesan en el **orden de faena** del plan. Para cada tramo de calidad y peso se buscan las puertas del programa vigente que lo aceptan.
3. Si varias puertas aceptan el tramo, las piezas van primero a la puerta del cliente de mayor prioridad hasta completar su requerimiento; el saldo pasa al siguiente cliente según prioridad, y así sucesivamente. Lo que sobra cuando todos están cubiertos va a la puerta de excedente; lo que no calza en ninguna regla va a la puerta fuera de rango.
4. Los requerimientos se van consumiendo a lo largo de la secuencia de jaulas, de modo que el resultado muestra en qué jaula y turno se completa cada cliente, y qué clientes terminan el día bajo su requerimiento.

Toda la lógica vive en un servicio puro del backend, testeable sin base de datos, con casos de prueba que incluyan empates de prioridad, clientes sin requerimiento, programas con huecos y jaulas sin historia.

**Resultados**

Por grader y puerta: piezas, kilos, producto y cliente. Por cliente: piezas proyectadas contra requerimiento, cobertura y jaula donde se completa. Por jaula: reparto entre puertas. Alertas: cliente prioritario bajo el umbral de cobertura, porcentaje alto en fuera de rango o excedente, jaulas simuladas con curva supuesta en vez de historia. La simulación se recalcula al cambiar cosecha, orden de faena, mezcla de calidad, programa o requerimientos, y cada ejecución guardada queda versionada junto al plan.

El resultado alimenta la propuesta de distribución comercial (sección 5.4); el planificador ajusta y el sistema marca la diferencia entre lo propuesto y lo decidido. También se ofrece una vista "hoja de grader" pensada para celular o impresión: por grader y turno, qué programa usar y qué va en cada puerta.

**Simulado versus real**

Lo que la grader realmente clasificó por puerta y por jaula o lote (piezas y kilos) se obtiene de la carga Excel pieza a pieza de cada cosecha y, cuando esté conectado, de Innova. El sistema muestra simulado contra real por puerta, cliente y jaula, con el error en piezas y porcentaje. Las cosechas reales alimentan los perfiles de distribución de peso y la mezcla de calidad por centro, de modo que la simulación mejora con el uso. Se registra el error histórico de la simulación por centro para saber qué tan confiable es.

---

## 6. Flujo del plan diario y versionado

**Borrador**: Planificación edita libremente. Puede crearse vacío, copiando el plan del día anterior o desde importación Excel.

**Publicado**: el plan queda visible para todas las áreas. Para publicar, el sistema exige que no existan alertas bloqueantes (etiquetas faltantes, asignación mayor a disponible, rangos de calibre inválidos). Un plan publicado puede modificarse, pero cada modificación genera una nueva versión con usuario, fecha, motivo obligatorio y diferencias campo a campo, y se notifica dentro de la app a los roles afectados.

**Cerrado**: al terminar la fecha productiva, Planificación o Admin lo cierra. Queda inmutable y se congela el cálculo de cumplimiento.

Se debe poder ver cualquier versión anterior y un comparador entre versiones. Las notificaciones son internas de la app (campana con contador); el correo queda fuera de esta versión, pero el diseño de eventos debe permitir agregarlo después.

---

## 7. Fuentes de datos e integración

**Ingreso manual**: formularios validados con Zod en el frontend y Pydantic en el backend; las reglas de negocio se validan siempre en el backend.

**Cargas Excel configurables (motor de cargas)**

El sistema no trae formatos de Excel fijos en el código. Tiene un motor que **reconoce la estructura de un archivo de ejemplo, se configura una sola vez y queda como una tarjeta de carga reutilizable**. La primera y más importante es la **carga de grader pieza a pieza**, que alimenta el histórico de distribución de pesos y mezcla de calidad por centro. Los archivos reales están en `C:\PlanIQ\cargaExcel` (sección 0) y traen el peso de entrada y de salida de cada pieza; el motor debe construirse genérico para que ese archivo, y cualquier otro futuro, se configure sin tocar código.

*Configuración, una sola vez (rol Admin / Control de Gestión):*

1. Se sube un archivo de ejemplo. El sistema detecta hojas, fila de encabezados, columnas, tipo de dato de cada columna (texto, número, fecha, fecha-hora), formato de fechas y separador decimal, y muestra una previsualización de las primeras filas.
2. Se elige el **destino** de la carga (por ejemplo, registros pieza a pieza de grader) y se mapea cada columna del archivo a un campo del destino. El sistema sugiere el mapeo por nombre de columna y tipo, y marca los campos obligatorios del destino que quedan sin asignar.
3. Se definen transformaciones simples por columna: unidad (gramos a kilos), formato de fecha, valores constantes para campos que el archivo no trae (por ejemplo, la planta o la grader), y la traducción de códigos del archivo a maestros del sistema (centro, jaula, puerta, calidad) mediante las tablas de mapeo.
4. Se definen las reglas de validación: obligatorios, rangos (peso mínimo y máximo plausibles), valores permitidos, y la **clave natural** que identifica un registro para detectar duplicados (por ejemplo, grader + fecha-hora + número de pieza).
5. Se asigna **nombre, descripción, ícono y roles autorizados** para cargar. Al guardar, se registra la **firma de estructura** del archivo (hoja, columnas y tipos) y aparece una **tarjeta** en la pantalla "Cargas" con su nombre, descripción, fecha de la última carga y el botón **"Cargar Excel"**.

Los perfiles de carga tienen versión: si el proveedor cambia el formato, se crea una nueva versión del perfil a partir de un nuevo archivo de ejemplo, sin perder el historial de cargas anteriores.

*Cada carga, siempre validada (roles autorizados en la tarjeta):*

1. El usuario pulsa "Cargar Excel" en la tarjeta y sube el archivo (`.xlsx` o `.csv`).
2. **Validación de estructura**: el archivo se compara contra la firma del perfil. Si faltan columnas, cambiaron de nombre o de tipo, la carga se rechaza mostrando exactamente qué difiere; no se intenta adivinar.
3. **Validación de contenido**, fila por fila: tipos, obligatorios, rangos, códigos sin mapeo (por ejemplo, un centro que no existe en el sistema) y duplicados, tanto dentro del archivo como contra cargas anteriores (por clave natural y por hash del archivo).
4. **Resumen previo**: filas leídas, válidas, con error y duplicadas; rango de fechas; centros, jaulas y graders incluidos; y un reporte de errores descargable en Excel con la fila y el motivo.
5. El usuario confirma. La carga se aplica en una sola transacción: entra completa o no entra. No hay cargas parciales. Si el perfil lo permite, se puede optar por cargar solo las filas válidas, pero esa decisión queda registrada.
6. Al terminar se recalculan los perfiles de distribución de peso y la mezcla de calidad de los centros afectados, y la tarjeta muestra la última carga.

Toda carga queda registrada con usuario, fecha, archivo original almacenado, versión del perfil usada, resultado y errores. Una carga se puede **anular** (por rol Admin) y el sistema revierte sus registros y recalcula el histórico afectado.

*Volumen y tamaño máximo:* el tamaño máximo por archivo es **300 MB**, configurable como parámetro del sistema. El límite se valida en tres puntos: en el navegador antes de subir (mensaje inmediato, sin gastar la subida), en el reverse proxy (`client_max_body_size 300m` o equivalente) y en la API, que rechaza con un error claro todo lo que lo exceda.

Un `.xlsx` de 300 MB está comprimido y puede equivaler a varios GB en memoria si se abre completo, así que:

- La subida se hace en **partes** (chunked upload) con reanudación, para que una caída de red en planta o en celular no obligue a partir de cero, y la API escribe a disco por streaming, nunca acumula el archivo en memoria.
- La lectura se hace en **streaming** fila a fila con `openpyxl` en modo `read_only` (o el lector CSV estándar), no cargando la hoja completa. `python-calamine` solo para archivos chicos, porque carga la hoja entera en memoria.
- La validación y la inserción corren en el worker, por bloques (por ejemplo, de 10.000 filas), con barra de progreso y tiempo estimado en la tarjeta; la pantalla no queda bloqueada y el usuario puede salir y volver.
- La inserción usa carga masiva hacia una tabla de staging (`fast_executemany` de pyodbc) y luego `INSERT ... SELECT` a la tabla final dentro de la transacción.
- El contenedor del worker debe tener memoria acotada y suficiente para procesar un archivo del máximo permitido; incluir una prueba de carga con un archivo ficticio cercano a 300 MB.
- Excel admite como máximo 1.048.576 filas por hoja. Si el origen lo supera, se acepta CSV (que con 300 MB permite bastantes más filas) o el archivo dividido en varias hojas, si el perfil lo define.
- El archivo original se guarda comprimido en un almacenamiento de archivos (volumen o almacenamiento de objetos), no dentro de SQL Server, con una política de retención configurable.

El mismo motor se usa después para cualquier otra carga (cosecha, requerimientos de congelado, maestros), cada una como su propia tarjeta configurada.

**Réplicas de Innova (solo lectura)**: un worker de sincronización consulta periódicamente producción real, rendimientos, calibres y calidad, normaliza y escribe en tablas de staging y luego en las tablas de hechos reales del sistema. Requisitos: conexión SQL Server separada con usuario de solo lectura, sincronización incremental por marca de tiempo o ID, idempotencia, log de cada ejecución (inicio, fin, filas, errores) y una pantalla de estado de la integración para Admin. El mapeo entre códigos de Innova y maestros propios (productos, clientes, calibres) se mantiene en tablas de mapeo editables, no en código. Si la réplica no responde, el sistema sigue operando con lo último sincronizado y muestra la antigüedad del dato.

**API para ProcessIQ**: endpoints de lectura de plan publicado, cumplimiento y maestros bajo `/api/v1`, autenticados por API key de servicio con alcance por planta.

---

## 8. Modelo de datos (base)

Esquemas sugeridos en SQL Server: `core` (usuarios, roles, plantas, auditoría), `master` (maestros y reglas), `plan` (plan diario y sus partes), `actual` (datos reales sincronizados), `integration` (staging, mapeos, logs).

Tablas principales:

```
core.users, core.roles, core.permissions, core.role_permissions, core.user_plants, core.audit_log
master.plants, master.shifts, master.farm_centers, master.cages, master.customers, master.markets,
master.products, master.quality_grades, master.size_ranges, master.label_formats, master.lines, master.printers,
master.grading_rules, master.downgrade_rules, master.priority_templates, master.yield_factors, master.parameters,
master.graders, master.grader_gates, master.grader_programs, master.grader_program_gates, master.grader_program_gate_customers,
master.weight_distribution_profiles, master.center_quality_mix
plan.daily_plans, plan.daily_plan_versions, plan.harvest_entries, plan.harvest_entry_quality_mix, plan.grader_program_assignments,
plan.shift_production_plans, plan.commercial_allocations, plan.frozen_requirements, plan.change_events, plan.notifications,
plan.grader_simulations, plan.grader_simulation_results
actual.production_actuals, actual.yields, actual.size_distribution, actual.quality_results, actual.frozen_progress,
actual.grader_gate_results, actual.grader_piece_records
integration.sync_runs, integration.staging_*, integration.code_mappings,
integration.import_profiles, integration.import_profile_versions, integration.import_profile_columns,
integration.import_profile_rules, integration.import_batches, integration.import_batch_errors
```

`actual.grader_piece_records` guarda cada pieza (grader, puerta, fecha-hora, peso, calidad, centro, jaula o lote, lote de carga). Por su volumen, usar **índice columnstore agrupado** de SQL Server, adecuado para millones de filas consultadas por agregación, y no aplicarle tablas temporales; su trazabilidad la da el lote de carga (`import_batch_id`).

Convenciones: PK `id` (BIGINT identity), `plant_id` en toda tabla operacional, columnas de auditoría (`created_at`, `created_by`, `updated_at`, `updated_by`), borrado lógico con `is_active`, reglas con `valid_from`/`valid_to` y `version`. Los valores decimales de peso usan `DECIMAL(10,3)`; nada de `FLOAT` para kilos o cajas. Vistas SQL para los cálculos de cumplimiento y cobertura, consumidas por la API de dashboards.

Uso de capacidades nativas de SQL Server:

- **Tablas temporales (system-versioned)** en las tablas del plan (`plan.*`) y en las reglas (`master.grading_rules`, `master.downgrade_rules`). El motor guarda automáticamente cada estado anterior y permite consultar el plan "tal como estaba" en cualquier momento con `FOR SYSTEM_TIME AS OF`. `plan.daily_plan_versions` queda solo como cabecera de versión (número, usuario, motivo, fecha de publicación) y el comparador de versiones se construye sobre las tablas de historial. Alembic debe crear estas tablas con SQL explícito (`op.execute`), porque no las genera solo.
- **`rowversion`** en las tablas editables para control de concurrencia optimista: si dos planificadores editan el mismo plan, el segundo recibe un conflicto en vez de pisar cambios.
- **Validación de rangos de calibre** en dos capas: en el servicio del backend (mensaje claro al usuario) y como respaldo en la base con un `CHECK` de `min < max` más un trigger `AFTER INSERT, UPDATE` que rechaza traslapes dentro del mismo tipo de producto. SQL Server no tiene tipos de rango, así que el trigger es la red de seguridad.
- **Vistas indexadas** solo para agregados de dashboard que se consulten con polling frecuente, una vez medido que hace falta; no anticiparlas.
- **Edición:** el diseño debe funcionar en Express para desarrollo y QA. Considerar que Express limita cada base a 10 GB y a 1 socket o 4 núcleos; antes de producción, estimar el crecimiento de `actual.*` y de las tablas de historial temporal y definir política de retención (por ejemplo, purga o archivo del historial temporal con `HISTORY_RETENTION_PERIOD`). Si el volumen lo supera, pasar a Standard.
- **Docker:** usar la imagen oficial `mcr.microsoft.com/mssql/server:2022-latest` en desarrollo, con volumen persistente y al menos 2 GB de RAM asignados al contenedor.

---

## 9. Requisitos de UX móvil

Diseño mobile-first desde 360 px. Navegación inferior en celular y lateral en escritorio. Objetivos táctiles de al menos 44 px, inputs numéricos con teclado numérico y separador decimal coma. Las grillas editables de escritorio se transforman en tarjetas o listas en celular; nunca scroll horizontal de página. Selector de planta, fecha productiva y turno siempre visible. Indicador de última actualización en toda pantalla con polling. Estados de carga con skeletons y estados vacíos con acción sugerida. Formato chileno: miles con punto, decimales con coma, fechas `dd-mm-aaaa`.

---

## 10. Requisitos no funcionales

Auditoría de toda escritura. Validación de reglas de negocio solo en el backend como fuente de verdad. Tests con pytest (servicios de cálculo, motor de reglas, importación) y Playwright para los flujos críticos (crear plan, publicar, versionar, importar). Logging estructurado. Variables de entorno para toda credencial; nada sensible en el repositorio. Rate limiting en login. Respaldos de la base documentados. CI con GitHub Actions en el repositorio `MauricioVillagran/PlanIQ`, con ramas `develop → qa → main`: en cada pull request se ejecutan lint, type-check, tests de backend y frontend y build de las imágenes Docker; `main` y `qa` quedan protegidas y solo reciben cambios por pull request con el CI en verde.

---

## 11. Fases de entrega

**Fase 0 — Fundación y administración.** Monorepo (`/api`, `/web`, `/worker`, `/infra`), Docker Compose con SQL Server 2022, base de datos nueva con Alembic, autenticación propia, layout responsive con la paleta, componente reutilizable de mantenedor, y los mantenedores de usuarios, roles y permisos, plantas, turnos y parámetros. Auditoría activa desde el primer registro. Al terminar, un administrador puede entrar, crear plantas, turnos y usuarios, y asignarles roles y plantas.

**Fase 1 — Planificación de cosecha (núcleo).** Mantenedores de centros, jaulas y jaulas de acopio; plan de cosecha diario con cálculos, validaciones, orden de faena, copia del día anterior, vista semanal, estados Borrador/Publicado/Cerrado con versionado y comparador, y notificaciones internas. Al terminar, la planificación de cosecha deja de enviarse por correo.

**Fase 2 — Integración Innova: real versus plan de cosecha.** Worker de sincronización con las réplicas de Innova (solo lectura), tablas de mapeo de códigos, pantalla de estado de la integración, columna real al lado de la planificada, desvíos y cumplimiento por turno y por centro, y la vista de supervisor en celular para la cosecha.

**Fase 3 — Plan de producción por turno.** Mantenedores de procesos y productos; plan por proceso y turno, validado contra la biomasa de la cosecha; real versus plan de producción desde Innova.

**Fase 4 — Reglas y graders.** Motor de cargas Excel configurables con pantalla de tarjetas, y la primera tarjeta: carga de grader pieza a pieza (se configura cuando se entregue el archivo real). Mantenedores de calidades y calibres; matriz de calibrado, motor de degradación con simulador, validador de rangos de calibre. Mantenedores de graders, puertas y programas; perfiles de distribución de peso y mezcla de calidad por centro (históricos desde Innova, con curva de respaldo); simulación pieza a pieza por puerta y producto, todavía sin clientes; hoja de grader; simulado versus real por puerta.

**Fase 5 — Comercial, etiquetas y congelados.** Mantenedores de clientes, mercados, líneas, impresoras y etiquetas; clientes y prioridades incorporados a los programas de grader; reparto por calibre y prioridad en la simulación como propuesta de distribución comercial ajustable; catálogo de etiquetas con alerta bloqueante; planificación de congelados, programación y cobertura.

**Fase 6 — Dashboards, importación y apertura.** Dashboards completos de planificación y gestión, alertas de desvío, tarjetas de carga adicionales que se necesiten (cosecha, congelados, maestros), API `/api/v1` con API keys para ProcessIQ, PWA instalable y documentación de usuario por rol.

Cada fase termina con: migraciones aplicadas, tests en verde, datos de ejemplo cargables (`seed`) y una nota breve de lo entregado y lo pendiente.

---

## 12. Instrucciones para Claude Code

1. Antes de escribir código, generar el `CLAUDE.md` del proyecto a partir de este documento y proponer la estructura de carpetas. Esperar confirmación.
2. Trabajar una fase a la vez. Al inicio de cada fase, listar las decisiones abiertas que encuentres y preguntar antes de asumir.
3. No inventar reglas de negocio: si un cálculo, rango o prioridad no está definido aquí, dejarlo como parámetro configurable y señalarlo.
4. Usar datos de ejemplo ficticios en los seeds; nunca datos reales de producción.
5. Mantener la lógica de cálculo (biomasa, WFE, cobertura, cumplimiento, motor de reglas) en servicios puros del backend, testeables sin base de datos.
6. Toda pantalla debe probarse en 360 px y en escritorio antes de darse por terminada.
7. Los archivos de grader pieza a pieza están en `C:\PlanIQ\cargaExcel` (sección 0). No inventar sus columnas ni escribir un lector específico: inspeccionarlos, informar la estructura y confirmar conmigo el significado de cada columna (sobre todo peso de entrada y de salida), construir el motor genérico de cargas y configurar el archivo como perfil desde la propia aplicación. Para los tests del motor, usar archivos ficticios, nunca los reales.
