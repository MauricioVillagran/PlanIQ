"use client";

import { ShieldX } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth/auth-context";

/** Muestra el contenido solo con el permiso; la API lo valida igual en cada llamada. */
export function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const { can } = useAuth();
  if (can(permission)) return <>{children}</>;
  return (
    <Card className="mx-auto max-w-lg">
      <EmptyState icon={ShieldX} title="Sin acceso" description="Su rol no tiene permiso para ver esta sección." />
    </Card>
  );
}
