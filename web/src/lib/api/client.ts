import createClient from "openapi-fetch";

import type { components, paths } from "./schema";
import { authFetch } from "./session";

/** Cliente tipado desde el OpenAPI de la API (`npm run api:types` lo regenera). */
export const api = createClient<paths>({ baseUrl: "", fetch: authFetch });

export type Schemas = components["schemas"];
export type FieldErrorItem = Schemas["FieldError"];

/** Error de la API con el formato único {code, message, details, field_errors}. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly fieldErrors: FieldErrorItem[] = [],
    readonly details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Mensaje del primer error de un campo, para mostrar bajo el input. */
  fieldMessage(field: string): string | undefined {
    return this.fieldErrors.find((e) => e.field === field)?.message;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function withQuery(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

/**
 * Llamada genérica por ruta dinámica, para el componente de mantenedor (los recursos se eligen en
 * tiempo de ejecución). En código específico preferir `api`, que está tipado por ruta.
 */
export async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  options: { query?: Query; body?: unknown } = {},
): Promise<T> {
  const response = await authFetch(
    new Request(withQuery(path, options.query), {
      method,
      headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    }),
  );
  const body: unknown = response.status === 204 ? undefined : await response.json().catch(() => undefined);
  if (response.ok) return body as T;
  return unwrap<T>({ error: body ?? {}, response });
}

/** Descarga un archivo autenticado (por ejemplo la exportación a Excel) y lo guarda en el equipo. */
export async function download(path: string, query?: Query): Promise<void> {
  const response = await authFetch(new Request(withQuery(path, query)));
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => ({}));
    unwrap({ error: body, response });
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "export.xlsx";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Devuelve los datos o lanza ApiError. Usar en las funciones de TanStack Query. */
export function unwrap<T>({ data, error, response }: Result<T>): T {
  if (response.ok && error === undefined) return data as T;
  const body = (error ?? {}) as Partial<Schemas["ErrorResponse"]>;
  throw new ApiError(
    response.status,
    body.code ?? "http_error",
    body.message ?? "No se pudo completar la operación.",
    body.field_errors ?? [],
    (body.details as Record<string, unknown> | null | undefined) ?? null,
  );
}
