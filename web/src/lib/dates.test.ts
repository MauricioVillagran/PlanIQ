import { describe, expect, it } from "vitest";

import { safeNext } from "./auth/redirect";
import { addDays, isIsoDate, weekdayLabel } from "./dates";

describe("fechas productivas", () => {
  it("valida AAAA-MM-DD", () => {
    expect(isIsoDate("2026-10-27")).toBe(true);
    expect(isIsoDate("27-10-2026")).toBe(false);
    expect(isIsoDate("2026-13-01")).toBe(false);
    expect(isIsoDate(null)).toBe(false);
  });

  it("suma días cruzando meses y años", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-01-01", -1)).toBe("2025-12-31");
  });

  it("no se corre de día con el cambio de horario de Chile", () => {
    // Primer domingo de abril y de septiembre de 2026.
    expect(addDays("2026-04-04", 1)).toBe("2026-04-05");
    expect(addDays("2026-09-05", 1)).toBe("2026-09-06");
  });

  it("nombra el día de la semana en español", () => {
    expect(weekdayLabel("2026-10-27")).toBe("martes");
  });
});

describe("redirección tras el ingreso", () => {
  it.each([
    ["/settings/users?plant=1", "/settings/users?plant=1"],
    [null, "/"],
    ["https://otro-sitio.com", "/"],
    ["//otro-sitio.com", "/"],
    ["/\\otro-sitio.com", "/"],
    ["/login", "/"],
  ])("%s → %s", (next, expected) => {
    expect(safeNext(next)).toBe(expected);
  });
});
