"use client";

import { useState } from "react";
import { Loader2, Send } from "lucide-react";

import { API_BASE_URL, apiHeaders, type ArbitrageRoute } from "@/lib/types";

type Props = {
  route: ArbitrageRoute;
};

type FormState = "idle" | "submitting" | "success" | "error";

export default function AgentIntroForm({ route }: Props) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [formState, setFormState] = useState<FormState>("idle");
  const [feedback, setFeedback] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormState("submitting");
    setFeedback("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/leads/agent-intro`, {
        method: "POST",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          farmer_name: name.trim(),
          farmer_phone: phone.trim(),
          crop_name: route.crop_name,
          source_mandi: route.source_mandi,
          destination_mandi: route.destination_mandi,
          destination_state: route.destination_state,
          notes: notes.trim(),
        }),
      });

      const data = (await response.json()) as { message?: string; detail?: string };
      if (!response.ok) {
        throw new Error(data.detail ?? data.message ?? `Error ${response.status}`);
      }

      setFormState("success");
      setFeedback(
        data.message ??
          "Request received. We will follow up when a verified agent is available.",
      );
      setName("");
      setPhone("");
      setNotes("");
    } catch (err) {
      setFormState("error");
      setFeedback(
        err instanceof Error ? err.message : "Could not submit request. Try again.",
      );
    }
  }

  return (
    <form
      onSubmit={(event) => void handleSubmit(event)}
      className="mt-4 rounded-xl border border-slate-700/80 bg-slate-900/60 p-4"
    >
      <p className="text-xs uppercase tracking-[0.16em] text-sky-400">
        Request agent intro
      </p>
      <p className="mt-1 text-sm leading-relaxed text-slate-400">
        No verified commission agent listed yet? Leave your number and we will
        queue a partner follow-up for{" "}
        <span className="text-slate-200">{route.destination_mandi}</span>.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="text-slate-400">Your name</span>
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100 outline-none ring-sky-400/0 focus:border-sky-400 focus:ring-2 focus:ring-sky-400/30"
            placeholder="Ram Singh"
            maxLength={128}
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-400">Mobile number</span>
          <input
            required
            type="tel"
            inputMode="tel"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-400/30"
            placeholder="9876543210"
            maxLength={20}
          />
        </label>
      </div>

      <label className="mt-3 block text-sm">
        <span className="text-slate-400">Notes (optional)</span>
        <textarea
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          rows={2}
          maxLength={500}
          placeholder="Approx. quintals, arrival date, preferred language…"
          className="mt-1 w-full resize-none rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-400/30"
        />
      </label>

      <button
        type="submit"
        disabled={formState === "submitting"}
        className="mt-4 inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {formState === "submitting" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
        Request intro at destination
      </button>

      {feedback && (
        <p
          className={`mt-3 text-sm ${
            formState === "success" ? "text-emerald-300" : "text-amber-200"
          }`}
        >
          {feedback}
        </p>
      )}
    </form>
  );
}
