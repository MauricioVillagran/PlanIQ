"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download, Plus, Search, SearchX } from "lucide-react";
import { useCallback, useEffect, useId, useState, type ReactNode } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, Badge, EmptyState, Skeleton } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { SidePanel } from "@/components/ui/side-panel";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { ApiError, download, request } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";

import { MaintainerHistory } from "./history";
import type { BaseRow, MaintainerDefinition, Page } from "./types";

const PAGE_SIZE = 25;
type Status = "active" | "inactive" | "all";

export function StatusBadge({ active, children }: { active: boolean; children?: ReactNode }) {
  return <Badge tone={active ? "ok" : "neutral"}>{children ?? (active ? "Activo" : "Inactivo")}</Badge>;
}

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

type PanelState<T> = { mode: "create" } | { mode: "edit"; item: T } | null;

/**
 * Mantenedor genérico (sección 5.1): listado paginado del servidor con búsqueda, filtros y orden;
 * alta y edición en panel lateral (pantalla completa en celular); activar/desactivar; historial;
 * exportación a Excel. Tabla en escritorio, tarjetas en celular.
 */
export function MaintainerPage<T extends BaseRow>({
  definition,
  baseQuery = {},
  header,
  createDisabledReason,
  onChanged,
}: {
  definition: MaintainerDefinition<T>;
  /** Filtros fijos (por ejemplo, la planta del contexto). */
  baseQuery?: Record<string, string | number | null | undefined>;
  /** Contenido sobre el listado (por ejemplo, la cobertura de turnos). */
  header?: ReactNode;
  /** Si viene, el alta queda deshabilitada con esta explicación. */
  createDisabledReason?: string;
  /** Después de cualquier cambio guardado (alta, edición, activación). */
  onChanged?: () => void;
}) {
  const { can } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const formId = useId();
  const { resource } = definition;
  const canEdit = can(definition.editPermission);

  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim());
  const [status, setStatus] = useState<Status>("active");
  const [sort, setSort] = useState(definition.defaultSort ?? "");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [panel, setPanel] = useState<PanelState<T>>(null);
  const [tab, setTab] = useState<"data" | "history">("data");
  const [conflict, setConflict] = useState<T | null>(null);
  const [confirmToggle, setConfirmToggle] = useState(false);

  // La página pertenece a una búsqueda: si cambian los filtros, se vuelve a la primera.
  const filterKey = JSON.stringify({ baseQuery, filters, q, status, sort });
  const [pageState, setPageState] = useState({ key: filterKey, page: 1 });
  const page = pageState.key === filterKey ? pageState.page : 1;
  const setPage = (update: (current: number) => number) => setPageState({ key: filterKey, page: update(page) });
  const query = { ...baseQuery, ...filters, q, status, sort, page, page_size: PAGE_SIZE };

  const list = useQuery({
    queryKey: [resource, "list", query],
    queryFn: () => request<Page<T>>("GET", `/api/v1/${resource}`, { query }),
    placeholderData: keepPreviousData,
  });

  const refresh = useCallback(async () => {
    onChanged?.();
    await queryClient.invalidateQueries({ queryKey: [resource] });
  }, [queryClient, resource, onChanged]);

  const closePanel = useCallback(() => {
    setPanel(null);
    setConflict(null);
    setConfirmToggle(false);
    setTab("data");
  }, []);

  const openEdit = (item: T) => {
    setConflict(null);
    setConfirmToggle(false);
    setTab("data");
    setPanel({ mode: "edit", item });
  };

  const submit = async (values: Record<string, unknown>) => {
    if (!panel) return;
    try {
      if (panel.mode === "create") {
        const created = await request<T>("POST", `/api/v1/${resource}`, { body: values });
        toast.success(`Registro creado: ${definition.rowLabel(created)}.`);
        closePanel();
        definition.onCreated?.(created);
      } else {
        const updated = await request<T>("PATCH", `/api/v1/${resource}/${panel.item.id}`, {
          body: { ...values, row_version: panel.item.row_version },
        });
        toast.success("Cambios guardados.");
        setPanel({ mode: "edit", item: updated });
      }
      await refresh();
    } catch (error) {
      // Conflicto de concurrencia: lo explica el aviso del panel, con el botón para cargar lo vigente.
      if (error instanceof ApiError && error.status === 409 && error.details?.current) {
        setConflict(error.details.current as T);
        return;
      }
      throw error;
    }
  };

  const toggleActive = useMutation({
    mutationFn: (item: T) =>
      request<T>("POST", `/api/v1/${resource}/${item.id}/${item.is_active ? "deactivate" : "activate"}`),
    onSuccess: async (item) => {
      toast.success(item.is_active ? "Registro activado." : "Registro desactivado.");
      setPanel({ mode: "edit", item });
      setConfirmToggle(false);
      await refresh();
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "No se pudo completar la operación."),
  });

  const exportExcel = useMutation({
    mutationFn: () => download(`/api/v1/${resource}/export.xlsx`, { ...baseQuery, ...filters, q, status, sort }),
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "No se pudo exportar."),
  });

  const toggleSort = (key: string) => setSort((current) => (current === key ? `-${key}` : key));

  const data = list.data;
  const items = data?.items ?? [];
  const from = data && data.total ? (data.page - 1) * data.page_size + 1 : 0;
  const to = data ? Math.min(data.page * data.page_size, data.total) : 0;
  const lastPage = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const Form = definition.Form;
  const item = panel?.mode === "edit" ? panel.item : null;
  const filtersActive = !!q || status !== "active" || Object.values(filters).some(Boolean);

  return (
    <div className="mx-auto max-w-6xl animate-fade-up">
      <PageHeader
        title={definition.title}
        actions={
          <>
            <Button variant="secondary" onClick={() => exportExcel.mutate()} loading={exportExcel.isPending}>
              <Download aria-hidden className="size-4" />
              <span className="hidden sm:inline">Exportar</span>
              <span className="sr-only sm:hidden">Exportar a Excel</span>
            </Button>
            {canEdit && (
              <Button
                onClick={() => {
                  closePanel();
                  setPanel({ mode: "create" });
                }}
                disabled={!!createDisabledReason}
                title={createDisabledReason}
              >
                <Plus aria-hidden className="size-4" />
                {definition.newLabel}
              </Button>
            )}
          </>
        }
      />

      {header}

      {/* Barra de búsqueda y filtros */}
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <label className="relative flex-1 sm:min-w-64">
          <span className="sr-only">Buscar</span>
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={definition.searchPlaceholder ?? "Buscar"}
            className="h-11 w-full rounded-lg border border-gray bg-card pl-9 pr-3 text-base text-navy placeholder:text-muted/70 focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/25"
          />
        </label>
        <div className="grid grid-cols-2 gap-2 sm:flex">
          <Select
            label="Estado"
            hideLabel
            value={status}
            onChange={(e) => setStatus(e.target.value as Status)}
            className="sm:w-36"
          >
            <option value="active">Activos</option>
            <option value="inactive">Inactivos</option>
            <option value="all">Todos</option>
          </Select>
          {definition.filters?.map((filter) => (
            <Select
              key={filter.name}
              label={filter.label}
              hideLabel
              value={filters[filter.name] ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, [filter.name]: e.target.value }))}
              className="sm:w-44"
            >
              <option value="">{filter.label}: todos</option>
              {filter.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          ))}
        </div>
      </div>

      {list.isError && (
        <Alert tone="alert" title="No se pudo cargar el listado">
          {list.error instanceof ApiError ? list.error.message : "Revise su conexión e intente nuevamente."}
        </Alert>
      )}

      {list.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          {filtersActive ? (
            <EmptyState icon={SearchX} title="Sin resultados" description="Pruebe con otra búsqueda o cambie los filtros." />
          ) : (
            <EmptyState
              title={`Aún no hay registros en ${definition.title.toLowerCase()}`}
              action={
                canEdit && !createDisabledReason ? (
                  <Button onClick={() => setPanel({ mode: "create" })}>
                    <Plus aria-hidden className="size-4" />
                    {definition.newLabel}
                  </Button>
                ) : undefined
              }
            />
          )}
        </Card>
      ) : (
        <>
          {/* Escritorio: tabla */}
          <Card className={cn("hidden overflow-hidden lg:block", list.isFetching && "opacity-70")}>
            <Table>
              <thead>
                <tr>
                  {definition.columns.map((col) => (
                    <Th key={col.key} numeric={col.numeric} aria-sort={sortState(sort, col.sortKey)}>
                      {col.sortKey ? (
                        <button
                          type="button"
                          onClick={() => toggleSort(col.sortKey!)}
                          className="inline-flex min-h-0 items-center gap-1 hover:text-teal-light"
                        >
                          {col.header}
                          {sort === col.sortKey && <ArrowUp aria-hidden className="size-3.5" />}
                          {sort === `-${col.sortKey}` && <ArrowDown aria-hidden className="size-3.5" />}
                        </button>
                      ) : (
                        col.header
                      )}
                    </Th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <Tr
                    key={row.id}
                    onClick={() => openEdit(row)}
                    className={cn("cursor-pointer", !row.is_active && "text-muted")}
                  >
                    {definition.columns.map((col) => (
                      <Td key={col.key} numeric={col.numeric}>
                        {col.render(row)}
                      </Td>
                    ))}
                  </Tr>
                ))}
              </tbody>
            </Table>
          </Card>

          {/* Celular: tarjetas */}
          <ul className={cn("space-y-2 lg:hidden", list.isFetching && "opacity-70")}>
            {items.map((row) => {
              const card = definition.card(row);
              return (
                <li key={row.id}>
                  <button
                    type="button"
                    onClick={() => openEdit(row)}
                    className="flex w-full flex-col gap-1 rounded-card bg-card p-4 text-left shadow-card active:bg-teal/[0.04]"
                  >
                    <span className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-navy">{card.title}</span>
                      <StatusBadge active={row.is_active} />
                    </span>
                    {card.subtitle && <span className="text-sm text-muted">{card.subtitle}</span>}
                    {card.meta && <span className="text-sm text-navy">{card.meta}</span>}
                  </button>
                </li>
              );
            })}
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

      {/* Panel de alta y edición */}
      <SidePanel
        open={!!panel}
        onClose={closePanel}
        title={item ? definition.rowLabel(item) : definition.newLabel}
        footer={
          tab === "data" && (canEdit || !item) ? (
            <>
              <Button type="submit" form={formId} className="flex-1">
                {item ? "Guardar cambios" : "Crear"}
              </Button>
              <Button variant="secondary" onClick={closePanel}>
                Cancelar
              </Button>
            </>
          ) : undefined
        }
      >
        {item && (
          <div role="tablist" className="mb-4 grid grid-cols-2 rounded-lg bg-bg p-1 text-sm font-semibold">
            {(["data", "history"] as const).map((t) => (
              <button
                key={t}
                role="tab"
                type="button"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                className={cn("h-10 min-h-0 rounded-md", tab === t ? "bg-card text-navy shadow-card" : "text-muted")}
              >
                {t === "data" ? "Datos" : "Historial"}
              </button>
            ))}
          </div>
        )}

        {tab === "history" && item ? (
          <MaintainerHistory resource={resource} id={item.id} fieldLabels={definition.fieldLabels} />
        ) : (
          <div className="space-y-4">
            {conflict && (
              <Alert tone="alert" title="Otro usuario modificó este registro">
                <p>Sus cambios no se guardaron. Cargue los datos actuales y vuelva a aplicarlos.</p>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-2"
                  onClick={() => {
                    setPanel({ mode: "edit", item: conflict });
                    setConflict(null);
                  }}
                >
                  Cargar datos actuales
                </Button>
              </Alert>
            )}
            {item && !item.is_active && <Alert tone="info">Este registro está inactivo.</Alert>}

            <Form
              key={item ? `${item.id}-${item.row_version}` : "new"}
              item={item}
              formId={formId}
              onSubmit={submit}
              readOnly={!canEdit}
            />

            {item && canEdit && definition.ExtraActions && (
              <definition.ExtraActions item={item} onChanged={(changed) => { setPanel({ mode: "edit", item: changed }); void refresh(); }} />
            )}

            {item && canEdit && (definition.canToggleActive?.(item) ?? true) && (
              <div className="border-t border-gray pt-4">
                {confirmToggle ? (
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button
                      variant={item.is_active ? "danger" : "primary"}
                      loading={toggleActive.isPending}
                      onClick={() => toggleActive.mutate(item)}
                    >
                      Confirmar {item.is_active ? "desactivación" : "activación"}
                    </Button>
                    <Button variant="ghost" onClick={() => setConfirmToggle(false)}>
                      No, volver
                    </Button>
                  </div>
                ) : (
                  <Button variant={item.is_active ? "ghostDanger" : "ghostPrimary"} onClick={() => setConfirmToggle(true)}>
                    {item.is_active ? "Desactivar" : "Activar"} {definition.singular}
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
      </SidePanel>
    </div>
  );
}

function sortState(sort: string, key?: string): "ascending" | "descending" | undefined {
  if (!key) return undefined;
  if (sort === key) return "ascending";
  if (sort === `-${key}`) return "descending";
  return undefined;
}
