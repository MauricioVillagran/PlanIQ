"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** Diálogo modal centrado (sobre el panel lateral). Se cierra solo con sus botones. */
export function Dialog({
  open,
  title,
  children,
  actions,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  actions: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) ref.current?.querySelector<HTMLElement>("button")?.focus();
  }, [open]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-navy/50 p-4 sm:items-center">
      <div
        ref={ref}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className="w-full max-w-sm rounded-card bg-card p-5 shadow-xl animate-fade-up"
      >
        <h2 id="dialog-title" className="mb-2 font-semibold text-navy">
          {title}
        </h2>
        <div className="mb-4 space-y-2 text-sm text-navy">{children}</div>
        <div className="flex flex-col gap-2 sm:flex-row-reverse">{actions}</div>
      </div>
    </div>,
    document.body,
  );
}
