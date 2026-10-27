"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, type ReactNode } from "react";

import { Brand } from "@/components/brand";
import { AppShell } from "@/components/layout/app-shell";
import { Spinner } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth/auth-context";

function FullScreenLoader() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 text-teal">
      <Brand />
      <Spinner className="size-7" />
    </div>
  );
}

/** Protege las rutas de la aplicación: sin sesión va a /login; con clave temporal, a cambiarla. */
function Guard({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const here = search ? `${pathname}?${search}` : pathname;

  const blocked = auth.status !== "authenticated" || auth.me.must_change_password;

  useEffect(() => {
    if (auth.status === "anonymous") router.replace(`/login?next=${encodeURIComponent(here)}`);
    else if (auth.status === "authenticated" && auth.me.must_change_password) {
      router.replace(`/change-password?next=${encodeURIComponent(here)}`);
    }
  }, [auth, here, router]);

  if (blocked) return <FullScreenLoader />;
  return <AppShell>{children}</AppShell>;
}

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Guard>{children}</Guard>
    </Suspense>
  );
}
