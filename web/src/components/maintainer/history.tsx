"use client";

import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";

import { EmptyState, Skeleton } from "@/components/ui/feedback";
import { request } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";

import type { Page } from "./types";

type AuditEntry = {
  id: number;
  occurred_at: string;
  username: string | null;
  action: string;
  changes: Record<string, unknown>;
};

// Marcas de tiempo ISO (por ejemplo password_changed_at): se muestran en hora de la planta.
const ISO_INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

export const ACTION_VERBS: Record<string, string> = {
  create: "Creó",
  update: "Modificó",
  deactivate: "Desactivó",
  activate: "Activó",
  delete: "Eliminó",
};

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (value === true) return "Sí";
  if (value === false) return "No";
  if (typeof value === "string" && ISO_INSTANT.test(value)) return formatDateTime(value);
  return String(value);
}

function refs(list: unknown): string {
  if (!Array.isArray(list)) return "";
  return list
    .map((r: Record<string, unknown>) => String(r.code ?? r.username ?? r.name ?? r.id))
    .join(", ");
}

function ChangeLine({ change, label }: { change: unknown; label: string }) {
  const c = (change ?? {}) as Record<string, unknown>;
  if ("added" in c || "removed" in c) {
    return (
      <li>
        <span className="font-medium">{label}</span>
        {refs(c.added) && <span className="text-teal"> + {refs(c.added)}</span>}
        {refs(c.removed) && <span className="text-coral"> − {refs(c.removed)}</span>}
      </li>
    );
  }
  return (
    <li>
      <span className="font-medium">{label}</span>:{" "}
      {"old" in c && <span className="text-muted line-through decoration-coral/60">{show(c.old)}</span>}
      {"old" in c && " → "}
      <span>{show(c.new)}</span>
    </li>
  );
}

/** Cambios campo a campo de una entrada de auditoría (valor anterior tachado → valor nuevo). */
export function ChangeList({
  changes,
  fieldLabels = {},
  limit,
}: {
  changes: Record<string, unknown>;
  fieldLabels?: Record<string, string>;
  /** Muestra solo los primeros campos y cuántos faltan. */
  limit?: number;
}) {
  const fields = Object.entries(changes).filter(([field]) => field !== "id");
  const shown = limit ? fields.slice(0, limit) : fields;
  return (
    <ul className="space-y-0.5 text-navy [overflow-wrap:anywhere]">
      {shown.map(([field, change]) => (
        <ChangeLine key={field} change={change} label={fieldLabels[field] ?? field} />
      ))}
      {shown.length < fields.length && (
        <li className="text-muted">
          y {fields.length - shown.length} {fields.length - shown.length === 1 ? "campo" : "campos"} más
        </li>
      )}
    </ul>
  );
}

/** Pestaña Historial: quién cambió qué y cuándo (auditoría central). */
export function MaintainerHistory({
  resource,
  id,
  fieldLabels = {},
}: {
  resource: string;
  id: number;
  fieldLabels?: Record<string, string>;
}) {
  const history = useQuery({
    queryKey: [resource, id, "history"],
    queryFn: () => request<Page<AuditEntry>>("GET", `/api/v1/${resource}/${id}/history`, { query: { page_size: 100 } }),
  });

  if (history.isPending) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-16" />
        <Skeleton className="h-16" />
      </div>
    );
  }
  if (!history.data?.items.length) {
    return <EmptyState icon={History} title="Sin cambios registrados" />;
  }
  return (
    <ol className="space-y-3">
      {history.data.items.map((entry) => (
        <li key={entry.id} className="rounded-lg border border-gray/80 p-3 text-sm">
          <p className="mb-1 flex flex-wrap justify-between gap-x-2 text-xs text-muted">
            <span>
              <span className="font-semibold text-navy">{ACTION_VERBS[entry.action] ?? entry.action}</span>{" "}
              {entry.username ?? "Sistema"}
            </span>
            <span className="num">{formatDateTime(entry.occurred_at)}</span>
          </p>
          <ChangeList changes={entry.changes} fieldLabels={fieldLabels} />
        </li>
      ))}
    </ol>
  );
}
