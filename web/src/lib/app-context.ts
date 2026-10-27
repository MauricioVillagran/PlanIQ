"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import { useAuth } from "@/lib/auth/auth-context";
import { isIsoDate, todayIn } from "@/lib/dates";

/**
 * Contexto de trabajo global: planta, fecha productiva y turno, guardado en la URL
 * (?plant=1&date=2026-10-27&shift=3) para que un enlace compartido abra exactamente la misma vista.
 */
export type AppContextUpdate = { plant?: number | null; date?: string | null; shift?: number | null };

const KEYS = ["plant", "date", "shift"] as const;

export function useAppContext() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { me } = useAuth();

  const plants = useMemo(() => me?.plants ?? [], [me]);
  const plantParam = Number(params.get("plant"));
  const plant = plants.find((p) => p.id === plantParam) ?? null;
  const dateParam = params.get("date");
  const date = isIsoDate(dateParam) ? dateParam : todayIn();
  const shiftId = Number(params.get("shift")) || null;

  const update = useCallback(
    (changes: AppContextUpdate) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(changes)) {
        if (value === null || value === undefined || value === "") next.delete(key);
        else next.set(key, String(value));
      }
      // Cambiar de planta invalida el turno elegido.
      if ("plant" in changes && !("shift" in changes)) next.delete("shift");
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  /** Enlace interno que conserva planta, fecha y turno. */
  const href = useCallback(
    (path: string) => {
      const kept = new URLSearchParams();
      for (const key of KEYS) {
        const value = params.get(key);
        if (value) kept.set(key, value);
      }
      const query = kept.toString();
      return query ? `${path}?${query}` : path;
    },
    [params],
  );

  return { plants, plant, date, shiftId, update, href };
}
