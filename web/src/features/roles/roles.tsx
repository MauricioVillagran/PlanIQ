"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { submitWithApiErrors } from "@/components/maintainer/form-errors";
import { StatusBadge } from "@/components/maintainer/maintainer-page";
import type { FormProps, MaintainerDefinition } from "@/components/maintainer/types";
import { Alert, Badge, Skeleton } from "@/components/ui/feedback";
import { Checkbox, Input } from "@/components/ui/form";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";

export type Role = Schemas["RoleOut"];
type Permission = Schemas["PermissionOut"];

const MODULES: Record<string, string> = {
  admin: "Administración",
  masters: "Maestros",
  plan: "Plan diario",
  rules: "Reglas de calidad",
};

function usePermissions() {
  return useQuery({
    queryKey: ["permissions"],
    queryFn: async () => unwrap(await api.GET("/api/v1/permissions")),
    staleTime: 5 * 60_000,
  });
}

function groupByModule(permissions: Permission[]): Array<[string, Permission[]]> {
  const groups = new Map<string, Permission[]>();
  for (const p of permissions) groups.set(p.module, [...(groups.get(p.module) ?? []), p]);
  return [...groups.entries()];
}

const schema = z.object({
  code: z.string().trim(),
  name: z.string().trim().min(1, "Campo obligatorio.").max(100),
  description: z.string().trim().max(400),
  permissions: z.array(z.string()),
});
type Values = z.infer<typeof schema>;
const FIELDS = ["code", "name", "description", "permissions"] as const;

function RoleForm({ item, formId, onSubmit, readOnly }: FormProps<Role>) {
  const permissions = usePermissions();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      code: item?.code ?? "",
      name: item?.name ?? "",
      description: item?.description ?? "",
      permissions: item?.permissions ?? [],
    },
  });
  const errors = form.formState.errors;

  const submit = form.handleSubmit((values) => {
    if (!item && !/^[a-z][a-z0-9_]{1,49}$/.test(values.code)) {
      form.setError("code", { message: "Minúsculas, números y guion bajo; empieza con letra." });
      return;
    }
    const body = {
      ...(item ? {} : { code: values.code }),
      name: values.name,
      description: values.description || null,
      permissions: values.permissions,
    };
    return submitWithApiErrors(form.setError, FIELDS, () => onSubmit(body));
  });

  return (
    <form id={formId} noValidate className="space-y-4" onSubmit={submit}>
      {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
      {item?.is_system && (
        <Alert tone="info">Rol base del sistema: no se desactiva, pero sus permisos se pueden ajustar.</Alert>
      )}
      <fieldset disabled={readOnly} className="space-y-4">
        {item ? (
          <p className="text-sm text-muted">
            Código: <span className="num font-semibold text-navy">{item.code}</span>
          </p>
        ) : (
          <Input
            label="Código"
            required
            autoCapitalize="none"
            spellCheck={false}
            className="num"
            placeholder="supervisor_frigorifico"
            error={errors.code?.message}
            {...form.register("code")}
          />
        )}
        <Input label="Nombre" required error={errors.name?.message} {...form.register("name")} />
        <Input label="Descripción" error={errors.description?.message} {...form.register("description")} />

        <div>
          <p className="mb-1 text-sm font-medium text-navy">Permisos</p>
          <p className="mb-2 text-xs text-muted">Los cambios rigen desde la siguiente acción de cada usuario.</p>
          {permissions.isPending ? (
            <Skeleton className="h-48" />
          ) : (
            <div className="space-y-3">
              {groupByModule(permissions.data ?? []).map(([module, items]) => (
                <fieldset key={module} className="rounded-lg border border-gray">
                  <legend className="ml-2 px-1 text-xs font-semibold uppercase tracking-wider text-muted">
                    {MODULES[module] ?? module}
                  </legend>
                  {items.map((p) => (
                    <Checkbox
                      key={p.code}
                      value={p.code}
                      label={p.name}
                      description={p.description ?? p.code}
                      {...form.register("permissions")}
                    />
                  ))}
                </fieldset>
              ))}
            </div>
          )}
          {errors.permissions && <p className="mt-1 text-sm text-coral">{errors.permissions.message}</p>}
        </div>
      </fieldset>
    </form>
  );
}

export const rolesDefinition: MaintainerDefinition<Role> = {
  resource: "roles",
  title: "Roles y permisos",
  singular: "rol",
  newLabel: "Nuevo rol",
  viewPermission: "users.admin",
  editPermission: "users.admin",
  defaultSort: "name",
  searchPlaceholder: "Buscar rol",
  columns: [
    { key: "name", header: "Rol", sortKey: "name", render: (r) => r.name },
    { key: "code", header: "Código", sortKey: "code", render: (r) => <span className="num">{r.code}</span> },
    { key: "permissions", header: "Permisos", numeric: true, render: (r) => formatNumber(r.permissions.length) },
    { key: "system", header: "Tipo", render: (r) => (r.is_system ? <Badge tone="info">Base</Badge> : "Propio") },
    { key: "status", header: "Estado", render: (r) => <StatusBadge active={r.is_active} /> },
  ],
  card: (r) => ({
    title: r.name,
    subtitle: (
      <>
        <span className="num">{r.code}</span> · {formatNumber(r.permissions.length)} permisos
        {r.is_system && " · Base"}
      </>
    ),
  }),
  rowLabel: (r) => r.name,
  Form: RoleForm,
  canToggleActive: (r) => !r.is_system,
  fieldLabels: { name: "Nombre", description: "Descripción", permissions: "Permisos", code: "Código", is_active: "Activo" },
};
