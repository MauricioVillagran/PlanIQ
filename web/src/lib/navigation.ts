import { Home, Settings, UserRound, type LucideIcon } from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Permisos que habilitan el ítem (basta uno); sin permiso no se muestra (la API valida igual). */
  anyPermission?: string[];
};

/** Cada fase agrega aquí sus módulos (Planificación en la Fase 1...). */
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Inicio", icon: Home },
  { href: "/settings", label: "Configuración", icon: Settings, anyPermission: ["masters.view", "users.admin"] },
  { href: "/profile", label: "Perfil", icon: UserRound },
];
