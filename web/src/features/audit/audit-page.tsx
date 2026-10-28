"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, SearchX } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { ChangeList } from "@/components/maintainer/history";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, Badge, EmptyState, Skeleton } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/form";
import { SidePanel } from "@/components/ui/side-panel";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { farmCentersDefinition, makeCagesDefinition, makeHoldingCagesDefinition } from "@/features/farms/farms";
import { makeParametersDefinition } from "@/features/parameters/parameters";
import { plantsDefinition } from "@/features/plants/plants";
import { rolesDefinition } from "@/features/roles/roles";
import { makeShiftsDefinition } from "@/features/shifts/shifts";
import { makeUsersDefinition } from "@/features/users/users";
import { api, ApiError, download, unwrap } from "@/lib/api/client";
import type { components, paths } from "@/lib/api/schema";
import { cn } from "@/lib/cn";
import { addDays, todayIn } from "@/lib/dates";
import { formatDateTime, formatNumber } from "@/lib/format";

type AuditEntry = components["schemas"]["AuditEntryOut"];
type AuditAction = NonNullable<NonNullable<paths["/api/v1/audit"]["get"]["parameters"]["query"]>["action"]>;

const PAGE_SIZE = 50;

export const AUDIT_ACTIONS: Record<string, { label: string; tone: "ok" | "alert" | "neutral" | "info" }> = {
  create: { label: "Creación", tone: "ok" },
  update: { label: "Modificación", tone: "info" },
  deactivate: { label: "Desactivación", tone: "alert" },
  activate: { label: "Activación", tone: "ok" },
  delete: { label: "Eliminación", tone: "alert" },
};

/** Nombres de campo de cada tabla, los mismos que usa la pestaña Historial de su mantenedor. */
const FIELD_LABELS: Record<string, Record<string, string> | undefined> = {
  "core.users": makeUsersDefinition(() => {}).fieldLabels,
  "core.roles": rolesDefinition.fieldLabels,
  "master.plants": plantsDefinition.fieldLabels,
  "master.shifts": makeShiftsDefinition(null).fieldLabels,
  "master.parameters": makeParametersDefinition([], false).fieldLabels,
  "master.farm_centers": farmCentersDefinition.fieldLabels,
  "master.cages": makeCagesDefinition([]).fieldLabels,
  "master.holding_cages": makeHoldingCagesDefinition(null).fieldLabels,
};

type Filters = {
  entity: string;
  user_id: string;
  action: string;
  date_from: string;
  date_to: string;
};

function ActionBadge({ action }: { action: string }) {
  const meta = AUDIT_ACTIONS[action];
  return <Badge tone={meta?.tone ?? "neutral"}>{meta?.label ?? action}</Badge>;
}

/** Auditoría (sección 13): quién cambió qué y cuándo, con filtros y exportación a Excel. */
export function AuditPage() {
  const toast = useToast();
  const today = todayIn();
  const [filters, setFilters] = useState<Filters>({
    entity: "",
    user_id: "",
    action: "",
    date_from: addDays(today, -6),
    date_to: today,
  });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AuditEntry | null>(null);

  const setFilter = (name: keyof Filters, value: string) => {
    setFilters((f) => ({ ...f, [name]: value }));
    setPage(1);
  };

  const query = {
    entity: filters.entity || undefined,
    user_id: filters.user_id ? Number(filters.user_id) : undefined,
    action: (filters.action || undefined) as AuditAction | undefined,
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
  };
  const rangeInvalid = !!query.date_from && !!query.date_to && query.date_from > query.date_to;

  const entities = useQuery({
    queryKey: ["audit", "entities"],
    queryFn: async () => unwrap(await api.GET("/api/v1/audit/entities")),
  });
  const users = useQuery({
    queryKey: ["audit", "users"],
    queryFn: async () => unwrap(await api.GET("/api/v1/audit/users")),
  });
  const list = useQuery({
    queryKey: ["audit", "list", query, page],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/audit", {
          params: { query: { ...query, page, page_size: PAGE_SIZE } },
        }),
      ),
    placeholderData: keepPreviousData,
    enabled: !rangeInvalid,
  });

  const exportExcel = useMutation({
    mutationFn: () => download("/api/v1/audit/export.xlsx", query),
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "No se pudo exportar."),
  });

  const data = list.data;
  const items = data?.items ?? [];
  const from = data && data.total ? (data.page - 1) * data.page_size + 1 : 0;
  const to = data ? Math.min(data.page * data.page_size, data.total) : 0;
  const lastPage = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const labelsOf = (entry: AuditEntry) => FIELD_LABELS[entry.entity] ?? {};

  return (
    <div className="mx-auto max-w-6xl animate-fade-up">
      <PageHeader
        title="Auditoría"
        subtitle="Quién cambió qué y cuándo"
        actions={
          <Button
            variant="secondary"
            onClick={() => exportExcel.mutate()}
            loading={exportExcel.isPending}
            disabled={rangeInvalid}
          >
            <Download aria-hidden className="size-4" />
            <span className="hidden sm:inline">Exportar</span>
            <span className="sr-only sm:hidden">Exportar a Excel</span>
          </Button>
        }
      />

      {/* Filtros */}
      <Card className="mb-3 grid grid-cols-2 gap-3 p-3 sm:grid-cols-6 sm:p-4 xl:grid-cols-[repeat(3,minmax(0,1fr))_10.5rem_10.5rem]">
        <div className="col-span-2 xl:col-span-1">
          <Select label="Tabla" value={filters.entity} onChange={(e) => setFilter("entity", e.target.value)}>
            <option value="">Todas</option>
            {entities.data?.map((o) => (
              <option key={o.entity} value={o.entity}>
                {o.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="sm:col-span-2 xl:col-span-1">
          <Select label="Usuario" value={filters.user_id} onChange={(e) => setFilter("user_id", e.target.value)}>
            <option value="">Todos</option>
            {users.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </Select>
        </div>
        <div className="sm:col-span-2 xl:col-span-1">
          <Select label="Acción" value={filters.action} onChange={(e) => setFilter("action", e.target.value)}>
            <option value="">Todas</option>
            {Object.entries(AUDIT_ACTIONS).map(([value, meta]) => (
              <option key={value} value={value}>
                {meta.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="sm:col-span-3 xl:col-span-1">
          <Input
            label="Desde"
            type="date"
            value={filters.date_from}
            max={filters.date_to || undefined}
            onChange={(e) => setFilter("date_from", e.target.value)}
          />
        </div>
        <div className="sm:col-span-3 xl:col-span-1">
          <Input
            label="Hasta"
            type="date"
            value={filters.date_to}
            min={filters.date_from || undefined}
            onChange={(e) => setFilter("date_to", e.target.value)}
            error={rangeInvalid ? "Debe ser igual o posterior a Desde" : undefined}
          />
        </div>
      </Card>

      {list.isError && (
        <Alert tone="alert" title="No se pudo cargar la auditoría">
          {list.error instanceof ApiError ? list.error.message : "Revise su conexión e intente nuevamente."}
        </Alert>
      )}

      {list.isPending && !rangeInvalid ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon={SearchX}
            title="Sin registros"
            description="No hay cambios con estos filtros. Amplíe el rango de fechas o quite filtros."
          />
        </Card>
      ) : (
        <>
          {/* Escritorio: tabla */}
          <Card className={cn("hidden overflow-hidden xl:block", list.isFetching && "opacity-70")}>
            <Table className="table-fixed">
              <thead>
                <tr>
                  <Th className="w-36">Fecha</Th>
                  <Th className="w-28">Usuario</Th>
                  <Th className="w-32">Acción</Th>
                  <Th className="w-36">Tabla</Th>
                  <Th numeric className="w-20">
                    Registro
                  </Th>
                  <Th>Cambios</Th>
                </tr>
              </thead>
              <tbody>
                {items.map((entry) => (
                  <Tr key={entry.id} onClick={() => setSelected(entry)} className="cursor-pointer align-top">
                    <Td className="num whitespace-nowrap">{formatDateTime(entry.occurred_at)}</Td>
                    <Td>{entry.username ?? <span className="text-muted">Sistema</span>}</Td>
                    <Td>
                      <ActionBadge action={entry.action} />
                    </Td>
                    <Td>{entry.entity_label}</Td>
                    <Td numeric>{entry.entity_id}</Td>
                    <Td className="text-sm">
                      <ChangeList changes={entry.changes} fieldLabels={labelsOf(entry)} limit={3} />
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </Card>

          {/* Celular: tarjetas */}
          <ul className={cn("space-y-2 xl:hidden", list.isFetching && "opacity-70")}>
            {items.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => setSelected(entry)}
                  className="flex w-full flex-col gap-1 rounded-card bg-card p-4 text-left shadow-card active:bg-teal/[0.04]"
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-navy">
                      {entry.entity_label} <span className="num font-normal text-muted">#{entry.entity_id}</span>
                    </span>
                    <ActionBadge action={entry.action} />
                  </span>
                  <span className="flex flex-wrap justify-between gap-x-2 text-sm text-muted">
                    <span>{entry.username ?? "Sistema"}</span>
                    <span className="num">{formatDateTime(entry.occurred_at)}</span>
                  </span>
                  <span className="text-sm">
                    <ChangeList changes={entry.changes} fieldLabels={labelsOf(entry)} limit={2} />
                  </span>
                </button>
              </li>
            ))}
          </ul>

          {/* Paginación */}
          <nav aria-label="Paginación" className="mt-3 flex items-center justify-between gap-2 text-sm text-muted">
            <span className="num">
              {formatNumber(from)}–{formatNumber(to)} de {formatNumber(data?.total ?? 0)}
            </span>
            <div className="flex gap-1">
              <Button variant="secondary" size="sm" onClick={() => setPage((p) => p - 1)} disabled={page <= 1}>
                <ChevronLeft aria-hidden className="size-4" />
                <span className="sr-only">Página anterior</span>
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setPage((p) => p + 1)} disabled={page >= lastPage}>
                <ChevronRight aria-hidden className="size-4" />
                <span className="sr-only">Página siguiente</span>
              </Button>
            </div>
          </nav>
        </>
      )}

      {/* Detalle de una entrada */}
      <SidePanel
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.entity_label} #${selected.entity_id}` : ""}
      >
        {selected && (
          <div className="space-y-4 text-sm">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
              <dt className="text-muted">Acción</dt>
              <dd>
                <ActionBadge action={selected.action} />
              </dd>
              <dt className="text-muted">Fecha</dt>
              <dd className="num">{formatDateTime(selected.occurred_at)}</dd>
              <dt className="text-muted">Usuario</dt>
              <dd>{selected.username ?? "Sistema"}</dd>
              <dt className="text-muted">Tabla</dt>
              <dd>
                {selected.entity_label} <span className="text-muted">({selected.entity})</span>
              </dd>
              {selected.plant_id !== null && (
                <>
                  <dt className="text-muted">Planta</dt>
                  <dd className="num">{selected.plant_id}</dd>
                </>
              )}
              {selected.request_id && (
                <>
                  <dt className="text-muted">Request ID</dt>
                  <dd className="num break-all">{selected.request_id}</dd>
                </>
              )}
            </dl>
            <section>
              <h3 className="mb-2 font-semibold text-navy">Cambios</h3>
              <div className="rounded-lg border border-gray/80 p-3">
                <ChangeList changes={selected.changes} fieldLabels={labelsOf(selected)} />
              </div>
            </section>
          </div>
        )}
      </SidePanel>
    </div>
  );
}
