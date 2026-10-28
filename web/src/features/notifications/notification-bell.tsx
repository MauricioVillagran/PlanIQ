"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { EmptyState, Skeleton } from "@/components/ui/feedback";
import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";

type Notification = components["schemas"]["NotificationOut"];

const SUMMARY_KEY = ["notifications", "summary"];
const LIST_KEY = ["notifications", "list"];

/**
 * Campana de avisos internos (sección 6): contador por polling, con el intervalo que define el
 * parámetro `notifications.poll_seconds`, y la lista con enlace al plan.
 */
export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const router = useRouter();
  const buttonRef = useRef<HTMLButtonElement>(null);

  const summary = useQuery({
    queryKey: SUMMARY_KEY,
    queryFn: async () => unwrap(await api.GET("/api/v1/notifications/summary")),
    refetchInterval: (query) => (query.state.data?.poll_seconds ?? 60) * 1000,
  });
  const list = useQuery({
    queryKey: LIST_KEY,
    queryFn: async () => unwrap(await api.GET("/api/v1/notifications", { params: { query: { page_size: 20 } } })),
    enabled: open,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });
  const markRead = useMutation({
    mutationFn: async (id: number) =>
      unwrap(await api.POST("/api/v1/notifications/{notification_id}/read", { params: { path: { notification_id: id } } })),
    onSuccess: refresh,
  });
  const markAll = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/notifications/read-all")),
    onSuccess: refresh,
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const unread = summary.data?.unread ?? 0;

  const openNotification = (n: Notification) => {
    if (!n.read_at) markRead.mutate(n.id);
    setOpen(false);
    if (n.link) router.push(n.link);
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={unread ? `Notificaciones: ${unread} sin leer` : "Notificaciones: sin novedades"}
        title="Notificaciones"
        className="relative flex size-11 items-center justify-center rounded-lg text-navy hover:bg-navy/5"
      >
        <Bell aria-hidden className="size-5" />
        {unread > 0 && (
          <span className="num absolute right-1.5 top-1.5 flex min-w-5 items-center justify-center rounded-full bg-coral px-1 text-[11px] font-semibold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open &&
        createPortal(
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)}>
            <div
              role="dialog"
              aria-label="Notificaciones"
              onClick={(e) => e.stopPropagation()}
              className="fixed inset-x-2 top-16 flex max-h-[70vh] flex-col overflow-hidden rounded-card bg-card shadow-xl ring-1 ring-gray/60 sm:left-auto sm:right-4 sm:w-96"
            >
              <div className="flex items-center justify-between gap-2 border-b border-gray/60 px-4 py-2">
                <h2 className="font-semibold text-navy">Notificaciones</h2>
                <div className="flex items-center">
                  {unread > 0 && (
                    <button
                      type="button"
                      onClick={() => markAll.mutate()}
                      className="flex min-h-11 items-center gap-1 rounded-lg px-2 text-sm font-medium text-teal hover:bg-teal/5"
                    >
                      <CheckCheck aria-hidden className="size-4" />
                      Marcar todo leído
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    aria-label="Cerrar"
                    className="flex size-11 items-center justify-center rounded-lg text-muted hover:bg-navy/5"
                  >
                    <X aria-hidden className="size-5" />
                  </button>
                </div>
              </div>
              <div className="overflow-y-auto">
                {list.isPending ? (
                  <div className="space-y-2 p-4">
                    <Skeleton className="h-14" />
                    <Skeleton className="h-14" />
                  </div>
                ) : !list.data?.items.length ? (
                  <EmptyState
                    icon={Bell}
                    title="Sin notificaciones"
                    description="Aquí verá cuando se publique o modifique un plan."
                  />
                ) : (
                  <ul>
                    {list.data.items.map((n) => (
                      <li key={n.id} className="border-b border-gray/40 last:border-0">
                        <button
                          type="button"
                          onClick={() => openNotification(n)}
                          className={cn(
                            "flex w-full gap-3 px-4 py-3 text-left hover:bg-navy/[0.03]",
                            !n.read_at && "bg-teal/[0.04]",
                          )}
                        >
                          <span
                            aria-hidden
                            className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.read_at ? "bg-transparent" : "bg-teal")}
                          />
                          <span className="flex-1">
                            <span className={cn("block text-sm text-navy", !n.read_at && "font-semibold")}>
                              {n.title}
                              {!n.read_at && <span className="sr-only"> (sin leer)</span>}
                            </span>
                            {n.body && <span className="block text-sm text-muted">{n.body}</span>}
                            <span className="num block text-xs text-muted">{formatDateTime(n.created_at)}</span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
