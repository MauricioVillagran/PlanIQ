"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Brand } from "@/components/brand";
import { NotificationBell } from "@/features/notifications/notification-bell";
import { useAppContext } from "@/lib/app-context";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { NAV_ITEMS } from "@/lib/navigation";

import { ContextBar } from "./context-bar";

function useNavItems() {
  const { can } = useAuth();
  return NAV_ITEMS.filter((item) => !item.anyPermission || item.anyPermission.some(can));
}

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function UserMenu() {
  const { me, logout } = useAuth();
  if (!me) return null;
  return (
    <div className="hidden items-center gap-2 lg:flex">
      <div className="text-right leading-tight">
        <p className="text-sm font-semibold text-navy">{me.full_name}</p>
        <p className="text-xs text-muted">{me.roles.map((r) => r.name).join(", ") || "Sin rol"}</p>
      </div>
      <button
        type="button"
        onClick={() => logout()}
        aria-label="Salir"
        title="Salir"
        className="flex size-11 items-center justify-center rounded-lg text-navy hover:bg-navy/5"
      >
        <LogOut aria-hidden className="size-5" />
      </button>
    </div>
  );
}

function SideNav() {
  const pathname = usePathname();
  const { href } = useAppContext();
  return (
    <nav aria-label="Principal" className="hidden w-60 shrink-0 flex-col gap-1 bg-navy px-3 py-4 lg:flex">
      <div className="mb-6 px-2">
        <span className="inline-flex rounded-lg bg-white px-2 py-1">
          <Brand />
        </span>
      </div>
      {useNavItems().map(({ href: path, label, icon: Icon }) => (
        <Link
          key={path}
          href={href(path)}
          aria-current={isActive(pathname, path) ? "page" : undefined}
          className={cn(
            "flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white",
            isActive(pathname, path) && "bg-teal text-white hover:bg-teal",
          )}
        >
          <Icon aria-hidden className="size-5" />
          {label}
        </Link>
      ))}
    </nav>
  );
}

function BottomNav() {
  const pathname = usePathname();
  const { href } = useAppContext();
  const items = useNavItems();
  return (
    <nav
      aria-label="Principal"
      className="fixed inset-x-0 bottom-0 z-40 grid border-t border-gray bg-card pb-[env(safe-area-inset-bottom)] lg:hidden"
      style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}
    >
      {items.map(({ href: path, label, icon: Icon }) => {
        const active = isActive(pathname, path);
        return (
          <Link
            key={path}
            href={href(path)}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-14 flex-col items-center justify-center gap-0.5 text-xs font-medium",
              active ? "text-teal" : "text-muted",
            )}
          >
            <Icon aria-hidden className="size-5" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh">
      <SideNav />
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Un solo selector de contexto: debajo de la marca en celular, en la misma fila en escritorio. */}
        <header className="sticky top-0 z-30 flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-gray bg-card/95 px-4 py-2 backdrop-blur">
          <Brand className="order-1 lg:hidden" />
          <div className="order-2 ml-auto flex items-center gap-1 lg:order-3">
            <NotificationBell />
            <UserMenu />
          </div>
          <ContextBar className="order-3 w-full pb-1 lg:order-2 lg:w-auto lg:flex-1 lg:pb-0" />
        </header>
        <main className="flex-1 px-4 pb-24 pt-4 lg:px-8 lg:pb-8">{children}</main>
      </div>
      <BottomNav />
    </div>
  );
}
