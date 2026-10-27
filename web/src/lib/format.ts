/**
 * Formato chileno (sección 9): miles con punto, decimales con coma, fechas dd-mm-aaaa.
 * Las fechas y horas se muestran en la zona de la planta.
 */

export const DEFAULT_TIMEZONE = "America/Santiago";

/** Número con separador de miles siempre (en español Intl omite el punto en números de 4 cifras). */
export function formatNumber(value: number | string | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("es-CL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: "always",
  }).format(number);
}

export function formatPercent(value: number | null | undefined, decimals = 1): string {
  return value === null || value === undefined ? "—" : `${formatNumber(value * 100, decimals)}%`;
}

/** "2026-10-27" → "27-10-2026". Acepta también una fecha-hora ISO (usa la fecha local de la planta). */
export function formatDate(value: string | null | undefined, timeZone = DEFAULT_TIMEZONE): string {
  if (!value) return "—";
  const plain = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (plain) return `${plain[3]}-${plain[2]}-${plain[1]}`;
  const parts = datePartsIn(new Date(value), timeZone);
  return `${parts.day}-${parts.month}-${parts.year}`;
}

/** Fecha-hora ISO (UTC) → "27-10-2026 14:05" en la zona de la planta. */
export function formatDateTime(value: string | null | undefined, timeZone = DEFAULT_TIMEZONE): string {
  if (!value) return "—";
  const parts = datePartsIn(new Date(value), timeZone);
  return `${parts.day}-${parts.month}-${parts.year} ${parts.hour}:${parts.minute}`;
}

/** "20:00:00" → "20:00". */
export function formatTime(value: string | null | undefined): string {
  return value ? value.slice(0, 5) : "—";
}

function datePartsIn(date: Date, timeZone: string): Record<"day" | "month" | "year" | "hour" | "minute", string> {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === type)?.value ?? "";
  return { day: get("day"), month: get("month"), year: get("year"), hour: get("hour"), minute: get("minute") };
}

/**
 * Texto escrito por el usuario → decimal para la API ("1.234,5" → "1234.5").
 * Devuelve null si no es un número válido. Punto = miles, coma = decimal.
 */
export function parseDecimalInput(text: string): string | null {
  const trimmed = text.trim().replace(/\s/g, "");
  if (!trimmed) return null;
  if (!/^-?[\d.]*,?\d*$/.test(trimmed)) return null;
  const normalized = trimmed.replace(/\./g, "").replace(",", ".");
  if (normalized === "" || normalized === "-" || normalized === ".") return null;
  return Number.isFinite(Number(normalized)) ? normalized : null;
}

/** Decimal de la API ("1234.5") → texto para editar ("1234,5"), sin separador de miles. */
export function decimalToInput(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(".", ",");
}
