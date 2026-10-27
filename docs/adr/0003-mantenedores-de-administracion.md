# ADR 0003 — Mantenedores de administración (F0.7)

- **Estado:** aceptada
- **Fecha:** 27-10-2026
- **Contexto:** la sección 5.1 define los mantenedores de usuarios, roles, plantas, turnos y parámetros. Este ADR registra cómo se resolvió lo que no detalla.

## 1. Turnos en `/shifts`, no en `/plants/{id}/shifts`

La sección 12 propone `/plants/{id}/shifts`. Se usa `/shifts` con filtro `plant_id` (y `plant_id` en el alta) para que todos los mantenedores tengan el mismo contrato y el componente genérico del frontend no necesite variantes. El acceso por planta se valida igual.

## 2. Turnos: reglas

- Intervalos semiabiertos [inicio, término); si el término es menor o igual que el inicio, el turno cruza la medianoche (se calcula al guardar).
- Inicio igual a término se rechaza (no hay turnos de 24 h de un solo bloque); horas en minutos, sin segundos.
- Los turnos **activos** de una planta no se traslapan; se valida al crear, editar y reactivar. Nombre único por planta.
- **La cobertura de 24 h no se exige al editar**: los turnos se configuran de a uno y exigirla bloquearía el alta del primero. `GET /shifts/coverage?plant_id=` informa los huecos y si el parámetro `shifts.full_coverage` la exige; la Fase 1 la valida al crear el plan.
- Fecha productiva: `app.domain.shifts.productive_date` imputa al día de inicio del turno; un instante en un hueco entre turnos usa la fecha calendario local.

## 3. Usuarios

- La contraseña inicial la genera el sistema (12 caracteres, sin caracteres ambiguos) y se muestra **una sola vez** en la respuesta del alta o del restablecimiento; el usuario debe cambiarla al ingresar. El administrador no define contraseñas.
- Restablecer contraseña también desbloquea la cuenta y cierra las sesiones abiertas.
- El nombre de usuario no cambia después del alta; usuario y correo se guardan en minúsculas. El correo se valida con un patrón simple (no se verifica que exista).
- Al menos un rol obligatorio; roles y plantas deben existir y estar activos.
- Desactivar un usuario cierra sus sesiones. Nadie puede desactivarse a sí mismo.
- **Siempre debe quedar al menos un usuario activo con `users.admin`**: se valida al quitar roles, desactivar usuarios, editar la matriz de un rol o desactivar un rol.

## 4. Roles

- El código no cambia después del alta. Los cuatro roles base no se desactivan, pero su matriz sí se edita.
- `permissions` en el `PATCH` reemplaza la lista completa del rol. El catálogo está en `GET /permissions`.
- Un cambio en la matriz rige desde la siguiente solicitud de cada usuario.

## 5. Parámetros

- Claves libres con formato `minúsculas.con.puntos` (no hay catálogo fijo de claves todavía; cada fase documenta las que usa).
- Tipo `int`, `decimal`, `bool` o `text`, fijo por clave. Los decimales aceptan coma y se guardan con punto.
- Alcance global (`plant_id` nulo) o por planta; el de la planta reemplaza al global.
- Vigencia [desde, hasta) opcional; no puede haber dos valores activos traslapados para la misma clave y alcance. `get_parameter(session, key, plant_id, on)` resuelve el valor vigente.
- Solo quien tiene `plants.all` edita parámetros globales.
- Se carga un único valor inicial: `shifts.full_coverage = false` (ADR 0001, decisión 7). Ningún otro valor de negocio se inventa.

## 6. La API de plantas se adelantó a F0.6

Se construyó como implementación de referencia del patrón de mantenedor.
