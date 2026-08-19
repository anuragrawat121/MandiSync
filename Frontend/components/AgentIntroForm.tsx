"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { apiHeaders, type ArbitrageRoute } from "@/lib/types";
import { apiRoot } from "@/lib/apiClient";

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
      const response = await fetch(`${apiRoot()}/api/leads/agent-intro`, {
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
      className="gov-card mt-4 p-4"
    >
      <fieldset>
        <legend className="gov-kicker">Request an introduction</legend>
        <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">
          No verified commission agent listed yet? Leave your number and we will
          queue a follow-up for {route.destination_mandi}.
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="gov-label">Your name</span>
            <input
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="gov-input"
              placeholder="Ram Singh"
              maxLength={128}
            />
          </label>
          <label className="block text-sm">
            <span className="gov-label">Mobile number</span>
            <input
              required
              type="tel"
              inputMode="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className="gov-input"
              placeholder="9876543210"
              maxLength={20}
            />
          </label>
        </div>

        <label className="mt-3 block text-sm">
          <span className="gov-label">Notes (optional)</span>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={2}
            maxLength={500}
            placeholder="Approx. quintals, arrival date, preferred language"
            className="gov-textarea"
          />
        </label>

        <button
          type="submit"
          disabled={formState === "submitting"}
          className="gov-btn gov-btn-primary mt-4"
        >
          {formState === "submitting" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : null}
          Submit request
        </button>

        {feedback && (
          <p
            className={`mt-3 text-sm ${
              formState === "success" ? "text-[var(--green)]" : "text-[var(--danger)]"
            }`}
          >
            {feedback}
          </p>
        )}
      </fieldset>
    </form>
  );
}
