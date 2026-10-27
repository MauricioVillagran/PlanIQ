"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { submitWithApiErrors } from "@/components/maintainer/form-errors";
import { StatusBadge } from "@/components/maintainer/maintainer-page";
import type { FormProps, MaintainerDefinition } from "@/components/maintainer/types";
import { Alert } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/form";
import type { Schemas } from "@/lib/api/client";

export type Plant = Schemas["PlantOut"];

export const PLANT_TYPES: Record<string, string> = { own: "Propia", contract: "Maquila" };
const TIMEZONES = ["America/Santiago", "America/Punta_Arenas", "Pacific/Easter"];

const schema = z.object({
  code: z.string().trim().min(1, "Campo obligatorio.").max(20, "Máximo 20 caracteres."),
  name: z.string().trim().min(1, "Campo obligatorio.").max(150, "Máximo 150 caracteres."),
  plant_type: z.enum(["own", "contract"]),
  location: z.string().trim().max(200, "Máximo 200 caracteres."),
  timezone: z.string().trim().min(1, "Campo obligatorio."),
});
type Values = z.infer<typeof schema>;
const FIELDS = ["code", "name", "plant_type", "location", "timezone"] as const;

function PlantForm({ item, formId, onSubmit, readOnly }: FormProps<Plant>) {
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      code: item?.code ?? "",
      name: item?.name ?? "",
      plant_type: (item?.plant_type as Values["plant_type"]) ?? "own",
      location: item?.location ?? "",
      timezone: item?.timezone ?? "America/Santiago",
    },
  });
  const errors = form.formState.errors;

  return (
    <form
      id={formId}
      noValidate
      className="space-y-4"
      onSubmit={form.handleSubmit((values) =>
        submitWithApiErrors(form.setError, FIELDS, () => onSubmit({ ...values, location: values.location || null })),
      )}
    >
      {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
      <fieldset disabled={readOnly} className="space-y-4">
        <Input label="Código" required autoCapitalize="characters" error={errors.code?.message} {...form.register("code")} />
        <Input label="Nombre" required error={errors.name?.message} {...form.register("name")} />
        <Select label="Tipo" required error={errors.plant_type?.message} {...form.register("plant_type")}>
          <option value="own">Propia</option>
          <option value="contract">Maquila</option>
        </Select>
        <Input label="Ubicación" error={errors.location?.message} {...form.register("location")} />
        <Input
          label="Zona horaria"
          required
          list="plant-timezones"
          hint="Formato IANA. Las fechas productivas de la planta se calculan en esta zona."
          error={errors.timezone?.message}
          {...form.register("timezone")}
        />
        <datalist id="plant-timezones">
          {TIMEZONES.map((tz) => (
            <option key={tz} value={tz} />
          ))}
        </datalist>
      </fieldset>
    </form>
  );
}

export const plantsDefinition: MaintainerDefinition<Plant> = {
  resource: "plants",
  title: "Plantas",
  singular: "planta",
  newLabel: "Nueva planta",
  viewPermission: "masters.view",
  editPermission: "masters.edit",
  defaultSort: "name",
  searchPlaceholder: "Buscar por código, nombre o ubicación",
  filters: [{ name: "plant_type", label: "Tipo", options: [{ value: "own", label: "Propia" }, { value: "contract", label: "Maquila" }] }],
  columns: [
    { key: "code", header: "Código", sortKey: "code", render: (p) => <span className="num">{p.code}</span> },
    { key: "name", header: "Nombre", sortKey: "name", render: (p) => p.name },
    { key: "type", header: "Tipo", sortKey: "plant_type", render: (p) => PLANT_TYPES[p.plant_type] ?? p.plant_type },
    { key: "location", header: "Ubicación", render: (p) => p.location ?? "—" },
    { key: "timezone", header: "Zona horaria", render: (p) => p.timezone },
    { key: "status", header: "Estado", render: (p) => <StatusBadge active={p.is_active} /> },
  ],
  card: (p) => ({
    title: p.name,
    subtitle: (
      <>
        <span className="num">{p.code}</span> · {PLANT_TYPES[p.plant_type] ?? p.plant_type}
      </>
    ),
    meta: p.location,
  }),
  rowLabel: (p) => `${p.code} · ${p.name}`,
  Form: PlantForm,
  fieldLabels: {
    code: "Código",
    name: "Nombre",
    plant_type: "Tipo",
    location: "Ubicación",
    timezone: "Zona horaria",
    is_active: "Activa",
  },
};
