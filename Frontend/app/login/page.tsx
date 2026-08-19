"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import GovMark from "@/components/GovMark";
import { friendlyApiError } from "@/lib/apiClient";

export default function LoginPage() {
  const { login, session } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(friendlyApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--paper)] text-sm text-[var(--muted)]">
        Signed in. Opening your workspace…
      </div>
    );
  }

  return (
    <div className="gov-root">
      <div className="gov-tricolor" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="gov-card w-full max-w-md p-6"
        >
          <div className="mb-4 flex items-center gap-3">
            <GovMark />
            <div>
              <p className="gov-kicker">MandiSync</p>
              <h1 className="font-serif text-xl text-navy-dark">Sign in</h1>
            </div>
          </div>
          <p className="text-sm leading-relaxed text-[var(--muted)]">
            Farmer accounts open crop corridors. Administrator accounts also
            open the operations console.
          </p>

          <label className="mt-5 block">
            <span className="gov-label">Username</span>
            <input
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="gov-input"
            />
          </label>
          <label className="mt-3 block">
            <span className="gov-label">Password</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="gov-input"
            />
          </label>

          {error && (
            <p className="gov-notice gov-notice-error mt-4">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="gov-btn gov-btn-primary mt-5 w-full"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Continue
          </button>

          <p className="mt-4 text-center text-sm text-[var(--muted)]">
            New here?{" "}
            <Link href="/register" className="font-medium text-navy underline">
              Create an account first
            </Link>
          </p>
        </form>
      </main>
    </div>
  );
}
