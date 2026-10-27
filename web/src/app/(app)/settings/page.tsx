"use client";

import { Building2, ChevronRight, Clock, ShieldCheck, SlidersHorizontal, Users, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/page-header";
import { useAppContext } from "@/lib/app-context";
import { useAuth } from "@/lib/auth/auth-context";

type Entry = { href: string; title: string; description: string; icon: LucideIcon; permission: string };

/** Mantenedores agrupados como en la sección 13; cada fase agrega sus grupos (Cultivo, Producción...). */
const GROUPS: Array<{ title: string; entries: Entry[] }> = [
  {
    title: "Administración",
    entries: [
      { href: "/settings/users", title: "Usuarios", description: "Cuentas, roles, plantas y contraseñas", icon: Users, permission: "users.admin" },
      { href: "/settings/roles", title: "Roles y permisos", description: "Matriz de permisos por rol", icon: ShieldCheck, permission: "users.admin" },
      { href: "/settings/plants", title: "Plantas", description: "Plantas propias y maquilas", icon: Building2, permission: "masters.view" },
      { href: "/settings/shifts", title: "Turnos", description: "Turnos por planta y cobertura del día", icon: Clock, permission: "masters.view" },
      { href: "/settings/parameters", title: "Parámetros", description: "Valores globales y por planta con vigencia", icon: SlidersHorizontal, permission: "masters.view" },
    ],
  },
];

export default function SettingsPage() {
  const { can } = useAuth();
  const { href } = useAppContext();
  return (
    <div className="mx-auto max-w-4xl animate-fade-up">
      <PageHeader title="Configuración" />
      {GROUPS.map((group) => {
        const entries = group.entries.filter((e) => can(e.permission));
        if (!entries.length) return null;
        return (
          <section key={group.title} className="mb-6">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">{group.title}</h2>
            <ul className="grid gap-2 sm:grid-cols-2">
              {entries.map(({ href: path, title, description, icon: Icon }) => (
                <li key={path}>
                  <Link
                    href={href(path)}
                    className="flex min-h-16 items-center gap-3 rounded-card bg-card p-4 shadow-card hover:ring-2 hover:ring-teal/30"
                  >
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-teal-soft text-teal">
                      <Icon aria-hidden className="size-5" />
                    </span>
                    <span className="flex-1">
                      <span className="block font-semibold text-navy">{title}</span>
                      <span className="block text-sm text-muted">{description}</span>
                    </span>
                    <ChevronRight aria-hidden className="size-5 text-muted" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
