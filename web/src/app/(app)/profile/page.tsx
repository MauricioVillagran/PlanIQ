"use client";

import { KeyRound, LogOut } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth/auth-context";

export default function ProfilePage() {
  const { me, logout } = useAuth();
  if (!me) return null;

  const rows: Array<[string, string]> = [
    ["Nombre", me.full_name],
    ["Usuario", me.username],
    ["Correo", me.email],
  ];
  return (
    <div className="mx-auto max-w-2xl animate-fade-up">
      <PageHeader title="Perfil" />
      <Card>
        <CardHeader title="Datos de la cuenta" />
        <dl className="divide-y divide-gray/70 px-4 sm:px-5">
          {rows.map(([label, value]) => (
            <div key={label} className="flex flex-col gap-0.5 py-3 sm:flex-row sm:justify-between">
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="break-all text-sm font-medium text-navy">{value}</dd>
            </div>
          ))}
          <div className="flex flex-col gap-2 py-3 sm:flex-row sm:justify-between">
            <dt className="text-sm text-muted">Roles</dt>
            <dd className="flex flex-wrap gap-2">
              {me.roles.map((r) => (
                <Badge key={r.code} tone="ok">
                  {r.name}
                </Badge>
              ))}
            </dd>
          </div>
        </dl>
      </Card>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Link
          href="/change-password?next=/profile"
          className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-gray bg-card px-4 text-sm font-semibold text-navy hover:border-teal hover:text-teal"
        >
          <KeyRound aria-hidden className="size-4" />
          Cambiar contraseña
        </Link>
        <Button variant="ghost" onClick={() => logout()}>
          <LogOut aria-hidden className="size-4" />
          Salir
        </Button>
      </div>
    </div>
  );
}
