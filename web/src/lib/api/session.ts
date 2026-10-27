/**
 * Sesión del navegador.
 *
 * - El token de acceso vive solo en memoria (nunca en localStorage): un script inyectado no lo encuentra.
 * - El refresh token está en una cookie httpOnly que el navegador envía solo a /api/v1/auth.
 * - Al recargar la página la sesión se recupera llamando a /auth/refresh.
 * - Si una llamada responde 401, se refresca una vez y se reintenta; varias llamadas simultáneas
 *   comparten el mismo refresco.
 */

const AUTH_BASE = "/api/v1/auth";

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
const listeners = new Set<() => void>();

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function hasAccessToken(): boolean {
  return accessToken !== null;
}

/** Aviso cuando la sesión se pierde (refresh rechazado): el AuthProvider vuelve a /login. */
export function onSessionExpired(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const res = await fetch(`${AUTH_BASE}/refresh`, { method: "POST", credentials: "same-origin" });
      if (!res.ok) {
        accessToken = null;
        return false;
      }
      const body = (await res.json()) as { access_token: string };
      accessToken = body.access_token;
      return true;
    } catch {
      accessToken = null;
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

function send(request: Request): Promise<Response> {
  const req = new Request(request);
  if (accessToken) req.headers.set("Authorization", `Bearer ${accessToken}`);
  return fetch(req, { credentials: "same-origin" });
}

function isAuthCall(url: string): boolean {
  const path = new URL(url, window.location.origin).pathname;
  return path === `${AUTH_BASE}/login` || path === `${AUTH_BASE}/refresh`;
}

/** fetch con token y reintento tras refrescar la sesión. Lo usa el cliente de la API. */
export async function authFetch(request: Request): Promise<Response> {
  const retry = request.clone();
  const response = await send(request);
  if (response.status !== 401 || isAuthCall(request.url)) return response;
  if (!(await refreshSession())) {
    listeners.forEach((listener) => listener());
    return response;
  }
  return send(retry);
}
