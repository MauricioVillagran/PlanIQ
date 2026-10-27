"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Moon } from "lucide-react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { submitWithApiErrors } from "@/components/maintainer/form-errors";
import { StatusBadge } from "@/components/maintainer/maintainer-page";
import type { FormProps, MaintainerDefinition } from "@/components/maintainer/types";
import { Card } from "@/components/ui/card";
import { Alert, Badge, Skeleton } from "@/components/ui/feedback";
import { Input, NumberInput } from "@/components/ui/form";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { formatNumber, formatTime } from "@/lib/format";

export type Shift = Schemas["ShiftOut"];
type PlantRef = { id: number; name: string };

const TIME = /^\d{2}:\d{2}$/;
const schema = z.object({
  name: z.string().trim().min(1, "Campo obligatorio.").max(50, "Máximo 50 caracteres."),
  start_time: z.string().regex(TIME, "Hora inválida (HH:MM)."),
  end_time: z.string().regex(TIME, "Hora inválida (HH:MM)."),
  sort_order: z.string().regex(/^\d{1,2}$/, "Número entre 0 y 99."),
});
type Values = z.infer<typeof schema>;
const FIELDS = ["name", "start_time", "end_time", "sort_order"] as const;

function durationLabel(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

function makeShiftForm(plant: PlantRef | null) {
  return function ShiftForm({ item, formId, onSubmit, readOnly }: FormProps<Shift>) {
    const form = useForm<Values>({
      resolver: zodResolver(schema),
      defaultValues: {
        name: item?.name ?? "",
        start_time: item ? formatTime(item.start_time) : "",
        end_time: item ? formatTime(item.end_time) : "",
        sort_order: String(item?.sort_order ?? 0),
      },
    });
    const errors = form.formState.errors;
    const [start, end] = useWatch({ control: form.control, name: ["start_time", "end_time"] });
    const crosses = TIME.test(start) && TIME.test(end) && end <= start && end !== start;

    return (
      <form
        id={formId}
        noValidate
        className="space-y-4"
        onSubmit={form.handleSubmit((values) =>
          submitWithApiErrors(form.setError, FIELDS, () =>
            onSubmit({
              ...(item ? {} : { plant_id: plant?.id }),
              name: values.name,
              start_time: values.start_time,
              end_time: values.end_time,
              sort_order: Number(values.sort_order),
            }),
          ),
        )}
      >
        {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
        <p className="text-sm text-muted">
          Planta: <span className="font-semibold text-navy">{plant?.name ?? "—"}</span>
        </p>
        <fieldset disabled={readOnly} className="space-y-4">
          <Input label="Nombre" required placeholder="Día, Noche…" error={errors.name?.message} {...form.register("name")} />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Inicio" type="time" required className="num" error={errors.start_time?.message} {...form.register("start_time")} />
            <Input label="Término" type="time" required className="num" error={errors.end_time?.message} {...form.register("end_time")} />
          </div>
          {crosses && (
            <Alert tone="info">
              El turno cruza la medianoche: lo producido después de las 00:00 se imputa a la fecha en que empezó.
            </Alert>
          )}
          <NumberInput label="Orden" decimals={false} hint="Orden en que se muestran los turnos." error={errors.sort_order?.message} {...form.register("sort_order")} />
        </fieldset>
      </form>
    );
  };
}

/** Cobertura de las 24 horas de los turnos activos de la planta del contexto. */
export function ShiftCoverage({ plantId }: { plantId: number }) {
  const coverage = useQuery({
    queryKey: ["shifts", "coverage", plantId],
    queryFn: async () => unwrap(await api.GET("/api/v1/shifts/coverage", { params: { query: { plant_id: plantId } } })),
  });
  if (coverage.isPending) return <Skeleton className="mb-3 h-16" />;
  if (!coverage.data) return null;
  const { covered, gaps, covered_minutes, full_coverage_required } = coverage.data;
  const tone = covered ? "border-l-teal" : full_coverage_required ? "border-l-coral" : "border-l-blue-mid";
  return (
    <Card className={`mb-3 flex flex-wrap items-center justify-between gap-2 border-l-4 px-4 py-3 ${tone}`}>
      <div>
        <p className="text-sm font-semibold text-navy">
          {covered ? "Los turnos cubren las 24 horas" : `Cubren ${durationLabel(covered_minutes)} de 24 h`}
        </p>
        {!covered && (
          <p className="text-sm text-muted">
            Sin turno:{" "}
            <span className="num">{gaps.map((g) => `${formatTime(g.start)}–${formatTime(g.end)}`).join(", ")}</span>
          </p>
        )}
      </div>
      <Badge tone={full_coverage_required ? (covered ? "ok" : "alert") : "neutral"}>
        {full_coverage_required ? "Cobertura completa exigida" : "Huecos permitidos"}
      </Badge>
    </Card>
  );
}

export function makeShiftsDefinition(plant: PlantRef | null): MaintainerDefinition<Shift> {
  return {
    resource: "shifts",
    title: "Turnos",
    singular: "turno",
    newLabel: "Nuevo turno",
    viewPermission: "masters.view",
    editPermission: "masters.edit",
    defaultSort: "sort_order",
    searchPlaceholder: "Buscar turno",
    columns: [
      { key: "name", header: "Turno", sortKey: "name", render: (s) => s.name },
      { key: "start", header: "Inicio", sortKey: "start_time", render: (s) => <span className="num">{formatTime(s.start_time)}</span> },
      { key: "end", header: "Término", render: (s) => <span className="num">{formatTime(s.end_time)}</span> },
      { key: "duration", header: "Duración", render: (s) => durationLabel(s.duration_minutes) },
      {
        key: "midnight",
        header: "Cruza medianoche",
        render: (s) => (s.crosses_midnight ? <Badge tone="info">Sí</Badge> : "No"),
      },
      { key: "order", header: "Orden", sortKey: "sort_order", numeric: true, render: (s) => formatNumber(s.sort_order) },
      { key: "status", header: "Estado", render: (s) => <StatusBadge active={s.is_active} /> },
    ],
    card: (s) => ({
      title: (
        <span className="inline-flex items-center gap-1.5">
          {s.name}
          {s.crosses_midnight && <Moon aria-label="Cruza medianoche" className="size-4 text-blue-mid" />}
        </span>
      ),
      subtitle: (
        <span className="num">
          {formatTime(s.start_time)}–{formatTime(s.end_time)} · {durationLabel(s.duration_minutes)}
        </span>
      ),
    }),
    rowLabel: (s) => `Turno ${s.name}`,
    Form: makeShiftForm(plant),
    fieldLabels: {
      name: "Nombre",
      start_time: "Inicio",
      end_time: "Término",
      crosses_midnight: "Cruza medianoche",
      sort_order: "Orden",
      plant_id: "Planta",
      is_active: "Activo",
    },
  };
}
