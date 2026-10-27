"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, unwrap, type Schemas } from "@/lib/api/client";
import { onSessionExpired, refreshSession, setAccessToken } from "@/lib/api/session";

export type Me = Schemas["MeResponse"];

type AuthState =
  | { status: "loading"; me: null }
  | { status: "anonymous"; me: null }
  | { status: "authenticated"; me: Me };

type AuthContextValue = AuthState & {
  login: (username: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<Me>;
  can: (permission: string) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchMe(): Promise<Me> {
  return unwrap(await api.GET("/api/v1/auth/me"));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ status: "loading", me: null });

  const becomeAnonymous = useCallback(() => {
    setAccessToken(null);
    queryClient.clear();
    setState({ status: "anonymous", me: null });
  }, [queryClient]);

  // Al cargar la app se intenta recuperar la sesión con la cookie de refresco.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ok = await refreshSession();
      if (cancelled) return;
      if (!ok) return setState({ status: "anonymous", me: null });
      try {
        const me = await fetchMe();
        if (!cancelled) setState({ status: "authenticated", me });
      } catch {
        if (!cancelled) setState({ status: "anonymous", me: null });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => onSessionExpired(becomeAnonymous), [becomeAnonymous]);

  const login = useCallback(async (username: string, password: string) => {
    const tokens = unwrap(await api.POST("/api/v1/auth/login", { body: { username, password } }));
    setAccessToken(tokens.access_token);
    const me = await fetchMe();
    setState({ status: "authenticated", me });
    return me;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.POST("/api/v1/auth/logout");
    } finally {
      becomeAnonymous();
    }
  }, [becomeAnonymous]);

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    const tokens = unwrap(
      await api.POST("/api/v1/auth/change-password", {
        body: { current_password: currentPassword, new_password: newPassword },
      }),
    );
    setAccessToken(tokens.access_token);
    const me = await fetchMe();
    setState({ status: "authenticated", me });
    return me;
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      login,
      logout,
      changePassword,
      // Solo oculta acciones en la interfaz: la API valida siempre los permisos.
      can: (permission: string) => state.me?.permissions.includes(permission) ?? false,
    }),
    [state, login, logout, changePassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return context;
}
