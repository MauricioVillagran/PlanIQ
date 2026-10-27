import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError } from "@/lib/api/client";

/**
 * Envía el formulario y lleva los errores de la API a los campos (mismos mensajes que devuelve la API).
 * Los errores sin campo quedan en `root.server`.
 */
export async function submitWithApiErrors<T extends FieldValues>(
  setError: UseFormSetError<T>,
  fields: readonly string[],
  action: () => Promise<void>,
): Promise<void> {
  try {
    await action();
  } catch (error) {
    if (!(error instanceof ApiError)) {
      setError("root.server", { message: "No se pudo conectar con el servidor." });
      return;
    }
    let mapped = false;
    for (const fieldError of error.fieldErrors) {
      const field = fieldError.field.split(".")[0] ?? fieldError.field;
      if (fields.includes(field)) {
        setError(field as Path<T>, { message: fieldError.message });
        mapped = true;
      }
    }
    // El mensaje general de una regla de negocio suele dar el contexto ("se traslapa con: Noche").
    if (!mapped || error.code !== "validation_error") setError("root.server", { message: error.message });
  }
}
