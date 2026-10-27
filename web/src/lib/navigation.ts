import { Home, UserRound, type LucideIcon } from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Permiso necesario para ver el ítem; sin permiso no se muestra (la API valida igual). */
  permission?: string;
};

/** Cada fase agrega aquí sus módulos (Configuración en F0.9, Planificación en la Fase 1...). */
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Inicio", icon: Home },
  { href: "/profile", label: "Perfil", icon: UserRound },
];
