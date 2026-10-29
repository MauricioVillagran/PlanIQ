import { describe, expect, it } from "vitest";

import { biomassKg, groupTotals, liveTotals, weightToGrams } from "./totals";

const line = (fish: number, weight: string, shift = 1, center = 1) => ({
  fish_count: fish,
  avg_weight_kg: weight,
  shift_id: shift,
  farm_center_id: center,
});

describe("totales del plan", () => {
  it("convierte el peso a gramos sin errores de punto flotante", () => {
    expect(weightToGrams("4.850")).toBe(4850);
    expect(weightToGrams("4.85")).toBe(4850);
    expect(weightToGrams("5")).toBe(5000);
    expect(biomassKg(12_000, "4.850")).toBe(58_200);
  });

  it("coincide con el cálculo manual de control del backend", () => {
    // 12.000 × 4,850 + 9.500 × 5,120 = 106.840 kg; WFE × 0,9 = 96.156 kg.
    const totals = liveTotals([line(12_000, "4.850"), line(9_500, "5.120", 2, 2)], "0.9");
    expect(totals).toEqual({ lines: 2, fish: 21_500, biomassKg: 106_840, wfeKg: 96_156 });
  });

  it("sin factor no hay WFE", () => {
    expect(liveTotals([line(1_000, "4.5")], null).wfeKg).toBeNull();
  });

  it("agrupa por turno y por centro", () => {
    const lines = [line(1_000, "4", 1, 10), line(2_000, "5", 2, 10), line(3_000, "6", 1, 20)];
    expect(groupTotals(lines, "shift_id", null).get(1)?.fish).toBe(4_000);
    expect(groupTotals(lines, "farm_center_id", null).get(10)?.biomassKg).toBe(14_000);
  });
});
