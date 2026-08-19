/** Session helpers for the static GitHub Pages SPA. */

const STORAGE_KEY = "mandisync.session";

export type UserRole = "user" | "admin";

export type AuthSession = {
  token: string;
  username: string;
  role: UserRole;
  expiresAt: string;
};

function appBase(): string {
  return process.env.NEXT_PUBLIC_BASE_PATH || "";
}

export function loginPath(): string {
  return `${appBase()}/login/`;
}

export function registerPath(): string {
  return `${appBase()}/register/`;
}

export function homePath(): string {
  return `${appBase()}/`;
}

export function readSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed.token || !parsed.username || !parsed.role) return null;
    if (parsed.expiresAt && Date.parse(parsed.expiresAt) <= Date.now()) {
      clearSession();
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeSession(session: AuthSession): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

export function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const next = window.location.pathname.endsWith("/login/")
    ? ""
    : window.location.pathname.endsWith("/login")
      ? ""
      : "";
  void next;
  window.location.href = loginPath();
}
