"use client";

import { CheckCircle2, AlertTriangle, X } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type Toast = { id: number; tone: "success" | "alert"; message: string };
type ToastApi = { success: (message: string) => void; error: (message: string) => void };

const ToastContext = createContext<ToastApi | null>(null);

/** Avisos breves de resultado ("Planta guardada"). Se apilan sobre la navegación inferior en celular. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((tone: Toast["tone"], message: string) => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, tone, message }]);
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), tone === "alert" ? 7000 : 3500);
  }, []);

  const value: ToastApi = {
    success: useCallback((m: string) => push("success", m), [push]),
    error: useCallback((m: string) => push("alert", m), [push]),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 lg:bottom-6 lg:items-end lg:px-6"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.tone === "alert" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex w-full max-w-sm items-start gap-2 rounded-lg border bg-card p-3 text-sm shadow-card animate-fade-up",
              toast.tone === "alert" ? "border-coral/60" : "border-teal/50",
            )}
          >
            {toast.tone === "alert" ? (
              <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-coral" />
            ) : (
              <CheckCircle2 aria-hidden className="mt-0.5 size-4 shrink-0 text-teal" />
            )}
            <p className="flex-1 text-navy">{toast.message}</p>
            <button
              type="button"
              aria-label="Cerrar aviso"
              onClick={() => setToasts((current) => current.filter((t) => t.id !== toast.id))}
              className="-m-1 flex size-6 min-h-0 items-center justify-center rounded text-muted hover:text-navy"
            >
              <X aria-hidden className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast debe usarse dentro de ToastProvider");
  return context;
}
