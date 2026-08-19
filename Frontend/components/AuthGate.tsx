"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { ready, session } = useAuth();
  const isLogin = pathname === "/login" || pathname === "/login/";
  const isRegister = pathname === "/register" || pathname === "/register/";
  const isPublic = isLogin || isRegister;
  const isAdmin = pathname === "/admin" || pathname === "/admin/";

  useEffect(() => {
    if (!ready) return;
    if (!session && !isPublic) {
      router.replace("/register");
      return;
    }
    if (session && isPublic) {
      router.replace(session.role === "admin" ? "/admin" : "/");
      return;
    }
    if (session && isAdmin && session.role !== "admin") {
      router.replace("/");
    }
  }, [ready, session, isPublic, isAdmin, router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--paper)] text-sm text-[var(--muted)]">
        Loading session…
      </div>
    );
  }

  if (!session && !isPublic) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--paper)] text-sm text-[var(--muted)]">
        Redirecting to registration…
      </div>
    );
  }

  if (session && isAdmin && session.role !== "admin") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--paper)] text-sm text-[var(--muted)]">
        Administrator access required.
      </div>
    );
  }

  return <>{children}</>;
}
