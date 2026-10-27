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
