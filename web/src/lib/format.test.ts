import { describe, expect, it } from "vitest";

import {
  decimalToInput,
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatTime,
  parseDecimalInput,
} from "./format";

describe("formato chileno de números", () => {
  it("usa punto de miles siempre, incluso con 4 cifras", () => {
    expect(formatNumber(1234)).toBe("1.234");
    expect(formatNumber(1234567)).toBe("1.234.567");
  });

  it("usa coma decimal", () => {
    expect(formatNumber(1234.5, 2)).toBe("1.234,50");
    expect(formatNumber("4.125", 3)).toBe("4,125");
  });

  it("muestra guion para valores vacíos o inválidos", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber("")).toBe("—");
    expect(formatNumber("abc")).toBe("—");
  });

  it("formatea porcentajes", () => {
    expect(formatPercent(1.12)).toBe("112,0%");
  });
});

describe("fechas", () => {
  it("convierte AAAA-MM-DD a dd-mm-aaaa sin depender de la zona", () => {
    expect(formatDate("2026-10-27")).toBe("27-10-2026");
  });

  it("muestra fecha-hora UTC en hora de Santiago", () => {
    // 05:00 UTC del 13-01-2026 = 02:00 en Santiago (verano, UTC-3).
    expect(formatDateTime("2026-01-13T05:00:00Z")).toBe("13-01-2026 02:00");
    // 05:00 UTC del 15-07-2026 = 01:00 en Santiago (invierno, UTC-4).
    expect(formatDateTime("2026-07-15T05:00:00Z")).toBe("15-07-2026 01:00");
  });

  it("toma la fecha local de una fecha-hora", () => {
    expect(formatDate("2026-01-13T02:00:00Z")).toBe("12-01-2026");
  });

  it("acorta horas a HH:MM", () => {
    expect(formatTime("20:00:00")).toBe("20:00");
  });
});

describe("entrada decimal", () => {
  it.each([
    ["4,5", "4.5"],
    ["1.234,56", "1234.56"],
    ["1234", "1234"],
    [" 12,0 ", "12.0"],
    ["-3,25", "-3.25"],
  ])("'%s' → %s", (input, expected) => {
    expect(parseDecimalInput(input)).toBe(expected);
  });

  it.each(["", "abc", "1,2,3", ",", "4.5.6,7x"])("rechaza '%s'", (input) => {
    expect(parseDecimalInput(input)).toBeNull();
  });

  it("prepara decimales de la API para editar", () => {
    expect(decimalToInput("1234.5")).toBe("1234,5");
    expect(decimalToInput(null)).toBe("");
  });
});
