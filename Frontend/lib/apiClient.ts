/** Timed fetch helpers for the GitHub Pages → Render free-tier path. */

import { API_BASE_URL } from "@/lib/types";

export class ApiTimeoutError extends Error {
  constructor(
    message = "The API took too long to respond. The free server may still be waking up.",
  ) {
    super(message);
    this.name = "ApiTimeoutError";
  }
}

export function apiRoot(): string {
  return API_BASE_URL.replace(/\/$/, "");
}

export function friendlyApiError(err: unknown): string {
  if (err instanceof ApiTimeoutError) {
    return err.message;
  }
  if (err instanceof DOMException && err.name === "AbortError") {
    return "Request cancelled.";
  }
  const message = err instanceof Error ? err.message : "";
  if (
    message === "Failed to fetch" ||
    message.includes("NetworkError") ||
    message.includes("Load failed")
  ) {
    return "Cannot reach the API. The free server may be sleeping, paused, or still starting. Tap retry.";
  }
  return message || "Unable to load data from the API.";
}

export async function fetchWithTimeout(
  url: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  const { timeoutMs = 90_000, signal, ...rest } = init;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }

  try {
    return await fetch(url, { ...rest, signal: controller.signal, cache: "no-store" });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      if (timedOut) {
        throw new ApiTimeoutError();
      }
      throw err;
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/** Hit /health first so Render can wake before the heavier arbitrage query. */
export async function wakeApi(signal?: AbortSignal): Promise<void> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const response = await fetchWithTimeout(`${apiRoot()}/health`, {
        timeoutMs: 90_000,
        signal,
      });
      if (response.ok) {
        return;
      }
      lastError = new Error(`API health ${response.status}`);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw err;
      }
      lastError = err;
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new ApiTimeoutError("Unable to wake the API.");
}
