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

const schema = z.object({
  username: z.string().trim().min(1, "Ingrese su usuario."),
  password: z.string().min(1, "Ingrese su contraseña."),
});
type Values = z.infer<typeof schema>;

function LoginForm() {
  const auth = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { username: "", password: "" } });

  useEffect(() => {
    if (auth.status === "authenticated") {
      router.replace(auth.me.must_change_password ? `/change-password?next=${encodeURIComponent(next)}` : next);
    }
  }, [auth, next, router]);

  const onSubmit = form.handleSubmit(async ({ username, password }) => {
    setError(null);
    try {
      await auth.login(username, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
      form.resetField("password");
      form.setFocus("password");
    }
  });

  if (auth.status !== "anonymous") {
    return (
      <div className="flex justify-center py-10 text-teal">
        <Spinner className="size-8" />
      </div>
    );
  }

  return (
    <Card className="p-5">
      <h1 className="mb-4 text-lg font-semibold text-navy">Ingresar</h1>
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        {error && <Alert tone="alert">{error}</Alert>}
        <Input
          label="Usuario"
          autoComplete="username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          error={form.formState.errors.username?.message}
          {...form.register("username")}
        />
        <Input
          label="Contraseña"
          type="password"
          autoComplete="current-password"
          error={form.formState.errors.password?.message}
          {...form.register("password")}
        />
        <Button type="submit" loading={form.formState.isSubmitting} className="mt-2 w-full">
          Ingresar
        </Button>
        <p className="text-center text-xs text-muted">
          ¿Olvidó su contraseña? El administrador puede restablecerla.
        </p>
      </form>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
