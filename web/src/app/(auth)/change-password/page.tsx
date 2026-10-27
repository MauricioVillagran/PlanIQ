"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, Spinner } from "@/components/ui/feedback";
import { Input } from "@/components/ui/form";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import { safeNext } from "@/lib/auth/redirect";

// La política vigente la valida la API (largo mínimo configurable); aquí solo lo evidente.
const schema = z
  .object({
    current_password: z.string().min(1, "Ingrese su contraseña actual."),
    new_password: z.string().min(1, "Ingrese la nueva contraseña."),
    confirm: z.string().min(1, "Repita la nueva contraseña."),
  })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Las contraseñas no coinciden." });
type Values = z.infer<typeof schema>;

function ChangePasswordForm() {
  const auth = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });

  useEffect(() => {
    if (auth.status === "anonymous") router.replace("/login");
  }, [auth.status, router]);

  const onSubmit = form.handleSubmit(async ({ current_password, new_password }) => {
    setError(null);
    try {
      await auth.changePassword(current_password, new_password);
      router.replace(next);
    } catch (err) {
      if (!(err instanceof ApiError)) return setError("No se pudo conectar con el servidor.");
      // Los errores por campo de la API se muestran bajo cada input.
      for (const fieldError of err.fieldErrors) {
        if (fieldError.field === "current_password" || fieldError.field === "new_password") {
          form.setError(fieldError.field, { message: fieldError.message });
        }
      }
      if (!err.fieldErrors.length) setError(err.message);
    }
  });

  if (auth.status !== "authenticated") {
    return (
      <div className="flex justify-center py-10 text-teal">
        <Spinner className="size-8" />
      </div>
    );
  }

  const forced = auth.me.must_change_password;
  return (
    <Card className="p-5">
      <h1 className="mb-1 text-lg font-semibold text-navy">Cambiar contraseña</h1>
      <p className="mb-4 text-sm text-muted">
        {forced
          ? "Por seguridad debe definir una contraseña propia antes de continuar."
          : `Usuario ${auth.me.username}.`}
      </p>
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        {error && <Alert tone="alert">{error}</Alert>}
        <input type="text" autoComplete="username" value={auth.me.username} readOnly hidden />
        <Input
          label={forced ? "Contraseña temporal" : "Contraseña actual"}
          type="password"
          autoComplete="current-password"
          error={form.formState.errors.current_password?.message}
          {...form.register("current_password")}
        />
        <Input
          label="Nueva contraseña"
          type="password"
          autoComplete="new-password"
          hint="Al menos 10 caracteres, distinta de su usuario y de la actual."
          error={form.formState.errors.new_password?.message}
          {...form.register("new_password")}
        />
        <Input
          label="Repetir nueva contraseña"
          type="password"
          autoComplete="new-password"
          error={form.formState.errors.confirm?.message}
          {...form.register("confirm")}
        />
        <Button type="submit" loading={form.formState.isSubmitting} className="mt-2 w-full">
          Guardar contraseña
        </Button>
        <Button variant="ghost" onClick={() => auth.logout()} className="w-full">
          Salir
        </Button>
      </form>
    </Card>
  );
}

export default function ChangePasswordPage() {
  return (
    <Suspense>
      <ChangePasswordForm />
    </Suspense>
  );
}
