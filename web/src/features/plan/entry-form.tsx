"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { submitWithApiErrors } from "@/components/maintainer/form-errors";
import { Alert } from "@/components/ui/feedback";
import { Input, NumberInput, Select } from "@/components/ui/form";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { decimalToInput, formatNumber, parseDecimalInput } from "@/lib/format";

import { biomassKg } from "./totals";
import type { LineValues, PlanRow } from "./working-copy";

export type Masters = {
  cages: Schemas["CageOut"][];
  holdingCages: Schemas["HoldingCageOut"][];
  shifts: Schemas["ShiftOut"][];
};

/** Jaulas, acopios y turnos activos para armar las líneas del plan de una planta. */
export function usePlanMasters(plantId: number | null) {
  return useQuery({
    queryKey: ["plan-masters", plantId],
    enabled: plantId !== null,
    staleTime: 5 * 60_000,
    queryFn: async (): Promise<Masters> => {
      const base = { status: "active", page_size: 200 } as const;
      const [cages, holdingCages, shifts] = await Promise.all([
        api.GET("/api/v1/cages", { params: { query: { ...base, sort: "code" } } }).then(unwrap),
        api.GET("/api/v1/holding-cages", { params: { query: { ...base, sort: "code", plant_id: plantId as number } } }).then(unwrap),
        api.GET("/api/v1/shifts", { params: { query: { ...base, sort: "sort_order", plant_id: plantId as number } } }).then(unwrap),
      ]);
      return { cages: cages.items, holdingCages: holdingCages.items, shifts: shifts.items };
    },
  });
}

const schema = z.object({
  farm_center_id: z.string().min(1, "Elija el centro."),
  cage_id: z.string().min(1, "Elija la jaula."),
  holding_cage_id: z.string().min(1, "Elija la jaula de acopio."),
  shift_id: z.string().min(1, "Elija el turno."),
  fish_count: z.string().regex(/^\d{1,3}(\.?\d{3})*$/, "Número entero de peces."),
  avg_weight_kg: z.string().min(1, "Campo obligatorio."),
  notes: z.string().max(500, "Máximo 500 caracteres."),
});
type FormValues = z.infer<typeof schema>;

const FIELDS = ["cage_id", "holding_cage_id", "shift_id", "fish_count", "avg_weight_kg", "notes"] as const;

/** Etiquetas de la línea elegida, para mostrarla en pantalla antes de guardarla. */
export function describeLine(values: LineValues, masters: Masters) {
  const cage = masters.cages.find((c) => c.id === values.cage_id);
  return {
    farm_center_id: cage?.farm_center_id ?? 0,
    farm_center_code: cage?.farm_center_code ?? "—",
    farm_center_name: cage?.farm_center_name ?? "—",
    cage_code: cage?.code ?? "—",
    holding_cage_code: masters.holdingCages.find((h) => h.id === values.holding_cage_id)?.code ?? "—",
    shift_name: masters.shifts.find((s) => s.id === values.shift_id)?.name ?? "—",
  };
}

export function EntryForm({
  formId,
  row,
  masters,
  readOnly,
  onSubmit,
}: {
  formId: string;
  row: PlanRow | null;
  masters: Masters;
  readOnly: boolean;
  onSubmit: (values: LineValues) => Promise<void>;
}) {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      farm_center_id: row ? String(row.farm_center_id) : "",
      cage_id: row ? String(row.cage_id) : "",
      holding_cage_id: row ? String(row.holding_cage_id) : masters.holdingCages.length === 1 ? String(masters.holdingCages[0]?.id) : "",
      shift_id: row ? String(row.shift_id) : "",
      fish_count: row ? String(row.fish_count) : "",
      avg_weight_kg: row ? decimalToInput(Number(row.avg_weight_kg)) : "",
      notes: row?.notes ?? "",
    },
  });
  const errors = form.formState.errors;
  const [centerValue, fishValue, weightValue] = useWatch({
    control: form.control,
    name: ["farm_center_id", "fish_count", "avg_weight_kg"],
  });
  const centerId = Number(centerValue);
  const fish = Number(fishValue.replace(/\./g, ""));
  const weight = parseDecimalInput(weightValue);

  const centers = [...new Map(masters.cages.map((c) => [c.farm_center_id, c])).values()].sort((a, b) =>
    a.farm_center_code.localeCompare(b.farm_center_code),
  );
  const cages = masters.cages.filter((c) => c.farm_center_id === centerId);
  const preview = fish > 0 && weight && Number(weight) > 0 ? biomassKg(fish, weight) : null;

  const submit = form.handleSubmit((v) => {
    const parsedWeight = parseDecimalInput(v.avg_weight_kg);
    const count = Number(v.fish_count.replace(/\./g, ""));
    if (!parsedWeight || Number(parsedWeight) <= 0 || !/^\d+(\.\d{1,3})?$/.test(parsedWeight)) {
      form.setError("avg_weight_kg", { message: "Peso en kg mayor que 0, con hasta 3 decimales." });
      return;
    }
    if (count <= 0) {
      form.setError("fish_count", { message: "Debe ser mayor que 0." });
      return;
    }
    const values: LineValues = {
      cage_id: Number(v.cage_id),
      holding_cage_id: Number(v.holding_cage_id),
      shift_id: Number(v.shift_id),
      fish_count: count,
      avg_weight_kg: parsedWeight,
      notes: v.notes.trim() || null,
    };
    return submitWithApiErrors(form.setError, FIELDS, () => onSubmit(values));
  });

  return (
    <form id={formId} noValidate className="space-y-4" onSubmit={submit}>
      {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
      <fieldset disabled={readOnly} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Centro"
            required
            error={errors.farm_center_id?.message}
            {...form.register("farm_center_id", { onChange: () => form.setValue("cage_id", "") })}
          >
            <option value="">Elegir</option>
            {centers.map((c) => (
              <option key={c.farm_center_id} value={c.farm_center_id}>
                {c.farm_center_code} · {c.farm_center_name}
              </option>
            ))}
          </Select>
          <Select label="Jaula" required error={errors.cage_id?.message} {...form.register("cage_id")}>
            <option value="">{centerId ? "Elegir" : "Elija centro"}</option>
            {cages.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code}
              </option>
            ))}
          </Select>
          <Select label="Turno" required error={errors.shift_id?.message} {...form.register("shift_id")}>
            <option value="">Elegir</option>
            {masters.shifts.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
          <Select label="Jaula de acopio" required error={errors.holding_cage_id?.message} {...form.register("holding_cage_id")}>
            <option value="">Elegir</option>
            {masters.holdingCages.map((h) => (
              <option key={h.id} value={h.id}>
                {h.code} ({formatNumber(h.capacity_fish)} peces)
              </option>
            ))}
          </Select>
          <NumberInput label="Peces" required decimals={false} error={errors.fish_count?.message} {...form.register("fish_count")} />
          <NumberInput label="Peso promedio (kg)" required error={errors.avg_weight_kg?.message} {...form.register("avg_weight_kg")} />
        </div>
        <p className="rounded-lg bg-bg px-3 py-2 text-sm text-muted">
          Biomasa estimada: <span className="num font-semibold text-navy">{preview === null ? "—" : `${formatNumber(preview, 0)} kg`}</span>
        </p>
        <Input label="Observaciones" maxLength={500} error={errors.notes?.message} {...form.register("notes")} />
      </fieldset>
    </form>
  );
}
