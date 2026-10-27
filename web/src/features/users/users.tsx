"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Copy, KeyRound, LockOpen } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { submitWithApiErrors } from "@/components/maintainer/form-errors";
import { StatusBadge } from "@/components/maintainer/maintainer-page";
import type { ExtraActionsProps, FormProps, MaintainerDefinition, Page } from "@/components/maintainer/types";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Alert, Badge, Skeleton } from "@/components/ui/feedback";
import { Checkbox, Input } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { ApiError, request, type Schemas } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";

export type User = Schemas["UserOut"];
type Ref = { id: number; code: string; name: string };

/** Muestra una clave temporal una sola vez, con botón para copiarla. */
export function TemporaryPasswordDialog({
  username,
  password,
  onClose,
}: {
  username: string;
  password: string | null;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <Dialog
      open={!!password}
      title="Clave temporal"
      actions={
        <>
          <Button
            onClick={async () => {
              await navigator.clipboard?.writeText(password ?? "");
              setCopied(true);
            }}
          >
            <Copy aria-hidden className="size-4" />
            {copied ? "Copiada" : "Copiar"}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Listo
          </Button>
        </>
      }
    >
      <p>
        Entregue esta clave a <strong>{username}</strong>. Deberá cambiarla en su primer ingreso.
      </p>
      <p className="num select-all rounded-lg bg-bg px-3 py-3 text-center text-xl tracking-wider">{password}</p>
      <p className="text-coral">No se volverá a mostrar.</p>
    </Dialog>
  );
}

function useOptions(resource: "roles" | "plants") {
  return useQuery({
    queryKey: [resource, "options"],
    queryFn: async () =>
      (await request<Page<Ref>>("GET", `/api/v1/${resource}`, { query: { status: "active", page_size: 200, sort: "name" } }))
        .items,
    staleTime: 60_000,
  });
}

const schema = z.object({
  username: z.string().trim(),
  email: z.string().trim().regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, "Correo inválido."),
  full_name: z.string().trim().min(1, "Campo obligatorio.").max(150),
  role_ids: z.array(z.string()).min(1, "Asigne al menos un rol."),
  plant_ids: z.array(z.string()),
});
type Values = z.infer<typeof schema>;
const FIELDS = ["username", "email", "full_name", "role_ids", "plant_ids"] as const;

function UserForm({ item, formId, onSubmit, readOnly }: FormProps<User>) {
  const roles = useOptions("roles");
  const plants = useOptions("plants");
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: item?.username ?? "",
      email: item?.email ?? "",
      full_name: item?.full_name ?? "",
      role_ids: item?.roles.map((r) => String(r.id)) ?? [],
      plant_ids: item?.plants.map((p) => String(p.id)) ?? [],
    },
  });
  const errors = form.formState.errors;

  const submit = form.handleSubmit((values) => {
    if (!item && !/^[a-z0-9._-]{3,50}$/i.test(values.username)) {
      form.setError("username", { message: "Entre 3 y 50 caracteres: letras, números, punto, guion o guion bajo." });
      return;
    }
    const body = {
      ...(item ? {} : { username: values.username }),
      email: values.email,
      full_name: values.full_name,
      role_ids: values.role_ids.map(Number),
      plant_ids: values.plant_ids.map(Number),
    };
    return submitWithApiErrors(form.setError, FIELDS, () => onSubmit(body));
  });

  return (
    <form id={formId} noValidate className="space-y-4" onSubmit={submit}>
      {errors.root?.server && <Alert tone="alert">{errors.root.server.message}</Alert>}
      <fieldset disabled={readOnly} className="space-y-4">
        {item ? (
          <p className="text-sm text-muted">
            Usuario: <span className="font-semibold text-navy">{item.username}</span>
          </p>
        ) : (
          <Input
            label="Usuario"
            required
            autoCapitalize="none"
            spellCheck={false}
            hint="Se guarda en minúsculas y no cambia después."
            error={errors.username?.message}
            {...form.register("username")}
          />
        )}
        <Input label="Nombre completo" required error={errors.full_name?.message} {...form.register("full_name")} />
        <Input label="Correo" type="email" required autoCapitalize="none" error={errors.email?.message} {...form.register("email")} />

        <fieldset>
          <legend className="mb-1 text-sm font-medium text-navy">
            Roles <span className="text-coral">*</span>
          </legend>
          {roles.isPending ? (
            <Skeleton className="h-24" />
          ) : (
            <div className="rounded-lg border border-gray">
              {roles.data?.map((r) => (
                <Checkbox key={r.id} label={r.name} value={String(r.id)} {...form.register("role_ids")} />
              ))}
            </div>
          )}
          {errors.role_ids && <p className="mt-1 text-sm text-coral">{errors.role_ids.message}</p>}
        </fieldset>

        <fieldset>
          <legend className="mb-1 text-sm font-medium text-navy">Plantas con acceso</legend>
          <p className="mb-1 text-xs text-muted">No aplica a roles con acceso a todas las plantas.</p>
          {plants.isPending ? (
            <Skeleton className="h-16" />
          ) : plants.data?.length ? (
            <div className="rounded-lg border border-gray">
              {plants.data.map((p) => (
                <Checkbox key={p.id} label={`${p.code} · ${p.name}`} value={String(p.id)} {...form.register("plant_ids")} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">Aún no hay plantas creadas.</p>
          )}
          {errors.plant_ids && <p className="mt-1 text-sm text-coral">{errors.plant_ids.message}</p>}
        </fieldset>
      </fieldset>
    </form>
  );
}

function UserActions({ item, onChanged }: ExtraActionsProps<User>) {
  const toast = useToast();
  const [confirmReset, setConfirmReset] = useState(false);
  const [temporary, setTemporary] = useState<string | null>(null);
  const onError = (error: unknown) =>
    toast.error(error instanceof ApiError ? error.message : "No se pudo completar la operación.");

  const reset = useMutation({
    mutationFn: () => request<{ temporary_password: string }>("POST", `/api/v1/users/${item.id}/reset-password`),
    onSuccess: async (result) => {
      setConfirmReset(false);
      setTemporary(result.temporary_password);
      onChanged(await request<User>("GET", `/api/v1/users/${item.id}`));
    },
    onError,
  });
  const unlock = useMutation({
    mutationFn: () => request<User>("POST", `/api/v1/users/${item.id}/unlock`),
    onSuccess: (user) => {
      toast.success("Usuario desbloqueado.");
      onChanged(user);
    },
    onError,
  });

  return (
    <div className="space-y-2 border-t border-gray pt-4">
      {item.locked && (
        <Alert tone="alert" title="Cuenta bloqueada por intentos fallidos">
          <Button size="sm" variant="secondary" className="mt-1" loading={unlock.isPending} onClick={() => unlock.mutate()}>
            <LockOpen aria-hidden className="size-4" />
            Desbloquear
          </Button>
        </Alert>
      )}
      {confirmReset ? (
        <div className="flex flex-col gap-2 rounded-lg bg-bg p-3 sm:flex-row sm:items-center">
          <p className="flex-1 text-sm text-navy">Se generará una clave temporal y se cerrarán sus sesiones.</p>
          <Button size="sm" loading={reset.isPending} onClick={() => reset.mutate()}>
            Confirmar
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirmReset(false)}>
            Volver
          </Button>
        </div>
      ) : (
        <Button variant="ghost" onClick={() => setConfirmReset(true)}>
          <KeyRound aria-hidden className="size-4" />
          Restablecer contraseña
        </Button>
      )}
      <TemporaryPasswordDialog username={item.username} password={temporary} onClose={() => setTemporary(null)} />
    </div>
  );
}

function statusBadge(u: User) {
  if (u.locked) return <Badge tone="alert">Bloqueado</Badge>;
  return <StatusBadge active={u.is_active} />;
}

export function makeUsersDefinition(onCreated: (user: User) => void): MaintainerDefinition<User> {
  return {
    resource: "users",
    title: "Usuarios",
    singular: "usuario",
    newLabel: "Nuevo usuario",
    viewPermission: "users.admin",
    editPermission: "users.admin",
    defaultSort: "username",
    searchPlaceholder: "Buscar por usuario, nombre o correo",
    columns: [
      { key: "username", header: "Usuario", sortKey: "username", render: (u) => <span className="num">{u.username}</span> },
      { key: "name", header: "Nombre", sortKey: "full_name", render: (u) => u.full_name },
      { key: "roles", header: "Roles", render: (u) => u.roles.map((r) => r.name).join(", ") || "—" },
      { key: "plants", header: "Plantas", render: (u) => u.plants.map((p) => p.code).join(", ") || "—" },
      {
        key: "last_login",
        header: "Último ingreso",
        sortKey: "last_login_at",
        render: (u) => <span className="num">{formatDateTime(u.last_login_at)}</span>,
      },
      { key: "status", header: "Estado", render: statusBadge },
    ],
    card: (u) => ({
      title: u.full_name,
      subtitle: (
        <>
          <span className="num">{u.username}</span> · {u.roles.map((r) => r.name).join(", ") || "Sin rol"}
        </>
      ),
      meta: u.locked ? <Badge tone="alert">Bloqueado</Badge> : u.plants.map((p) => p.code).join(", ") || undefined,
    }),
    rowLabel: (u) => u.full_name,
    Form: UserForm,
    ExtraActions: UserActions,
    onCreated,
    fieldLabels: {
      username: "Usuario",
      email: "Correo",
      full_name: "Nombre",
      roles: "Roles",
      plants: "Plantas",
      password_hash: "Contraseña",
      must_change_password: "Debe cambiar contraseña",
      locked_at: "Bloqueo",
      is_active: "Activo",
    },
  };
}
