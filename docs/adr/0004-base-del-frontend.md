# ADR 0004 — Base del frontend (F0.8)

- **Estado:** aceptada
- **Fecha:** 27-10-2026

## 1. Versiones

Next.js 16.4, React 19.3, Tailwind 4.3 y TanStack Query 5, fijadas a versión exacta. Dos excepciones a "estable vigente":

- **TypeScript 5.9.3** (no 6.x): `openapi-typescript`, que genera el cliente tipado, declara compatibilidad solo con TypeScript 5.
- **ESLint 9.39** (no 10.x): los plugins que trae `eslint-config-next` declaran ESLint 9 como máximo. Actualizar cuando Next declare soporte para ESLint 10.

## 2. Sesión en el navegador

- El token de acceso vive **solo en memoria** (nunca en `localStorage`), para que un script inyectado no pueda leerlo.
- El refresh token es la cookie httpOnly de la API. Al recargar la página la sesión se recupera llamando a `/auth/refresh`.
- Ante un 401 el cliente refresca una sola vez (las llamadas simultáneas comparten el refresco) y reintenta; si el refresco falla, vuelve al ingreso conservando la ruta en `?next=` (solo rutas internas).
- El navegador habla siempre con la API por el mismo origen (`/api/v1`, a través de Caddy): sin CORS y con la cookie restringida a `/api/v1/auth`.

## 3. Cliente de la API tipado desde el OpenAPI

`src/lib/api/schema.d.ts` se genera con `npm run api:types` desde la API en ejecución y se versiona. Los errores llegan como `ApiError` con `code`, `message` y `field_errors`, y los formularios muestran bajo cada campo el mensaje de la API.

## 4. Contexto global en la URL

Planta, fecha productiva y turno van en la URL (`?plant=1&date=2026-10-27&shift=2`), así un enlace compartido abre la misma vista. Sin planta en la URL se usa la última elegida en ese navegador o la primera disponible. La fecha por defecto es "hoy" en `America/Santiago`, no en la zona del navegador.

## 5. Interfaz

- Paleta ThemeDaaS como tokens de Tailwind (`bg-teal`, `text-navy`, `bg-coral`...), tipografía DM Sans y DM Mono para cifras (servidas por la propia app con `next/font`, sin CDN en ejecución).
- Celular: barra superior con marca, campana y selector de contexto debajo, y navegación inferior. Escritorio (≥1024 px): barra lateral azul y selector en la barra superior.
- Objetivos táctiles de 44 px como mínimo; sin scroll horizontal de página (verificado en 360 px).
- Rutas en inglés (`/login`, `/change-password`, `/profile`), como el resto del código; los textos visibles en español.

## 6. Datos ficticios de desarrollo

`python -m app.seed` (solo con `APP_ENV=development`) crea la planta "Planta Demo" (código DEMO) con turnos día y noche y un usuario `demo.*` por rol base, con la contraseña `DEV_SEED_PASSWORD` de `.env`. No crea la Planta Victoria Sur: esa la crea el administrador, como exige la especificación.
