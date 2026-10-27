import { cn } from "@/lib/cn";

/** Marca de la aplicación: tres barras que crecen (plan → avance → cumplimiento). */
export function Brand({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-bold text-navy", className)}>
      <svg viewBox="0 0 24 24" aria-hidden className="size-7 shrink-0">
        <rect x="2" y="13" width="5" height="9" rx="1.5" fill="#80CAD0" />
        <rect x="9.5" y="8" width="5" height="14" rx="1.5" fill="#0096A0" />
        <rect x="17" y="3" width="5" height="19" rx="1.5" fill="#324664" />
      </svg>
      {!compact && (
        <span className="text-xl tracking-tight">
          Plan<span className="text-teal">IQ</span>
        </span>
      )}
    </span>
  );
}
