"use client";

import { CalendarDays, Factory } from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge, EmptyState, Skeleton } from "@/components/ui/feedback";
import { PlanDayCard, usePlanDays } from "@/features/plan/week-page";
import { useAppContext } from "@/lib/app-context";
import { useAuth } from "@/lib/auth/auth-context";
import { weekdayLabel } from "@/lib/dates";
import { formatDate } from "@/lib/format";

function PlanDays({ plantId, date }: { plantId: number; date: string }) {
  const { href } = useAppContext();
  const days = usePlanDays(plantId, date, 2);
  const linkFor = (day: string) => {
    const url = new URL(href("/plan"), "http://x");
    url.searchParams.set("date", day);
    return `${url.pathname}?${url.searchParams.toString()}`;
  };
  if (days.isPending) return <Skeleton className="m-4 h-32" />;
  return (
    <ul className="space-y-2 p-3 sm:p-4">
      {days.data?.map((day) => (
        <li key={day.productive_date}>
          <PlanDayCard day={day} href={linkFor(day.productive_date)} />
        </li>
      ))}
    </ul>
  );
}

/** Inicio: el plan de hoy y mañana de la planta del contexto, y el acceso del usuario. */
export default function HomePage() {
  const { me, can } = useAuth();
  const { plant, date } = useAppContext();
  if (!me) return null;

  const firstName = me.full_name.split(" ")[0];
  return (
    <div className="mx-auto max-w-5xl animate-fade-up">
      <PageHeader
        title={`Hola, ${firstName}`}
        subtitle={`${weekdayLabel(date)} ${formatDate(date)}${plant ? ` · ${plant.name}` : ""}`}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Plan de cosecha" description="Hoy y mañana, con sus alertas" />
          {can("plan.view") && plant ? (
            <PlanDays plantId={plant.id} date={date} />
          ) : (
            <EmptyState
              icon={CalendarDays}
              title={plant ? "Sin acceso al plan" : "Elija una planta"}
              description="El plan de cosecha se ve con el permiso de plan y una planta asignada."
            />
          )}
        </Card>

        <Card>
          <CardHeader title="Su acceso" />
          <div className="space-y-4 px-4 py-4 sm:px-5">
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">Roles</p>
              <div className="flex flex-wrap gap-2">
                {me.roles.length ? (
                  me.roles.map((r) => (
                    <Badge key={r.code} tone="ok">
                      {r.name}
                    </Badge>
                  ))
                ) : (
                  <Badge tone="alert">Sin rol asignado</Badge>
                )}
              </div>
            </div>
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">
                Plantas {me.all_plants && "(todas)"}
              </p>
              {me.plants.length ? (
                <ul className="space-y-1">
                  {me.plants.map((p) => (
                    <li key={p.id} className="flex items-center gap-2 text-sm">
                      <Factory aria-hidden className="size-4 text-teal" />
                      <span className="num text-muted">{p.code}</span>
                      {p.name}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">Aún no hay plantas creadas o asignadas.</p>
              )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
