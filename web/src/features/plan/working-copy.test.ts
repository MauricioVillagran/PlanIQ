import { describe, expect, it } from "vitest";

import { buildChanges, move, moveTo, type PlanRow } from "./working-copy";

function row(id: number | null, key: number | string, fish: number, weight = "4.500"): PlanRow {
  return {
    key,
    id,
    row_version: id ? `00000000000000${String(id).padStart(2, "0")}` : null,
    cage_id: 1,
    holding_cage_id: 1,
    shift_id: 1,
    fish_count: fish,
    avg_weight_kg: weight,
    notes: null,
    farm_center_id: 1,
    farm_center_code: "CN",
    farm_center_name: "Centro Norte",
    cage_code: "N1",
    holding_cage_code: "A1",
    shift_name: "Día",
  };
}

describe("lote de cambios de un plan publicado", () => {
  const original = [row(1, 1, 1_000), row(2, 2, 2_000), row(3, 3, 3_000)];

  it("sin cambios no hay nada que enviar", () => {
    expect(buildChanges(original, original).count).toBe(0);
  });

  it("detecta modificaciones, bajas, altas y el orden resultante", () => {
    const working = [row(3, 3, 3_000), { ...row(1, 1, 1_500) }, row(null, "tmp-1", 800)];
    const changes = buildChanges(original, working);
    expect(changes.update).toEqual([{ id: 1, row_version: "0000000000000001", fish_count: 1_500 }]);
    expect(changes.delete).toEqual([{ id: 2, row_version: "0000000000000002" }]);
    expect(changes.add).toHaveLength(1);
    expect(changes.order).toEqual([3, 1, "new-0"]);
    expect(changes.count).toBe(4);
  });

  it("el mismo peso escrito distinto no es un cambio", () => {
    const working = [row(1, 1, 1_000, "4.5"), row(2, 2, 2_000), row(3, 3, 3_000)];
    expect(buildChanges(original, working).count).toBe(0);
  });

  it("mueve líneas con botones y arrastrando", () => {
    expect(move([1, 2, 3], 0, 1)).toEqual([2, 1, 3]);
    expect(move([1, 2, 3], 0, -1)).toEqual([1, 2, 3]);
    expect(moveTo([1, 2, 3], 2, 0)).toEqual([3, 1, 2]);
  });
});
