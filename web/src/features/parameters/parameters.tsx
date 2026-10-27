"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { submitWithApiErrors } from "@/components/maintainer/form-errors";
import { StatusBadge } from "@/components/maintainer/maintainer-page";
import type { FormProps, MaintainerDefinition } from "@/components/maintainer/types";
import { Alert, Badge } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/form";
import type { Schemas } from "@/lib/api/client";
import { decimalToInput, formatDate, parseDecimalInput } from "@/lib/format";

export type Parameter = Schemas["ParameterOut"];
type PlantRef = { id: number; code: string; name: string };

const TYPES: Record<string, string> = { int: "Entero", decimal: "Decimal", bool: "Sí / No", text: "Texto" };

/** Valor para mostrar: coma decimal y Sí/No. */
export function showParameterValue(p: Pick<Parameter, "value" | "value_type" | "unit">): string {
  const value = p.value_type === "bool" ? (p.value === "true" ? "Sí" : "No") : p.value_type === "decimal" ? decimalToInput(p.value) : p.value;
  return p.unit ? `${value} ${p.unit}` : value;
}

const KEY_PATTERN = /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$/;

// Clave, alcance y tipo solo se envían al crear; en edición se muestran como texto.
const schema = z.object({
  key: z.string().trim(),
  scope: z.string(),
  value_type: z.enum(["int", "decimal", "bool", "text"]),
  value: z.string().trim().min(1, "Campo obligatorio.").max(400),
  unit: z.string().trim().max(30),
  description: z.string().trim().max(400),
  valid_from: z.string(),
  valid_to: z.string(),
});
type Values = z.infer<typeof schema>;
const FIELDS = ["key", "value_type", "value", "unit", "description", "valid_from", "valid_to"] as const;

function makeParameterForm(plants: PlantRef[], allowGlobal: boolean) {
  return function ParameterForm({ item, formId, onSubmit, readOnly }: FormProps<Parameter>) {
    const form = useForm<Values>({
      resolver: zodResolver(schema),
      defaultValues: {
        key: item?.key ?? "",
        scope: item ? String(item.plant_id ?? "") : allowGlobal ? "" : String(plants[0]?.id ?? ""),
        value_type: (item?.value_type as Values["value_type"]) ?? "decimal",
        value: item ? (item.value_type === "decimal" ? decimalToInput(item.value) : item.value) : "",
        unit: item?.unit ?? "",
        description: item?.description ?? "",
        valid_from: item?.valid_from ?? "",
        valid_to: item?.valid_to ?? "",
      },
    });
    const errors = form.formState.errors;
    const valueType = useWatch({ control: form.control, name: "value_type" });

    const submit = form.handleSubmit((values) => {
      if (!item && !KEY_PATTERN.test(values.key)) {
        form.setError("key", { message: "Minúsculas, números y guion bajo, separados por puntos." });
        return;
      }
      let value: string | null = values.value;
      if (values.value_type === "decimal") {
        value = parseDecimalInput(values.value);
        if (value === null) {
          form.setError("value", { message: "Debe ser un número decimal (use coma para los decimales)." });
          return;
        }
      }
      const common = {
        value,
        unit: values.unit || null,
        description: values.description || null,
        valid_from: values.valid_from || null,
        valid_to: values.valid_to || null,
      };
      const body = item
        ? common
        : { ...common, key: values.key, plant_id: values.scope ? Number(values.scope) : null, value_type: values.value_type };
      return submitWithApiErrors(form.setError, FIELDS, () => onSubmit(body));
    });

    return (
      <form id={formId} noValidate className="space-y-4" onSubmit={submit}>
        {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
        <fieldset disabled={readOnly} className="space-y-4">
          {item ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg bg-bg px-3 py-2 text-sm">
              <dt className="text-muted">Clave</dt>
              <dd className="num break-all text-navy">{item.key}</dd>
              <dt className="text-muted">Alcance</dt>
              <dd className="text-navy">
                {item.plant_id === null ? "Global" : (plants.find((p) => p.id === item.plant_id)?.name ?? item.plant_id)}
              </dd>
              <dt className="text-muted">Tipo</dt>
              <dd className="text-navy">{TYPES[item.value_type] ?? item.value_type}</dd>
            </dl>
          ) : (
            <>
              <Input
                label="Clave"
                required
                placeholder="harvest.avg_weight_kg.max"
                autoCapitalize="none"
                spellCheck={false}
                className="num"
                error={errors.key?.message}
                {...form.register("key")}
              />
              <div className="grid grid-cols-2 gap-3">
                <Select label="Alcance" {...form.register("scope")}>
                  {allowGlobal && <option value="">Global (todas)</option>}
                  {plants.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
                <Select label="Tipo" error={errors.value_type?.message} {...form.register("value_type")}>
                  {Object.entries(TYPES).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </div>
            </>
          )}
          <div className="grid grid-cols-[1fr_7rem] gap-3">
            {valueType === "bool" ? (
              <Select label="Valor" required error={errors.value?.message} {...form.register("value")}>
                <option value="">Elegir…</option>
                <option value="true">Sí</option>
                <option value="false">No</option>
              </Select>
            ) : (
              <Input
                label="Valor"
                required
                inputMode={valueType === "decimal" ? "decimal" : valueType === "int" ? "numeric" : "text"}
                className={valueType === "text" ? undefined : "num text-right"}
                error={errors.value?.message}
                {...form.register("value")}
              />
            )}
            <Input label="Unidad" placeholder="kg" error={errors.unit?.message} {...form.register("unit")} />
          </div>
          <Input label="Descripción" error={errors.description?.message} {...form.register("description")} />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Vigente desde" type="date" className="num" error={errors.valid_from?.message} {...form.register("valid_from")} />
            <Input label="Vigente hasta" type="date" className="num" hint="Excluida; vacío = sin límite" error={errors.valid_to?.message} {...form.register("valid_to")} />
          </div>
        </fieldset>
      </form>
    );
  };
}

function validity(p: Parameter): string {
  if (!p.valid_from && !p.valid_to) return "Siempre";
  if (p.valid_from && !p.valid_to) return `Desde ${formatDate(p.valid_from)}`;
  if (!p.valid_from && p.valid_to) return `Hasta ${formatDate(p.valid_to)}`;
  return `${formatDate(p.valid_from)} a ${formatDate(p.valid_to)}`;
}

export function makeParametersDefinition(plants: PlantRef[], allowGlobal: boolean): MaintainerDefinition<Parameter> {
  const scope = (p: Parameter) =>
    p.plant_id === null ? <Badge tone="info">Global</Badge> : (plants.find((x) => x.id === p.plant_id)?.name ?? `Planta ${p.plant_id}`);
  return {
    resource: "parameters",
    title: "Parámetros",
    singular: "parámetro",
    newLabel: "Nuevo parámetro",
    viewPermission: "masters.view",
    editPermission: "parameters.edit",
    defaultSort: "key",
    searchPlaceholder: "Buscar por clave o descripción",
    filters: [
      {
        name: "plant_id",
        label: "Planta",
        options: plants.map((p) => ({ value: String(p.id), label: p.name })),
      },
    ],
    columns: [
      { key: "key", header: "Clave", sortKey: "key", render: (p) => <span className="num">{p.key}</span> },
      { key: "scope", header: "Alcance", sortKey: "plant_id", render: scope },
      { key: "value", header: "Valor", render: (p) => <span className="num">{showParameterValue(p)}</span> },
      { key: "type", header: "Tipo", render: (p) => TYPES[p.value_type] ?? p.value_type },
      { key: "validity", header: "Vigencia", sortKey: "valid_from", render: validity },
      { key: "status", header: "Estado", render: (p) => <StatusBadge active={p.is_active} /> },
    ],
    card: (p) => ({
      title: <span className="num break-all">{p.key}</span>,
      subtitle: (
        <span className="flex flex-wrap items-center gap-2">
          {scope(p)} · {validity(p)}
        </span>
      ),
      meta: <span className="num">{showParameterValue(p)}</span>,
    }),
    rowLabel: (p) => p.key,
    Form: makeParameterForm(plants, allowGlobal),
    fieldLabels: {
      value: "Valor",
      unit: "Unidad",
      description: "Descripción",
      valid_from: "Vigente desde",
      valid_to: "Vigente hasta",
      key: "Clave",
      plant_id: "Planta",
      value_type: "Tipo",
      is_active: "Activo",
    },
  };
}
