# ADR 0002 — Autenticación y permisos (F0.4)

- **Estado:** aceptada
- **Fecha:** 27-10-2026
- **Contexto:** la especificación fija usuarios propios, Argon2, JWT corto con refresh en cookie httpOnly, bloqueo por intentos, cambio obligatorio de contraseña y permisos granulares por rol y planta. Este ADR registra cómo se resolvió lo que la especificación no detalla.

## 1. Catálogo de permisos y matriz inicial

Permisos de partida (los crea la migración `0004`; cada fase agrega los suyos con migraciones nuevas):

| Código | Para qué |
|---|---|
| `users.admin` | Usuarios, roles y matriz de permisos |
| `plants.all` | Acceso a todas las plantas sin asignación |
| `masters.view` / `masters.edit` | Plantas, turnos y maestros |
| `parameters.edit` | Parámetros |
| `audit.view` | Auditoría |
| `plan.view` / `plan.edit` / `plan.publish` / `plan.close` | Plan diario |
| `production.record` | Registro manual de producción |
| `rules.view` / `rules.edit` | Matriz de calibrado, degradación y calidades |

Matriz inicial (sección 3 de la especificación), editable luego por Admin:

| Rol | Permisos |
|---|---|
| Planificación (`planning`) | masters.view, plan.view, plan.edit, plan.publish, plan.close, rules.view |
| Producción / Frigorífico (`production`) | masters.view, plan.view, production.record |
| Calidad (`quality`) | masters.view, plan.view, rules.view, rules.edit |
| Control de Gestión / Admin (`admin`) | todos |

Los cuatro roles base son `is_system`: no se desactivan, pero su matriz sí se edita.

## 2. Acceso por planta

Un usuario ve las plantas asignadas en `core.user_plants` (solo las activas). El permiso `plants.all` da acceso a todas, en vez de un `if role == admin`. Toda consulta operacional pasa por `ensure_plant_access`.

## 3. La tabla `master.plants` se crea en F0.4

El acceso por planta necesita la FK. La tabla se crea con las columnas de la especificación; el mantenedor (API y pantalla) llega en F0.7.

## 4. Columnas de auditoría sin FK

`created_by` y `updated_by` guardan el id del usuario sin FK, para no acoplar cada tabla a `core.users`. Los usuarios nunca se borran, solo se desactivan.

## 5. Sesión

- Token de acceso JWT HS256 de 15 min, en el encabezado `Authorization: Bearer`.
- Refresh token aleatorio de 12 h, en cookie `planiq_refresh` (`HttpOnly`, `SameSite=Strict`, `Path=/api/v1/auth`, `Secure` fuera de desarrollo). En la base se guarda solo su hash SHA-256.
- Cada refresco **rota** el token. Reutilizar uno ya rotado revoca toda su familia (señal de robo).
- Cambiar la contraseña cierra todas las demás sesiones.
- En cada solicitud se recarga el usuario: desactivarlo, bloquearlo o quitarle un rol tiene efecto inmediato, sin esperar a que venza el token.

## 6. Ingreso y bloqueo

- Usuario inexistente, inactivo o contraseña errónea dan el mismo mensaje ("Usuario o contraseña incorrectos."); con usuario inexistente se verifica igual un hash para no revelar por tiempo de respuesta qué usuarios existen.
- Al quinto intento fallido la cuenta se bloquea y lo informa. Desbloqueo manual por Admin (F0.7); el desbloqueo automático se activa con `AUTH_AUTO_UNLOCK_MINUTES`.
- Límite de intentos por IP (`AUTH_LOGIN_RATE_LIMIT`, 10/min) en memoria. Vale para una réplica de la API; si se escala horizontalmente, mover el conteo a SQL Server.

## 7. Política de contraseñas

Solo lo que la especificación permite afirmar: largo mínimo configurable (10), distinta del nombre de usuario y de la contraseña actual. Reglas adicionales (mayúsculas, símbolos, vencimiento) quedan pendientes de definición.

## 8. Usuario que debe cambiar su contraseña

Puede usar solo `/auth/me`, `/auth/change-password` y `/auth/logout`. Cualquier otro endpoint responde 403 `password_change_required`.

## 9. Administrador inicial

Lo crea `python -m app.bootstrap`, que corre en el servicio `migrate` después de las migraciones, solo si la base no tiene usuarios. Toma `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_EMAIL` e `INITIAL_ADMIN_PASSWORD` del entorno y queda con cambio de contraseña obligatorio.
