"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import GovMark from "@/components/GovMark";
import { friendlyApiError } from "@/lib/apiClient";

export default function RegisterPage() {
  const { register, session } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await register(username.trim(), password);
    } catch (err) {
      setError(friendlyApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--paper)] text-sm text-[var(--muted)]">
        Account created. Opening your workspace…
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
              <h1 className="font-serif text-xl text-navy-dark">
                Create your account
              </h1>
            </div>
          </div>
          <p className="text-sm leading-relaxed text-[var(--muted)]">
            Register first to open crop corridors for your FPO. New accounts
            are farmer access only. Operations console logins are issued
            separately.
          </p>

          <label className="mt-5 block">
            <span className="gov-label">Username</span>
            <input
              autoComplete="username"
              required
              minLength={3}
              maxLength={32}
              pattern="[A-Za-z][A-Za-z0-9_]{2,31}"
              title="Start with a letter. Use 3–32 letters, numbers, or underscores."
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="gov-input"
            />
          </label>
          <label className="mt-3 block">
            <span className="gov-label">Password</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="gov-input"
            />
          </label>
          <label className="mt-3 block">
            <span className="gov-label">Confirm password</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
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
            Register
          </button>

          <p className="mt-4 text-center text-sm text-[var(--muted)]">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-navy underline">
              Sign in
            </Link>
          </p>
        </form>
      </main>
    </div>
  );
}
