import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const CONTROL =
  "w-full rounded-lg border bg-card px-3 text-base text-navy placeholder:text-muted/70 " +
  "focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/25 disabled:bg-bg disabled:text-muted";

/** Etiqueta, ayuda y error de un campo. El error usa el mensaje que devuelve la API. */
export function Field({
  label,
  hint,
  error,
  required,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  htmlFor: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium text-navy">
        {label}
        {required && <span className="ml-0.5 text-coral">*</span>}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-sm text-coral">
          {error}
        </p>
      ) : (
        hint && <p className="text-xs text-muted">{hint}</p>
      )}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string };

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, id, className, required, ...props },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  return (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId}>
      <input
        ref={ref}
        id={inputId}
        required={required}
        aria-invalid={!!error || undefined}
        aria-describedby={error ? `${inputId}-error` : undefined}
        className={cn(CONTROL, "h-11", error ? "border-coral" : "border-gray", className)}
        {...props}
      />
    </Field>
  );
});

/**
 * Número con coma decimal y teclado numérico en el celular. Trabaja con texto: convertir con
 * parseDecimalInput antes de enviar a la API.
 */
export const NumberInput = forwardRef<HTMLInputElement, InputProps & { decimals?: boolean }>(function NumberInput(
  { decimals = true, className, ...props },
  ref,
) {
  return (
    <Input
      ref={ref}
      type="text"
      inputMode={decimals ? "decimal" : "numeric"}
      autoComplete="off"
      className={cn("num text-right", className)}
      {...props}
    />
  );
});

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  hint?: string;
  error?: string;
  hideLabel?: boolean;
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, id, className, required, hideLabel, children, ...props },
  ref,
) {
  const autoId = useId();
  const selectId = id ?? autoId;
  const control = (
    <select
      ref={ref}
      id={selectId}
      required={required}
      aria-invalid={!!error || undefined}
      aria-label={hideLabel ? label : undefined}
      className={cn(CONTROL, "h-11 pr-8", error ? "border-coral" : "border-gray", className)}
      {...props}
    >
      {children}
    </select>
  );
  if (hideLabel) return control;
  return (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={selectId}>
      {control}
    </Field>
  );
});
