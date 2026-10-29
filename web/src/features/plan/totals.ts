/**
 * Totales en vivo del plan de cosecha en el navegador (mientras se acumulan cambios sin guardar).
 * Misma regla que el backend (app/domain/harvest.py): biomasa = peces × peso promedio, exacta a 3
 * decimales; WFE = biomasa del grupo × factor, redondeado a 3 decimales una sola vez. El backend sigue
 * siendo la fuente de verdad: valida y recalcula al guardar.
 *
 * Se calcula en gramos enteros para no arrastrar errores de punto flotante (12.000 peces × 4,850 kg
 * = 58.200.000 g, muy por debajo de 2^53).
 */

export type TotalsLine = { fish_count: number; avg_weight_kg: string; shift_id: number; farm_center_id: number };

export type LiveTotals = { lines: number; fish: number; biomassKg: number; wfeKg: number | null };

/** "4.850" → 4850 gramos. Acepta hasta 3 decimales (lo que guarda la base). */
export function weightToGrams(weight: string): number {
  const [int = "0", frac = ""] = weight.split(".");
  return Number(int) * 1000 + Number((frac + "000").slice(0, 3));
}

export function biomassKg(fish: number, weight: string): number {
  return (fish * weightToGrams(weight)) / 1000;
}

function wfe(biomassGrams: number, factor: string | null | undefined): number | null {
  if (factor === null || factor === undefined || factor === "") return null;
  // Redondeo a 3 decimales de kg (= gramos), mitad hacia arriba como en el backend.
  return Math.round(biomassGrams * Number(factor)) / 1000;
}

export function liveTotals(lines: readonly TotalsLine[], factor: string | null | undefined): LiveTotals {
  const grams = lines.reduce((sum, l) => sum + l.fish_count * weightToGrams(l.avg_weight_kg), 0);
  return {
    lines: lines.length,
    fish: lines.reduce((sum, l) => sum + l.fish_count, 0),
    biomassKg: grams / 1000,
    wfeKg: wfe(grams, factor),
  };
}

export function groupTotals<K extends "shift_id" | "farm_center_id">(
  lines: readonly TotalsLine[],
  key: K,
  factor: string | null | undefined,
): Map<number, LiveTotals> {
  const groups = new Map<number, TotalsLine[]>();
  for (const line of lines) groups.set(line[key], [...(groups.get(line[key]) ?? []), line]);
  return new Map([...groups].map(([id, group]) => [id, liveTotals(group, factor)]));
}
