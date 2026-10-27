import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-card bg-card shadow-card", className)} {...props} />;
}

export function CardHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-gray/70 px-4 py-3 sm:px-5">
      <div>
        <h2 className="font-semibold text-navy">{title}</h2>
        {description && <p className="text-sm text-muted">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

/** Cifra destacada (pocas cifras grandes en la vista de supervisor). Coral solo para desvíos. */
export function KpiCard({
  label,
  value,
  unit,
  tone = "ok",
  hint,
}: {
  label: string;
  value: string;
  unit?: string;
  tone?: "ok" | "alert" | "neutral";
  hint?: string;
}) {
  const border = tone === "alert" ? "border-l-coral" : tone === "ok" ? "border-l-teal" : "border-l-blue-mid";
  return (
    <Card className={cn("flex flex-col gap-1 border-l-4 px-4 py-3 animate-fade-up", border)}>
      <span className="text-xs font-medium uppercase tracking-wider text-muted">{label}</span>
      <span className="num text-2xl text-navy">
        {value}
        {unit && <span className="ml-1 text-sm text-muted">{unit}</span>}
      </span>
      {hint && <span className={cn("text-xs", tone === "alert" ? "text-coral" : "text-muted")}>{hint}</span>}
    </Card>
  );
}
