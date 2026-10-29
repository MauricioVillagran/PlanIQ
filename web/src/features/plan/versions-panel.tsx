"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, GitCompare, History, Minus, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Badge, EmptyState, Skeleton } from "@/components/ui/feedback";
import { SidePanel } from "@/components/ui/side-panel";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { formatDateTime, formatNumber } from "@/lib/format";

type PlanLine = Schemas["PlanLineOut"];

function tons(kg: string | null | undefined): string {
  return kg === null || kg === undefined ? "—" : `${formatNumber(Number(kg) / 1000, 1)} t`;
}

function showValue(field: string, value: string | number | null): string {
  if (value === null || value === "") return "—";
  if (field === "fish_count") return formatNumber(value);
  if (field === "avg_weight_kg") return formatNumber(value, 3);
  return String(value);
}

function LineSummary({ line }: { line: PlanLine }) {
  return (
    <span>
      <span className="font-medium">
        {line.farm_center_code} · {line.cage_code}
      </span>{" "}
      <span className="text-muted">
        turno {line.shift_name} · acopio {line.holding_cage_code} ·{" "}
        <span className="num">{formatNumber(line.fish_count)}</span> peces ×{" "}
        <span className="num">{formatNumber(line.avg_weight_kg, 3)}</span> kg
      </span>
    </span>
  );
}

function Comparison({ planId, a, b }: { planId: number; a: number; b: number }) {
  const compare = useQuery({
    queryKey: ["daily-plan", planId, "compare", a, b],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/daily-plans/{plan_id}/versions/compare", { params: { path: { plan_id: planId }, query: { a, b } } })),
  });
  if (compare.isPending) return <Skeleton className="h-40" />;
  const diff = compare.data;
  if (!diff) return null;
  const nothing = !diff.added.length && !diff.removed.length && !diff.changed.length;
  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: `Versión ${a}`, totals: diff.totals_a },
          { label: `Versión ${b}`, totals: diff.totals_b },
        ].map(({ label, totals }) => (
          <div key={label} className="rounded-lg bg-bg px-3 py-2">
            <p className="text-xs font-medium uppercase tracking-wider text-muted">{label}</p>
            <p className="num text-navy">{formatNumber(totals.fish_count)} peces</p>
            <p className="num text-navy">{tons(totals.biomass_kg)} biomasa</p>
          </div>
        ))}
      </div>
      {nothing && <p className="text-muted">Sin diferencias en las líneas.</p>}
      {diff.added.length > 0 && (
        <section>
          <h4 className="mb-1 font-semibold text-teal">Agregadas</h4>
          <ul className="space-y-1">
            {diff.added.map((l) => (
              <li key={l.entry_id} className="flex gap-2">
                <Plus aria-hidden className="mt-0.5 size-4 shrink-0 text-teal" />
                <LineSummary line={l} />
              </li>
            ))}
          </ul>
        </section>
      )}
      {diff.removed.length > 0 && (
        <section>
          <h4 className="mb-1 font-semibold text-coral">Eliminadas</h4>
          <ul className="space-y-1">
            {diff.removed.map((l) => (
              <li key={l.entry_id} className="flex gap-2">
                <Minus aria-hidden className="mt-0.5 size-4 shrink-0 text-coral" />
                <LineSummary line={l} />
              </li>
            ))}
          </ul>
        </section>
      )}
      {diff.changed.length > 0 && (
        <section>
          <h4 className="mb-1 font-semibold text-navy">Modificadas</h4>
          <ul className="space-y-2">
            {diff.changed.map((c) => (
              <li key={c.entry_id} className="rounded-lg border border-gray/80 p-2">
                <p className="mb-1 font-medium text-navy">{c.label}</p>
                <ul className="space-y-0.5">
                  {c.changes.map((f) => (
                    <li key={f.field}>
                      {f.label}:{" "}
                      <span className="num text-muted line-through decoration-coral/60">{showValue(f.field, f.old)}</span> →{" "}
                      <span className="num font-semibold">{showValue(f.field, f.new)}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Historial de versiones publicadas y comparador entre dos versiones (sección 6). */
export function VersionsPanel({ planId, open, onClose }: { planId: number; open: boolean; onClose: () => void }) {
  const [pair, setPair] = useState<{ a: number; b: number } | null>(null);
  const versions = useQuery({
    queryKey: ["daily-plan", planId, "versions"],
    enabled: open,
    queryFn: async () => unwrap(await api.GET("/api/v1/daily-plans/{plan_id}/versions", { params: { path: { plan_id: planId } } })),
  });
  const list = versions.data ?? [];

  return (
    <SidePanel
      open={open}
      onClose={() => {
        setPair(null);
        onClose();
      }}
      title={pair ? `Versión ${pair.a} → ${pair.b}` : "Historial de versiones"}
    >
      {pair ? (
        <div className="space-y-4">
          <Button variant="ghost" size="sm" onClick={() => setPair(null)}>
            <ArrowLeft aria-hidden className="size-4" />
            Volver a las versiones
          </Button>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <label className="flex items-center gap-2">
              Comparar
              <select
                value={pair.a}
                onChange={(e) => setPair({ ...pair, a: Number(e.target.value) })}
                className="h-11 rounded-lg border border-gray bg-card px-2"
                aria-label="Versión base"
              >
                {list.map((v) => (
                  <option key={v.number} value={v.number}>
                    v{v.number}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2">
              con
              <select
                value={pair.b}
                onChange={(e) => setPair({ ...pair, b: Number(e.target.value) })}
                className="h-11 rounded-lg border border-gray bg-card px-2"
                aria-label="Versión a comparar"
              >
                {list.map((v) => (
                  <option key={v.number} value={v.number}>
                    v{v.number}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <Comparison planId={planId} a={pair.a} b={pair.b} />
        </div>
      ) : versions.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      ) : !list.length ? (
        <EmptyState icon={History} title="Aún no hay versiones" description="La versión 1 se crea al publicar el plan." />
      ) : (
        <ol className="space-y-3">
          {list.map((v) => (
            <li key={v.number} className="rounded-lg border border-gray/80 p-3 text-sm">
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <span className="flex items-center gap-2">
                  <span className="font-semibold text-navy">Versión {v.number}</span>
                  <Badge tone={v.kind === "publish" ? "ok" : "info"}>{v.kind === "publish" ? "Publicación" : "Modificación"}</Badge>
                </span>
                <span className="num text-xs text-muted">{formatDateTime(v.created_at)}</span>
              </div>
              <p className="text-muted">{v.created_by_name ?? "Sistema"}</p>
              {v.reason && <p className="mt-1 text-navy">Motivo: {v.reason}</p>}
              <p className="num mt-1 text-muted">
                {formatNumber(v.totals.lines)} líneas · {formatNumber(v.totals.fish_count)} peces · {tons(v.totals.biomass_kg)}
              </p>
              {v.number > 1 && (
                <Button variant="secondary" size="sm" className="mt-2" onClick={() => setPair({ a: v.number - 1, b: v.number })}>
                  <GitCompare aria-hidden className="size-4" />
                  Comparar con v{v.number - 1}
                </Button>
              )}
            </li>
          ))}
        </ol>
      )}
    </SidePanel>
  );
}
