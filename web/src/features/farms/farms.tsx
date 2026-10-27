"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { submitWithApiErrors } from "@/components/maintainer/form-errors";
import { StatusBadge } from "@/components/maintainer/maintainer-page";
import type { FormProps, MaintainerDefinition } from "@/components/maintainer/types";
import { Alert } from "@/components/ui/feedback";
import { Input, NumberInput, Select } from "@/components/ui/form";
import type { Schemas } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";

export type FarmCenter = Schemas["FarmCenterOut"];
export type Cage = Schemas["CageOut"];
export type HoldingCage = Schemas["HoldingCageOut"];
type Ref = { id: number; code: string; name: string };

const required = (max: number) => z.string().trim().min(1, "Campo obligatorio.").max(max, `Máximo ${max} caracteres.`);

// --- Centros -----------------------------------------------------------------------------

const centerSchema = z.object({ code: required(20), name: required(150), zone: z.string().trim().max(100) });
type CenterValues = z.infer<typeof centerSchema>;

function FarmCenterForm({ item, formId, onSubmit, readOnly }: FormProps<FarmCenter>) {
  const form = useForm<CenterValues>({
    resolver: zodResolver(centerSchema),
    defaultValues: { code: item?.code ?? "", name: item?.name ?? "", zone: item?.zone ?? "" },
  });
  const errors = form.formState.errors;
  return (
    <form
      id={formId}
      noValidate
      className="space-y-4"
      onSubmit={form.handleSubmit((v) =>
        submitWithApiErrors(form.setError, ["code", "name", "zone"], () => onSubmit({ ...v, zone: v.zone || null })),
      )}
    >
      {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
      <fieldset disabled={readOnly} className="space-y-4">
        <Input label="Código" required autoCapitalize="characters" className="num" error={errors.code?.message} {...form.register("code")} />
        <Input label="Nombre" required error={errors.name?.message} {...form.register("name")} />
        <Input label="Zona o barrio" error={errors.zone?.message} {...form.register("zone")} />
      </fieldset>
    </form>
  );
}

export const farmCentersDefinition: MaintainerDefinition<FarmCenter> = {
  resource: "farm-centers",
  title: "Centros de cultivo",
  singular: "centro",
  newLabel: "Nuevo centro",
  viewPermission: "masters.view",
  editPermission: "farms.edit",
  defaultSort: "name",
  searchPlaceholder: "Buscar por código, nombre o zona",
  columns: [
    { key: "code", header: "Código", sortKey: "code", render: (c) => <span className="num">{c.code}</span> },
    { key: "name", header: "Centro", sortKey: "name", render: (c) => c.name },
    { key: "zone", header: "Zona o barrio", sortKey: "zone", render: (c) => c.zone ?? "—" },
    { key: "status", header: "Estado", render: (c) => <StatusBadge active={c.is_active} /> },
  ],
  card: (c) => ({ title: c.name, subtitle: <span className="num">{c.code}</span>, meta: c.zone }),
  rowLabel: (c) => `${c.code} · ${c.name}`,
  Form: FarmCenterForm,
  fieldLabels: { code: "Código", name: "Nombre", zone: "Zona o barrio", is_active: "Activo" },
};

// --- Jaulas ------------------------------------------------------------------------------

const cageSchema = z.object({ farm_center_id: z.string(), code: required(20) });
type CageValues = z.infer<typeof cageSchema>;

function makeCageForm(centers: Ref[]) {
  return function CageForm({ item, formId, onSubmit, readOnly }: FormProps<Cage>) {
    const form = useForm<CageValues>({
      resolver: zodResolver(cageSchema),
      defaultValues: { farm_center_id: String(item?.farm_center_id ?? centers[0]?.id ?? ""), code: item?.code ?? "" },
    });
    const errors = form.formState.errors;
    const submit = form.handleSubmit((v) => {
      if (!item && !v.farm_center_id) {
        form.setError("farm_center_id", { message: "Elija un centro." });
        return;
      }
      const body = item ? { code: v.code } : { farm_center_id: Number(v.farm_center_id), code: v.code };
      return submitWithApiErrors(form.setError, ["farm_center_id", "code"], () => onSubmit(body));
    });
    return (
      <form id={formId} noValidate className="space-y-4" onSubmit={submit}>
        {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
        <fieldset disabled={readOnly} className="space-y-4">
          {item ? (
            <p className="text-sm text-muted">
              Centro:{" "}
              <span className="font-semibold text-navy">
                {item.farm_center_code} · {item.farm_center_name}
              </span>
            </p>
          ) : (
            <Select label="Centro" required error={errors.farm_center_id?.message} {...form.register("farm_center_id")}>
              {centers.length === 0 && <option value="">Primero cree un centro</option>}
              {centers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.name}
                </option>
              ))}
            </Select>
          )}
          <Input label="Código de jaula" required autoCapitalize="characters" className="num" error={errors.code?.message} {...form.register("code")} />
        </fieldset>
      </form>
    );
  };
}

export function makeCagesDefinition(centers: Ref[]): MaintainerDefinition<Cage> {
  return {
    resource: "cages",
    title: "Jaulas",
    singular: "jaula",
    newLabel: "Nueva jaula",
    viewPermission: "masters.view",
    editPermission: "farms.edit",
    defaultSort: "code",
    searchPlaceholder: "Buscar jaula",
    filters: [
      { name: "farm_center_id", label: "Centro", options: centers.map((c) => ({ value: String(c.id), label: `${c.code} · ${c.name}` })) },
    ],
    columns: [
      { key: "center", header: "Centro", sortKey: "farm_center_id", render: (c) => `${c.farm_center_code} · ${c.farm_center_name}` },
      { key: "code", header: "Jaula", sortKey: "code", render: (c) => <span className="num">{c.code}</span> },
      { key: "status", header: "Estado", render: (c) => <StatusBadge active={c.is_active} /> },
    ],
    card: (c) => ({ title: <span className="num">{c.code}</span>, subtitle: `${c.farm_center_code} · ${c.farm_center_name}` }),
    rowLabel: (c) => `Jaula ${c.code} (${c.farm_center_code})`,
    Form: makeCageForm(centers),
    fieldLabels: { code: "Código", farm_center_id: "Centro", is_active: "Activa" },
  };
}

// --- Jaulas de acopio --------------------------------------------------------------------

const holdingSchema = z.object({ code: required(20), capacity_fish: z.string().regex(/^\d{1,8}$/, "Número entero de peces.") });
type HoldingValues = z.infer<typeof holdingSchema>;

function makeHoldingCageForm(plant: Ref | null) {
  return function HoldingCageForm({ item, formId, onSubmit, readOnly }: FormProps<HoldingCage>) {
    const form = useForm<HoldingValues>({
      resolver: zodResolver(holdingSchema),
      defaultValues: { code: item?.code ?? "", capacity_fish: item ? String(item.capacity_fish) : "" },
    });
    const errors = form.formState.errors;
    const submit = form.handleSubmit((v) => {
      const capacity = Number(v.capacity_fish);
      if (capacity <= 0) {
        form.setError("capacity_fish", { message: "Debe ser mayor que 0." });
        return;
      }
      const body = { ...(item ? {} : { plant_id: plant?.id }), code: v.code, capacity_fish: capacity };
      return submitWithApiErrors(form.setError, ["code", "capacity_fish"], () => onSubmit(body));
    });
    return (
      <form id={formId} noValidate className="space-y-4" onSubmit={submit}>
        {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
        <p className="text-sm text-muted">
          Planta: <span className="font-semibold text-navy">{plant?.name ?? "—"}</span>
        </p>
        <fieldset disabled={readOnly} className="space-y-4">
          <Input label="Código" required autoCapitalize="characters" className="num" error={errors.code?.message} {...form.register("code")} />
          <NumberInput
            label="Capacidad (peces)"
            required
            decimals={false}
            hint="Los peces asignados a esta jaula en un mismo turno no pueden superarla."
            error={errors.capacity_fish?.message}
            {...form.register("capacity_fish")}
          />
        </fieldset>
      </form>
    );
  };
}

export function makeHoldingCagesDefinition(plant: Ref | null): MaintainerDefinition<HoldingCage> {
  return {
    resource: "holding-cages",
    title: "Jaulas de acopio",
    singular: "jaula de acopio",
    newLabel: "Nuevo acopio",
    viewPermission: "masters.view",
    editPermission: "farms.edit",
    defaultSort: "code",
    searchPlaceholder: "Buscar acopio",
    columns: [
      { key: "code", header: "Acopio", sortKey: "code", render: (h) => <span className="num">{h.code}</span> },
      { key: "capacity", header: "Capacidad (peces)", sortKey: "capacity_fish", numeric: true, render: (h) => formatNumber(h.capacity_fish) },
      { key: "status", header: "Estado", render: (h) => <StatusBadge active={h.is_active} /> },
    ],
    card: (h) => ({ title: <span className="num">{h.code}</span>, subtitle: `${formatNumber(h.capacity_fish)} peces` }),
    rowLabel: (h) => `Acopio ${h.code}`,
    Form: makeHoldingCageForm(plant),
    fieldLabels: { code: "Código", capacity_fish: "Capacidad (peces)", is_active: "Activo" },
  };
}
