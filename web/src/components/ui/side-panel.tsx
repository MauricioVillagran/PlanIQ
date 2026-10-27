"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Panel lateral para crear y editar (sección 5.1): a la derecha en escritorio, pantalla completa en
 * celular. Se cierra con Escape o el botón; mantiene el foco dentro mientras está abierto.
 */
export function SidePanel({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previous?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  // Portal al body: un ancestro con transform (animaciones) haría que "fixed" se ubique dentro de él.
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end">
      <button aria-label="Cerrar panel" className="absolute inset-0 bg-navy/40" onClick={onClose} tabIndex={-1} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="side-panel-title"
        className="relative flex h-full w-full flex-col bg-card shadow-xl sm:max-w-md"
      >
        <header className="flex items-center justify-between gap-3 border-b border-gray px-4 py-2">
          <h2 id="side-panel-title" className="font-semibold text-navy">
            {title}
          </h2>
          <button
            onClick={onClose}
            aria-label="Cerrar"
            className="flex size-11 items-center justify-center rounded-lg text-navy hover:bg-navy/5"
          >
            <X aria-hidden className="size-5" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-4">{children}</div>
        {footer && (
          <footer className="flex gap-2 border-t border-gray px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            {footer}
          </footer>
        )}
      </div>
    </div>,
    document.body,
  );
}
