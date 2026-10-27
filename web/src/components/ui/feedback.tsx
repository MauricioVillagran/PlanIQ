import { AlertTriangle, CheckCircle2, Info, Loader2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 aria-hidden className={cn("animate-spin", className ?? "size-5")} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-md bg-gray/60", className)} />;
}

/** Estado vacío con acción sugerida (sección 9). */
export function EmptyState({
  icon: Icon = Info,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-teal-soft text-teal">
        <Icon aria-hidden className="size-6" />
      </span>
      <p className="font-semibold text-navy">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted">{description}</p>}
      {action}
    </div>
  );
}

type Tone = "info" | "success" | "alert";

const TONES: Record<Tone, { box: string; icon: LucideIcon }> = {
  info: { box: "border-blue-mid/40 bg-blue-mid/10 text-navy", icon: Info },
  success: { box: "border-teal/40 bg-teal-soft text-navy", icon: CheckCircle2 },
  alert: { box: "border-coral/50 bg-coral-soft text-navy", icon: AlertTriangle },
};

export function Alert({ tone = "info", title, children }: { tone?: Tone; title?: string; children?: ReactNode }) {
  const { box, icon: Icon } = TONES[tone];
  return (
    <div role={tone === "alert" ? "alert" : "status"} className={cn("flex gap-3 rounded-lg border p-3 text-sm", box)}>
      <Icon aria-hidden className={cn("mt-0.5 size-5 shrink-0", tone === "alert" ? "text-coral" : "text-teal")} />
      <div className="space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children}
      </div>
    </div>
  );
}

type BadgeTone = "ok" | "alert" | "neutral" | "info";

const BADGES: Record<BadgeTone, string> = {
  ok: "bg-teal-soft text-teal",
  alert: "bg-coral-soft text-coral",
  neutral: "bg-gray/50 text-navy",
  info: "bg-blue-mid/15 text-navy",
};

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", BADGES[tone])}>
      {children}
    </span>
  );
}
