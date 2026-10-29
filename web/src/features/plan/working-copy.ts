/**
 * Copia de trabajo de un plan publicado (ADR 0005, decisión 2): los cambios se acumulan en pantalla y
 * se envían juntos, con un motivo, en un solo lote (`POST /daily-plans/{id}/changes`).
 */
import type { Schemas } from "@/lib/api/client";

export type HarvestEntry = Schemas["HarvestEntryOut"];
export type ChangesBody = Schemas["PlanChangesIn"];

export type LineValues = {
  cage_id: number;
  holding_cage_id: number;
  shift_id: number;
  fish_count: number;
  avg_weight_kg: string;
  notes: string | null;
};

/** Una línea en pantalla. Las nuevas aún no tienen id: su clave es "tmp-<n>". */
export type PlanRow = LineValues & {
  key: number | string;
  id: number | null;
  row_version: string | null;
  farm_center_id: number;
  farm_center_code: string;
  farm_center_name: string;
  cage_code: string;
  holding_cage_code: string;
  shift_name: string;
};

const EDITABLE: (keyof LineValues)[] = ["cage_id", "holding_cage_id", "shift_id", "fish_count", "avg_weight_kg", "notes"];

/** Normaliza el peso para comparar ("4.850" y "4.85" son el mismo valor). */
function sameValue(field: keyof LineValues, a: unknown, b: unknown): boolean {
  if (field === "avg_weight_kg") return Number(a) === Number(b);
  if (field === "notes") return (a || null) === (b || null);
  return a === b;
}

export function fromEntry(e: HarvestEntry): PlanRow {
  return {
    key: e.id,
    id: e.id,
    row_version: e.row_version,
    cage_id: e.cage_id,
    holding_cage_id: e.holding_cage_id,
    shift_id: e.shift_id,
    fish_count: e.fish_count,
    avg_weight_kg: e.avg_weight_kg,
    notes: e.notes,
    farm_center_id: e.farm_center_id,
    farm_center_code: e.farm_center_code,
    farm_center_name: e.farm_center_name,
    cage_code: e.cage_code,
    holding_cage_code: e.holding_cage_code,
    shift_name: e.shift_name,
  };
}

/** Diferencias entre el plan guardado y la copia de trabajo, como lote para la API. */
export function buildChanges(original: readonly PlanRow[], working: readonly PlanRow[]) {
  const before = new Map(original.map((r) => [r.id, r]));
  const kept = new Set(working.filter((r) => r.id !== null).map((r) => r.id));

  const remove = original
    .filter((r) => !kept.has(r.id))
    .map((r) => ({ id: r.id as number, row_version: r.row_version as string }));

  const update = working.flatMap((r) => {
    const old = r.id !== null ? before.get(r.id) : undefined;
    if (!old) return [];
    const changed = EDITABLE.filter((f) => !sameValue(f, old[f], r[f]));
    if (!changed.length) return [];
    return [{ id: r.id as number, row_version: r.row_version as string, ...Object.fromEntries(changed.map((f) => [f, r[f]])) }];
  });

  const added = working.filter((r) => r.id === null);
  const add = added.map(({ cage_id, holding_cage_id, shift_id, fish_count, avg_weight_kg, notes }) => ({
    cage_id,
    holding_cage_id,
    shift_id,
    fish_count,
    avg_weight_kg,
    notes,
  }));
  const newKey = new Map(added.map((r, i) => [r.key, `new-${i}`]));
  const order = working.map((r) => (r.id !== null ? r.id : (newKey.get(r.key) as string)));

  const keptInOrder = original.filter((r) => kept.has(r.id)).map((r) => r.id);
  const reordered = working.filter((r) => r.id !== null).some((r, i) => r.id !== keptInOrder[i]);
  const count = remove.length + update.length + add.length + (reordered ? 1 : 0);
  return { add, update, delete: remove, order, count };
}

/** Mueve una línea una posición hacia arriba (-1) o abajo (+1). */
export function move<T>(rows: readonly T[], index: number, delta: -1 | 1): T[] {
  const target = index + delta;
  if (target < 0 || target >= rows.length) return [...rows];
  const next = [...rows];
  [next[index], next[target]] = [next[target] as T, next[index] as T];
  return next;
}

/** Lleva la línea de `from` a la posición `to` (arrastrar y soltar). */
export function moveTo<T>(rows: readonly T[], from: number, to: number): T[] {
  const next = [...rows];
  const [item] = next.splice(from, 1);
  if (item === undefined) return [...rows];
  next.splice(to, 0, item);
  return next;
}
