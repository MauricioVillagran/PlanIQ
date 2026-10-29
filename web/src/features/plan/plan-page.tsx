"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CalendarDays,
  CalendarRange,
  Copy,
  GripVertical,
  History,
  Lock,
  Pencil,
  Plus,
  Send,
  Trash2,
  Undo2,
} from "lucide-react";
import Link from "next/link";
import { useId, useMemo, useState, type DragEvent } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, KpiCard } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Alert, Badge, EmptyState, Skeleton } from "@/components/ui/feedback";
import { SidePanel } from "@/components/ui/side-panel";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { useAppContext } from "@/lib/app-context";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { addDays, weekdayLabel } from "@/lib/dates";
import { formatDate, formatDateTime, formatNumber } from "@/lib/format";

import { describeLine, EntryForm, usePlanMasters, type Masters } from "./entry-form";
import { biomassKg, groupTotals, liveTotals } from "./totals";
import { VersionsPanel } from "./versions-panel";
import { buildChanges, fromEntry, move, moveTo, type LineValues, type PlanRow } from "./working-copy";

type PlanDetail = Schemas["DailyPlanDetailOut"];
type Issue = Schemas["IssueOut"];

const STATUS: Record<string, { label: string; tone: "neutral" | "ok" | "info" }> = {
  draft: { label: "Borrador", tone: "neutral" },
  published: { label: "Publicado", tone: "ok" },
  closed: { label: "Cerrado", tone: "info" },
};

const POLL_MS = 120_000;

function tons(kg: number | null): string {
  return kg === null ? "—" : formatNumber(kg / 1000, 1);
}

export function errorMessage(error: unknown, fallback = "No se pudo completar la operación."): string {
  return error instanceof ApiError ? error.message : fallback;
}

// --- Plan inexistente ----------------------------------------------------------------------

function NoPlan({ plantId, date, canEdit, onCreated }: { plantId: number; date: string; canEdit: boolean; onCreated: () => void }) {
  const toast = useToast();
  const previous = addDays(date, -1);
  const create = useMutation({
    mutationFn: async (copyFrom: string | null) =>
      unwrap(
        await api.POST("/api/v1/plants/{plant_id}/daily-plans/{productive_date}", {
          params: { path: { plant_id: plantId, productive_date: date } },
          body: { copy_from: copyFrom },
        }),
      ),
    onSuccess: () => {
      toast.success("Plan creado en Borrador.");
      onCreated();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  return (
    <Card>
      <EmptyState
        icon={CalendarDays}
        title={canEdit ? "Aún no hay plan para esta fecha" : "El plan de esta fecha aún no se publica"}
        description={
          canEdit
            ? "Créelo vacío o copie las líneas del día anterior para ajustarlas."
            : "Cuando Planificación lo publique, aparecerá aquí y le llegará un aviso."
        }
        action={
          canEdit ? (
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button onClick={() => create.mutate(null)} loading={create.isPending && create.variables === null}>
                <Plus aria-hidden className="size-4" />
                Crear plan vacío
              </Button>
              <Button variant="secondary" onClick={() => create.mutate(previous)} loading={create.isPending && create.variables === previous}>
                <Copy aria-hidden className="size-4" />
                Copiar del {formatDate(previous)}
              </Button>
            </div>
          ) : undefined
        }
      />
    </Card>
  );
}

// --- Totales y alertas -----------------------------------------------------------------------

function TotalsBar({ rows, factor, live }: { rows: PlanRow[]; factor: string | null; live: boolean }) {
  const day = liveTotals(rows, factor);
  const byShift = groupTotals(rows, "shift_id", factor);
  const byCenter = groupTotals(rows, "farm_center_id", factor);
  const label = (key: "shift_name" | "farm_center_code", id: number, field: "shift_id" | "farm_center_id") =>
    rows.find((r) => r[field] === id)?.[key] ?? "—";
  return (
    <section aria-label="Totales del día" className="mb-4 space-y-3">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="Peces" value={formatNumber(day.fish)} />
        <KpiCard label="Biomasa" value={tons(day.biomassKg)} unit="t" />
        <KpiCard
          label="WFE proyectado"
          value={tons(day.wfeKg)}
          unit={day.wfeKg === null ? undefined : "t"}
          tone={day.wfeKg === null ? "neutral" : "ok"}
          hint={day.wfeKg === null ? "Sin factor configurado" : undefined}
        />
        <KpiCard label="Líneas" value={formatNumber(day.lines)} tone="neutral" hint={live ? "Incluye cambios sin guardar" : undefined} />
      </div>
      {rows.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            { title: "Por turno", groups: byShift, name: (id: number) => label("shift_name", id, "shift_id") },
            { title: "Por centro", groups: byCenter, name: (id: number) => label("farm_center_code", id, "farm_center_id") },
          ].map(({ title, groups, name }) => (
            <Card key={title} className="px-4 py-3">
              <h2 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted">{title}</h2>
              <ul className="space-y-1 text-sm">
                {[...groups].map(([id, t]) => (
                  <li key={id} className="flex justify-between gap-2">
                    <span className="font-medium text-navy">{name(id)}</span>
                    <span className="num text-muted">
                      {formatNumber(t.fish)} peces · {tons(t.biomassKg)} t
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

function IssuesList({ issues }: { issues: Issue[] }) {
  if (!issues.length) return null;
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  return (
    <div className="mb-4 space-y-2">
      {errors.length > 0 && (
        <Alert tone="alert" title={`${errors.length} ${errors.length === 1 ? "error bloquea" : "errores bloquean"} la publicación`}>
          <ul className="list-disc pl-5">
            {errors.map((i, n) => (
              <li key={n}>{i.message}</li>
            ))}
          </ul>
        </Alert>
      )}
      {warnings.length > 0 && (
        <Alert tone="info" title={warnings.length === 1 ? "Advertencia" : `${warnings.length} advertencias`}>
          <ul className="list-disc pl-5">
            {warnings.map((i, n) => (
              <li key={n}>{i.message}</li>
            ))}
          </ul>
        </Alert>
      )}
    </div>
  );
}

function IssueMark({ issues }: { issues: Issue[] | undefined }) {
  if (!issues?.length) return null;
  const error = issues.some((i) => i.severity === "error");
  return (
    <span title={issues.map((i) => i.message).join("\n")} className={cn("inline-flex", error ? "text-coral" : "text-blue-mid")}>
      <AlertTriangle aria-hidden className="size-4" />
      <span className="sr-only">{issues.map((i) => i.message).join(". ")}</span>
    </span>
  );
}

// --- Líneas ----------------------------------------------------------------------------------

type LinesProps = {
  rows: PlanRow[];
  issuesByEntry: Map<number, Issue[]>;
  editable: boolean;
  onEdit: (row: PlanRow) => void;
  onMove: (index: number, delta: -1 | 1) => void;
  onMoveTo: (from: number, to: number) => void;
  onDelete: (row: PlanRow) => void;
};

function MoveButtons({ index, total, onMove, row }: { index: number; total: number; onMove: LinesProps["onMove"]; row: PlanRow }) {
  return (
    <span className="flex">
      <Button variant="ghost" size="sm" className="px-2" onClick={() => onMove(index, -1)} disabled={index === 0}>
        <ArrowUp aria-hidden className="size-4" />
        <span className="sr-only">Subir {row.cage_code}</span>
      </Button>
      <Button variant="ghost" size="sm" className="px-2" onClick={() => onMove(index, 1)} disabled={index === total - 1}>
        <ArrowDown aria-hidden className="size-4" />
        <span className="sr-only">Bajar {row.cage_code}</span>
      </Button>
    </span>
  );
}

function LinesTable({ rows, issuesByEntry, editable, onEdit, onMove, onMoveTo, onDelete }: LinesProps) {
  const [dragging, setDragging] = useState<number | null>(null);
  const drop = (event: DragEvent, to: number) => {
    event.preventDefault();
    if (dragging !== null && dragging !== to) onMoveTo(dragging, to);
    setDragging(null);
  };
  return (
    <Card className="hidden overflow-hidden lg:block">
      <Table>
        <thead>
          <tr>
            <Th className="w-16">Orden</Th>
            <Th>Centro</Th>
            <Th>Jaula</Th>
            <Th>Turno</Th>
            <Th>Acopio</Th>
            <Th numeric>Peces</Th>
            <Th numeric>Peso prom. (kg)</Th>
            <Th numeric>Biomasa (kg)</Th>
            <Th>Observaciones</Th>
            {editable && <Th className="w-40">Acciones</Th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <Tr
              key={row.key}
              draggable={editable}
              onDragStart={() => setDragging(index)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => drop(e, index)}
              onDragEnd={() => setDragging(null)}
              className={cn(dragging === index && "opacity-50", row.id === null && "bg-teal/[0.05]")}
            >
              <Td>
                <span className="flex items-center gap-1">
                  {editable && <GripVertical aria-hidden className="size-4 cursor-grab text-muted" />}
                  <span className="num">{index + 1}</span>
                  <IssueMark issues={row.id !== null ? issuesByEntry.get(row.id) : undefined} />
                </span>
              </Td>
              <Td>
                <span className="num font-medium">{row.farm_center_code}</span>
                <span className="block text-xs text-muted">{row.farm_center_name}</span>
              </Td>
              <Td className="num">{row.cage_code}</Td>
              <Td>{row.shift_name}</Td>
              <Td className="num">{row.holding_cage_code}</Td>
              <Td numeric>{formatNumber(row.fish_count)}</Td>
              <Td numeric>{formatNumber(row.avg_weight_kg, 3)}</Td>
              <Td numeric>{formatNumber(biomassKg(row.fish_count, row.avg_weight_kg), 0)}</Td>
              <Td className="max-w-48 truncate text-sm text-muted" title={row.notes ?? undefined}>
                {row.notes ?? ""}
              </Td>
              {editable && (
                <Td>
                  <span className="flex items-center">
                    <MoveButtons index={index} total={rows.length} onMove={onMove} row={row} />
                    <Button variant="ghost" size="sm" className="px-2" onClick={() => onEdit(row)}>
                      <Pencil aria-hidden className="size-4" />
                      <span className="sr-only">Editar {row.cage_code}</span>
                    </Button>
                    <Button variant="ghostDanger" size="sm" className="px-2" onClick={() => onDelete(row)}>
                      <Trash2 aria-hidden className="size-4" />
                      <span className="sr-only">Eliminar {row.cage_code}</span>
                    </Button>
                  </span>
                </Td>
              )}
            </Tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

function LinesCards({ rows, issuesByEntry, editable, onEdit, onMove, onDelete }: LinesProps) {
  const groups = new Map<number, { code: string; name: string; items: { row: PlanRow; index: number }[] }>();
  rows.forEach((row, index) => {
    const group = groups.get(row.farm_center_id) ?? { code: row.farm_center_code, name: row.farm_center_name, items: [] };
    group.items.push({ row, index });
    groups.set(row.farm_center_id, group);
  });
  return (
    <div className="space-y-4 lg:hidden">
      {[...groups.values()].map((group) => {
        const t = liveTotals(group.items.map((i) => i.row), null);
        return (
          <section key={group.code} aria-label={`Centro ${group.code}`}>
            <h2 className="mb-2 flex items-baseline justify-between gap-2 px-1">
              <span className="font-semibold text-navy">
                {group.code} <span className="font-normal text-muted">{group.name}</span>
              </span>
              <span className="num text-sm text-muted">
                {formatNumber(t.fish)} peces · {tons(t.biomassKg)} t
              </span>
            </h2>
            <ul className="space-y-2">
              {group.items.map(({ row, index }) => (
                <li key={row.key} className={cn("rounded-card bg-card p-4 shadow-card", row.id === null && "ring-2 ring-teal/30")}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-navy">
                      <span className="num text-muted">#{index + 1}</span> Jaula <span className="num">{row.cage_code}</span>{" "}
                      <IssueMark issues={row.id !== null ? issuesByEntry.get(row.id) : undefined} />
                    </span>
                    <Badge tone="info">{row.shift_name}</Badge>
                  </div>
                  <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <dt className="text-xs text-muted">Peces</dt>
                      <dd className="num text-navy">{formatNumber(row.fish_count)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted">Peso (kg)</dt>
                      <dd className="num text-navy">{formatNumber(row.avg_weight_kg, 3)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted">Biomasa (kg)</dt>
                      <dd className="num text-navy">{formatNumber(biomassKg(row.fish_count, row.avg_weight_kg), 0)}</dd>
                    </div>
                  </dl>
                  <p className="mt-1 text-sm text-muted">
                    Acopio <span className="num">{row.holding_cage_code}</span>
                    {row.notes ? ` · ${row.notes}` : ""}
                  </p>
                  {editable && (
                    <div className="mt-2 flex items-center justify-between border-t border-gray/60 pt-2">
                      <MoveButtons index={index} total={rows.length} onMove={onMove} row={row} />
                      <span className="flex">
                        <Button variant="ghost" size="sm" onClick={() => onEdit(row)}>
                          <Pencil aria-hidden className="size-4" />
                          Editar
                        </Button>
                        <Button variant="ghostDanger" size="sm" className="px-2" onClick={() => onDelete(row)}>
                          <Trash2 aria-hidden className="size-4" />
                          <span className="sr-only">Eliminar {row.cage_code}</span>
                        </Button>
                      </span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

// --- Página ----------------------------------------------------------------------------------

type PanelState = { row: PlanRow | null } | null;

function PlanView({
  detail,
  masters,
  refresh,
  checkedAt,
}: {
  detail: PlanDetail;
  masters: Masters;
  refresh: () => Promise<unknown>;
  /** Hora de la última consulta: decide si ya se puede cerrar sin leer el reloj al dibujar. */
  checkedAt: number;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const formId = useId();
  const { plan, summary } = detail;
  const planId = plan.id;
  const serverRows = useMemo(() => detail.entries.map(fromEntry), [detail.entries]);

  const [working, setWorking] = useState<PlanRow[] | null>(null);
  const [panel, setPanel] = useState<PanelState>(null);
  const [confirmDelete, setConfirmDelete] = useState<PlanRow | null>(null);
  const [dialog, setDialog] = useState<"publish" | "close" | "save" | null>(null);
  const [reason, setReason] = useState("");
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [showVersions, setShowVersions] = useState(false);
  const [tmpCounter, setTmpCounter] = useState(0);

  const isDraft = plan.status === "draft";
  const isPublished = plan.status === "published";
  const editing = working !== null;
  const canEdit = can("plan.edit") && (isDraft || (isPublished && editing));
  const rows = working ?? serverRows;
  const changes = editing ? buildChanges(serverRows, working) : null;

  const issuesByEntry = useMemo(() => {
    const map = new Map<number, Issue[]>();
    for (const issue of summary.issues) for (const id of issue.entry_ids) map.set(id, [...(map.get(id) ?? []), issue]);
    return map;
  }, [summary.issues]);

  const closableAt = detail.closable_at;
  const closable = isPublished && !editing && !!closableAt && new Date(closableAt).getTime() <= checkedAt;

  // Borrador: cada acción va directo a la API.
  const onConflict = async (error: unknown) => {
    if (error instanceof ApiError && error.status === 409) {
      toast.error("Otro usuario modificó el plan. Se cargaron los datos actuales.");
      setPanel(null);
      await refresh();
      return true;
    }
    return false;
  };

  const saveLine = async (values: LineValues) => {
    const row = panel?.row ?? null;
    if (editing) {
      const labels = describeLine(values, masters);
      const key = `tmp-${tmpCounter}`;
      if (!row) setTmpCounter((n) => n + 1);
      setWorking((current) => {
        const list = current ?? serverRows;
        if (row) return list.map((r) => (r.key === row.key ? { ...r, ...values, ...labels } : r));
        return [...list, { ...values, ...labels, key, id: null, row_version: null }];
      });
      setPanel(null);
      return;
    }
    try {
      if (row?.id) {
        unwrap(
          await api.PATCH("/api/v1/daily-plans/{plan_id}/harvest-entries/{entry_id}", {
            params: { path: { plan_id: planId, entry_id: row.id } },
            body: { row_version: row.row_version as string, ...values },
          }),
        );
        toast.success("Línea actualizada.");
      } else {
        unwrap(
          await api.POST("/api/v1/daily-plans/{plan_id}/harvest-entries", {
            params: { path: { plan_id: planId } },
            body: values,
          }),
        );
        toast.success("Línea agregada.");
      }
      setPanel(null);
      await refresh();
    } catch (error) {
      if (!(await onConflict(error))) throw error;
    }
  };

  const reorder = async (next: PlanRow[]) => {
    if (editing) {
      setWorking(next);
      return;
    }
    try {
      unwrap(
        await api.PUT("/api/v1/daily-plans/{plan_id}/harvest-entries/order", {
          params: { path: { plan_id: planId } },
          body: { entry_ids: next.map((r) => r.id as number) },
        }),
      );
      await refresh();
    } catch (error) {
      if (!(await onConflict(error))) toast.error(errorMessage(error));
    }
  };

  const remove = async (row: PlanRow) => {
    setConfirmDelete(null);
    if (editing) {
      setWorking((current) => (current ?? serverRows).filter((r) => r.key !== row.key));
      return;
    }
    try {
      unwrap(
        await api.DELETE("/api/v1/daily-plans/{plan_id}/harvest-entries/{entry_id}", {
          params: { path: { plan_id: planId, entry_id: row.id as number }, query: { row_version: row.row_version as string } },
        }),
      );
      toast.success("Línea eliminada.");
      await refresh();
    } catch (error) {
      if (!(await onConflict(error))) toast.error(errorMessage(error));
    }
  };

  const transition = useMutation({
    mutationFn: async (kind: "publish" | "close" | "save") => {
      const path = { params: { path: { plan_id: planId } } };
      if (kind === "publish") return unwrap(await api.POST("/api/v1/daily-plans/{plan_id}/publish", { ...path, body: { row_version: plan.row_version } }));
      if (kind === "close") return unwrap(await api.POST("/api/v1/daily-plans/{plan_id}/close", { ...path, body: { row_version: plan.row_version } }));
      const { add, update, delete: del, order } = buildChanges(serverRows, working ?? serverRows);
      return unwrap(
        await api.POST("/api/v1/daily-plans/{plan_id}/changes", {
          ...path,
          body: { row_version: plan.row_version, reason: reason.trim(), add, update, delete: del, order },
        }),
      );
    },
    onSuccess: async (_data, kind) => {
      toast.success(
        kind === "publish" ? "Plan publicado: se avisó a las demás áreas." : kind === "close" ? "Plan cerrado." : "Cambios guardados como versión nueva.",
      );
      setDialog(null);
      setDialogError(null);
      setReason("");
      setWorking(null);
      await refresh();
    },
    onError: (error) => setDialogError(errorMessage(error)),
  });

  const status = STATUS[plan.status] ?? { label: plan.status, tone: "neutral" as const };

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge tone={status.tone}>
          {status.label}
          {plan.current_version > 0 && ` · versión ${plan.current_version}`}
        </Badge>
        {plan.published_at && <span className="text-sm text-muted">Publicado el {formatDateTime(plan.published_at)}</span>}
        <div className="ml-auto flex flex-wrap gap-2">
          {plan.current_version > 0 && (
            <Button variant="secondary" onClick={() => setShowVersions(true)}>
              <History aria-hidden className="size-4" />
              Versiones
            </Button>
          )}
          {isDraft && can("plan.publish") && (
            <Button onClick={() => setDialog("publish")} disabled={!rows.length || summary.has_errors}>
              <Send aria-hidden className="size-4" />
              Publicar
            </Button>
          )}
          {isPublished && can("plan.edit") && !editing && (
            <Button variant="secondary" onClick={() => setWorking(serverRows)}>
              <Pencil aria-hidden className="size-4" />
              Modificar
            </Button>
          )}
          {isPublished && can("plan.close") && !editing && (
            <Button
              variant="secondary"
              onClick={() => setDialog("close")}
              disabled={!closable}
              title={closable || !closableAt ? undefined : `Se puede cerrar desde ${formatDateTime(closableAt)}`}
            >
              <Lock aria-hidden className="size-4" />
              Cerrar
            </Button>
          )}
        </div>
      </div>

      {editing && changes && (
        <Alert tone="info" title="Modificando un plan publicado">
          <p>Los cambios se guardan juntos, con un motivo, y crean la versión {plan.current_version + 1}. Las demás áreas siguen viendo la versión vigente hasta entonces.</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="sm" onClick={() => setDialog("save")} disabled={changes.count === 0}>
              Guardar cambios ({changes.count})
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setWorking(null)}>
              <Undo2 aria-hidden className="size-4" />
              Descartar
            </Button>
          </div>
        </Alert>
      )}
      {plan.status === "closed" && <Alert tone="info">Plan cerrado el {formatDateTime(plan.closed_at)}: es de solo lectura.</Alert>}

      <div className={cn((editing || plan.status === "closed") && "mt-4")}>
        <TotalsBar rows={rows} factor={summary.wfe_factor} live={editing && (changes?.count ?? 0) > 0} />
      </div>
      {!editing && <IssuesList issues={summary.issues} />}

      {canEdit && (
        <div className="mb-3 flex justify-end">
          <Button onClick={() => setPanel({ row: null })}>
            <Plus aria-hidden className="size-4" />
            Agregar línea
          </Button>
        </div>
      )}

      {rows.length === 0 ? (
        <Card>
          <EmptyState
            title="El plan no tiene líneas"
            description={canEdit ? "Agregue la primera jaula a cosechar." : "Planificación aún no carga la cosecha de este día."}
          />
        </Card>
      ) : (
        <>
          {(["table", "cards"] as const).map((kind) => {
            const props: LinesProps = {
              rows,
              issuesByEntry: editing ? new Map() : issuesByEntry,
              editable: canEdit,
              onEdit: (row) => setPanel({ row }),
              onMove: (index, delta) => void reorder(move(rows, index, delta)),
              onMoveTo: (from, to) => void reorder(moveTo(rows, from, to)),
              onDelete: (row) => setConfirmDelete(row),
            };
            return kind === "table" ? <LinesTable key={kind} {...props} /> : <LinesCards key={kind} {...props} />;
          })}
        </>
      )}

      <SidePanel
        open={!!panel}
        onClose={() => setPanel(null)}
        title={panel?.row ? `Jaula ${panel.row.cage_code}` : "Nueva línea de cosecha"}
        footer={
          <>
            <Button type="submit" form={formId} className="flex-1">
              {editing ? "Aplicar" : panel?.row ? "Guardar cambios" : "Agregar"}
            </Button>
            <Button variant="secondary" onClick={() => setPanel(null)}>
              Cancelar
            </Button>
          </>
        }
      >
        {panel && (
          <EntryForm key={String(panel.row?.key ?? "new")} formId={formId} row={panel.row} masters={masters} readOnly={false} onSubmit={saveLine} />
        )}
      </SidePanel>

      <Dialog
        open={!!confirmDelete}
        title="Eliminar línea"
        actions={
          <>
            <Button variant="danger" onClick={() => confirmDelete && void remove(confirmDelete)}>
              Eliminar
            </Button>
            <Button variant="secondary" onClick={() => setConfirmDelete(null)}>
              Cancelar
            </Button>
          </>
        }
      >
        <p>
          Se quitará la jaula <span className="num font-semibold">{confirmDelete?.cage_code}</span> del centro {confirmDelete?.farm_center_code} del plan.
        </p>
      </Dialog>

      <Dialog
        open={dialog !== null}
        title={dialog === "publish" ? "Publicar plan" : dialog === "close" ? "Cerrar plan" : "Guardar cambios"}
        actions={
          <>
            <Button
              variant={dialog === "close" ? "danger" : "primary"}
              loading={transition.isPending}
              disabled={dialog === "save" && reason.trim().length < 5}
              onClick={() => dialog && transition.mutate(dialog)}
            >
              {dialog === "publish" ? "Publicar" : dialog === "close" ? "Cerrar plan" : "Guardar versión"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setDialog(null);
                setDialogError(null);
              }}
            >
              Cancelar
            </Button>
          </>
        }
      >
        {dialogError && <Alert tone="alert">{dialogError}</Alert>}
        {dialog === "publish" && (
          <p>
            Se creará la versión 1 y el plan quedará visible para todas las áreas, que recibirán un aviso.
            {summary.issues.length > 0 && ` Tiene ${summary.issues.length} advertencia(s) que no bloquean.`}
          </p>
        )}
        {dialog === "close" && <p>El plan quedará inmutable y no se podrá reabrir.</p>}
        {dialog === "save" && (
          <label className="flex flex-col gap-1.5">
            <span className="font-medium">Motivo del cambio *</span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="Ej.: jaula N2 en ayuno extendido"
              className="w-full rounded-lg border border-gray bg-card px-3 py-2 text-base text-navy focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/25"
            />
            <span className="text-xs text-muted">Mínimo 5 caracteres. Las demás áreas lo verán en el aviso.</span>
          </label>
        )}
      </Dialog>

      <VersionsPanel planId={planId} open={showVersions} onClose={() => setShowVersions(false)} />
    </>
  );
}

/** Planificación › Plan de cosecha de la planta y fecha del contexto (sección 5.2). */
export function PlanPage() {
  const { plant, date, href } = useAppContext();
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const plantId = plant?.id ?? null;
  const key = ["daily-plan", plantId, date];

  const planQuery = useQuery({
    queryKey: key,
    enabled: plantId !== null,
    refetchInterval: POLL_MS,
    queryFn: async () => {
      try {
        return unwrap(
          await api.GET("/api/v1/plants/{plant_id}/daily-plans/{productive_date}", {
            params: { path: { plant_id: plantId as number, productive_date: date } },
          }),
        );
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
  });
  const masters = usePlanMasters(plantId);
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });

  return (
    <div className="mx-auto max-w-6xl animate-fade-up">
      <PageHeader
        title="Plan de cosecha"
        subtitle={`${weekdayLabel(date)} ${formatDate(date)}${plant ? ` · ${plant.name}` : ""}`}
        actions={
          <Link
            href={href("/plan/week")}
            className="inline-flex h-11 items-center gap-2 rounded-lg border border-gray bg-card px-4 text-sm font-semibold text-navy hover:border-teal hover:text-teal"
          >
            <CalendarRange aria-hidden className="size-4" />
            Semana
          </Link>
        }
      />
      {planQuery.dataUpdatedAt > 0 && (
        <p className="-mt-3 mb-3 text-xs text-muted">Actualizado {formatDateTime(new Date(planQuery.dataUpdatedAt).toISOString())}</p>
      )}

      {!plant ? (
        <Card>
          <EmptyState title="Elija una planta" description="Use el selector de planta de arriba para ver su plan." />
        </Card>
      ) : planQuery.isError ? (
        <Alert tone="alert" title="No se pudo cargar el plan">
          {errorMessage(planQuery.error, "Revise su conexión e intente nuevamente.")}
        </Alert>
      ) : planQuery.isPending || masters.isPending ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
          <Skeleton className="h-64" />
        </div>
      ) : planQuery.data === null ? (
        <NoPlan plantId={plant.id} date={date} canEdit={can("plan.edit")} onCreated={() => void refresh()} />
      ) : planQuery.data && masters.data ? (
        <PlanView
          key={planQuery.data.plan.id}
          detail={planQuery.data}
          masters={masters.data}
          refresh={refresh}
          checkedAt={planQuery.dataUpdatedAt}
        />
      ) : null}
    </div>
  );
}
