import type { ComponentType, ReactNode } from "react";

/** Campos comunes que la API devuelve en todo mantenedor (MaintainerOut). */
export type BaseRow = {
  id: number;
  is_active: boolean;
  row_version: string;
  created_at: string;
  updated_at: string | null;
};

export type Column<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Campo de orden de la API; sin él la columna no se ordena. */
  sortKey?: string;
  numeric?: boolean;
};

export type FilterDef = {
  name: string;
  label: string;
  options: Array<{ value: string; label: string }>;
};

export type FormProps<T> = {
  /** null = alta. */
  item: T | null;
  /** id del <form>: el botón Guardar está en el pie del panel. */
  formId: string;
  /** Envía los valores; lanza ApiError (los errores por campo se muestran en el formulario). */
  onSubmit: (values: Record<string, unknown>) => Promise<void>;
  readOnly: boolean;
};

export type ExtraActionsProps<T> = { item: T; onChanged: (item: T) => void };

export type MaintainerDefinition<T extends BaseRow> = {
  /** Segmento de la API: /api/v1/<resource>. */
  resource: string;
  title: string;
  /** "planta": para mensajes. */
  singular: string;
  newLabel: string;
  viewPermission: string;
  editPermission: string;
  columns: Column<T>[];
  /** Tarjeta del listado en celular. */
  card: (row: T) => { title: ReactNode; subtitle?: ReactNode; meta?: ReactNode };
  rowLabel: (row: T) => string;
  Form: ComponentType<FormProps<T>>;
  filters?: FilterDef[];
  defaultSort?: string;
  searchPlaceholder?: string;
  /** Nombres en español de los campos, para el historial. */
  fieldLabels?: Record<string, string>;
  /** Acciones propias en el panel (restablecer contraseña, desbloquear...). */
  ExtraActions?: ComponentType<ExtraActionsProps<T>>;
  /** Si devuelve false, no se ofrece activar/desactivar (por ejemplo, roles base). */
  canToggleActive?: (row: T) => boolean;
  /** Después de un alta (por ejemplo, mostrar la clave temporal). */
  onCreated?: (row: T) => void;
};

export type Page<T> = { items: T[]; page: number; page_size: number; total: number };
