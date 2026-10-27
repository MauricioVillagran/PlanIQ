import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

import { Spinner } from "./feedback";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "sm";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-teal text-white hover:bg-[#00818a] disabled:bg-teal/50",
  secondary: "bg-card text-navy border border-gray hover:border-teal hover:text-teal disabled:opacity-50",
  ghost: "text-navy hover:bg-navy/5 disabled:opacity-50",
  // Coral se reserva para acciones destructivas o de alerta.
  danger: "bg-coral text-white hover:bg-[#e85e4b] disabled:bg-coral/50",
};

const SIZES: Record<Size, string> = {
  md: "h-11 px-4 text-sm",
  sm: "h-11 px-3 text-sm sm:h-9 sm:min-h-0",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, className, children, disabled, type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors",
        "disabled:cursor-not-allowed",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {loading && <Spinner className="size-4" />}
      {children}
    </button>
  );
});
