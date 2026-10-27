"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect } from "react";

import { Select } from "@/components/ui/form";
import { api, unwrap } from "@/lib/api/client";
import { useAppContext } from "@/lib/app-context";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { addDays, todayIn } from "@/lib/dates";
import { formatTime } from "@/lib/format";

const LAST_PLANT_KEY = "planiq.lastPlant";

function readLastPlant(): number | null {
  try {
    return Number(window.localStorage.getItem(LAST_PLANT_KEY)) || null;
  } catch {
    return null;
  }
}

function rememberPlant(id: number): void {
  try {
    window.localStorage.setItem(LAST_PLANT_KEY, String(id));
  } catch {
    // Navegación privada: no se recuerda, sin consecuencias.
  }
}

/** Selector de planta, fecha productiva y turno, siempre visible (sección 9). */
export function ContextBar({ className }: { className?: string }) {
  const { can } = useAuth();
  const { plants, plant, date, shiftId, update } = useAppContext();

  // Sin planta en la URL: la última usada en este navegador o la primera disponible.
  useEffect(() => {
    if (plant || plants.length === 0) return;
    const last = readLastPlant();
    update({ plant: plants.find((p) => p.id === last)?.id ?? plants[0]!.id });
  }, [plant, plants, update]);

  const shifts = useQuery({
    queryKey: ["shifts", "active", plant?.id],
    enabled: !!plant && can("masters.view"),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/shifts", {
          params: { query: { plant_id: plant!.id, status: "active", sort: "sort_order", page_size: 50 } },
        }),
      ).items,
  });

  if (plants.length === 0) {
    return <p className={cn("text-sm text-coral", className)}>Sin plantas asignadas. Contacte al administrador.</p>;
  }

  const today = todayIn();
  return (
    <div className={cn("grid grid-cols-2 gap-2 lg:flex lg:items-center", className)}>
      <Select
        label="Planta"
        hideLabel
        value={plant?.id ?? ""}
        onChange={(e) => {
          const id = Number(e.target.value);
          rememberPlant(id);
          update({ plant: id });
        }}
        className="lg:w-56"
      >
        {plants.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </Select>

      <Select
        label="Turno"
        hideLabel
        value={shiftId ?? ""}
        onChange={(e) => update({ shift: Number(e.target.value) || null })}
        disabled={!shifts.data?.length}
        className="lg:w-44"
      >
        <option value="">Todos</option>
        {shifts.data?.map((s) => (
          <option key={s.id} value={s.id} title={`${formatTime(s.start_time)}–${formatTime(s.end_time)}`}>
            {s.name}
          </option>
        ))}
      </Select>

      <div className="col-span-2 flex items-center gap-1 lg:col-span-1">
        <button
          type="button"
          aria-label="Día anterior"
          onClick={() => update({ date: addDays(date, -1) })}
          className="flex size-11 shrink-0 items-center justify-center rounded-lg border border-gray bg-card text-navy hover:border-teal"
        >
          <ChevronLeft aria-hidden className="size-5" />
        </button>
        <label className="sr-only" htmlFor="context-date">
          Fecha productiva
        </label>
        <input
          id="context-date"
          type="date"
          value={date}
          onChange={(e) => update({ date: e.target.value || null })}
          className="num h-11 min-w-0 flex-1 rounded-lg border border-gray bg-card px-2 text-center text-navy focus:border-teal focus:outline-none lg:w-40 lg:flex-none"
        />
        <button
          type="button"
          aria-label="Día siguiente"
          onClick={() => update({ date: addDays(date, 1) })}
          className="flex size-11 shrink-0 items-center justify-center rounded-lg border border-gray bg-card text-navy hover:border-teal"
        >
          <ChevronRight aria-hidden className="size-5" />
        </button>
        {date !== today && (
          <button
            type="button"
            onClick={() => update({ date: null })}
            className="h-11 shrink-0 rounded-lg px-2 text-sm font-semibold text-teal hover:bg-teal/10"
          >
            Hoy
          </button>
        )}
      </div>
    </div>
  );
}
