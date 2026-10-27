/** Solo se redirige a rutas internas: evita usar ?next= para mandar al usuario a otro sitio. */
export function safeNext(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return "/";
  if (value.startsWith("/login") || value.startsWith("/change-password")) return "/";
  return value;
}
