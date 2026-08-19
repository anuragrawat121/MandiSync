"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { apiRoot, fetchWithTimeout, wakeApi } from "@/lib/apiClient";
import {
  clearSession,
  readSession,
  writeSession,
  type AuthSession,
  type UserRole,
} from "@/lib/auth";

type AuthContextValue = {
  ready: boolean;
  session: AuthSession | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<AuthSession | null>(null);

  useEffect(() => {
    setSession(readSession());
    setReady(true);
  }, []);

  const applySession = useCallback((payload: {
    access_token?: string;
    username?: string;
    role?: UserRole;
    expires_at?: string;
    detail?: string;
  } | null, response: Response, failedLabel: string) => {
    if (!response.ok) {
      const detail = payload?.detail;
      const message =
        typeof detail === "string" ? detail : `${failedLabel} (${response.status})`;
      throw new Error(message);
    }
    if (!payload?.access_token || !payload.username || !payload.role) {
      throw new Error("Sign-in response was incomplete.");
    }
    const next: AuthSession = {
      token: payload.access_token,
      username: payload.username,
      role: payload.role,
      expiresAt: payload.expires_at ?? "",
    };
    writeSession(next);
    setSession(next);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await wakeApi();
    const response = await fetchWithTimeout(`${apiRoot()}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      timeoutMs: 45_000,
      body: JSON.stringify({ username, password }),
    });
    const payload = (await response.json().catch(() => null)) as {
      access_token?: string;
      username?: string;
      role?: UserRole;
      expires_at?: string;
      detail?: string;
    } | null;
    applySession(payload, response, "Sign-in failed");
  }, [applySession]);

  const register = useCallback(async (username: string, password: string) => {
    await wakeApi();
    const response = await fetchWithTimeout(`${apiRoot()}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      timeoutMs: 45_000,
      body: JSON.stringify({ username, password }),
    });
    const payload = (await response.json().catch(() => null)) as {
      access_token?: string;
      username?: string;
      role?: UserRole;
      expires_at?: string;
      detail?: string;
    } | null;
    applySession(payload, response, "Registration failed");
  }, [applySession]);

  const logout = useCallback(() => {
    clearSession();
    setSession(null);
  }, []);

  const value = useMemo(
    () => ({ ready, session, login, register, logout }),
    [ready, session, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return value;
}
