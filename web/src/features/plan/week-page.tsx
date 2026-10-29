"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronRight } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Alert, Badge, EmptyState, Skeleton } from "@/components/ui/feedback";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useAppContext } from "@/lib/app-context";
import { addDays, weekdayLabel } from "@/lib/dates";
import { formatDate, formatNumber } from "@/lib/format";

import { errorMessage } from "./plan-page";

type PlanDay = Schemas["PlanDayOut"];

const STATUS: Record<string, { label: string; tone: "neutral" | "ok" | "info" }> = {
  draft: { label: "Borrador", tone: "neutral" },
  published: { label: "Publicado", tone: "ok" },
  closed: { label: "Cerrado", tone: "info" },
};

/** Estado y totales del plan por día, para la vista semanal y el inicio. */
export function usePlanDays(plantId: number | null, from: string, days: number) {
  return useQuery({
    queryKey: ["daily-plans", plantId, from, days],
    enabled: plantId !== null,
    refetchInterval: 120_000,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/plants/{plant_id}/daily-plans", {
          params: { path: { plant_id: plantId as number }, query: { from, to: addDays(from, days - 1) } },
        }),
      ),
  });
}

export function PlanDayCard({ day, href }: { day: PlanDay; href: string }) {
  const status = day.status ? STATUS[day.status] : null;
  return (
    <Link href={href} className="flex items-center gap-3 rounded-card bg-card p-4 shadow-card hover:ring-2 hover:ring-teal/30">
      <span className="w-24 shrink-0">
        <span className="block text-sm font-semibold capitalize text-navy">{weekdayLabel(day.productive_date)}</span>
        <span className="num block text-sm text-muted">{formatDate(day.productive_date)}</span>
      </span>
      <span className="flex flex-1 flex-col gap-1">
        {status ? (
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={status.tone}>
              {status.label}
              {day.current_version ? ` · v${day.current_version}` : ""}
            </Badge>
            {day.errors > 0 && (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-coral">
                <AlertTriangle aria-hidden className="size-3.5" />
                {day.errors} {day.errors === 1 ? "error" : "errores"}
              </span>
            )}
            {day.warnings > 0 && <span className="text-xs text-muted">{day.warnings} advertencia(s)</span>}
          </span>
        ) : (
          <span className="text-sm text-muted">Sin plan</span>
        )}
        {day.totals && (
          <span className="num text-sm text-navy">
            {formatNumber(day.totals.lines)} líneas · {formatNumber(day.totals.fish_count)} peces ·{" "}
            {formatNumber(Number(day.totals.biomass_kg) / 1000, 1)} t
          </span>
        )}
      </span>
      <ChevronRight aria-hidden className="size-5 text-muted" />
    </Link>
  );
}

/** Vista semanal de solo lectura: los 7 días desde la fecha del contexto (ADR 0005, decisión 10). */
export function WeekPage() {
  const { plant, date, href } = useAppContext();
  const days = usePlanDays(plant?.id ?? null, date, 7);
  const linkFor = (day: string) => {
    const base = href("/plan");
    const url = new URL(base, "http://x");
    url.searchParams.set("date", day);
    return `${url.pathname}?${url.searchParams.toString()}`;
  };
  return (
    <div className="mx-auto max-w-3xl animate-fade-up">
      <PageHeader title="Semana de cosecha" subtitle={`Desde ${formatDate(date)}${plant ? ` · ${plant.name}` : ""}`} />
      {!plant ? (
        <Card>
          <EmptyState title="Elija una planta" />
        </Card>
      ) : days.isError ? (
        <Alert tone="alert" title="No se pudo cargar la semana">
          {errorMessage(days.error)}
        </Alert>
      ) : days.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 7 }, (_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : (
        <ul className="space-y-2">
          {days.data.map((day) => (
            <li key={day.productive_date}>
              <PlanDayCard day={day} href={linkFor(day.productive_date)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
