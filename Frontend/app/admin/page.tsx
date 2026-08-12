"use client";

/**
 * MandiSync ops console — triage agent-intro leads and curate verified
 * commission agents per mandi. Protected by the same X-API-Key as the API.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Loader2, Plus, Save, Trash2 } from "lucide-react";

import { API_BASE_URL, apiHeaders } from "@/lib/types";

type LeadStatus = "pending" | "contacted" | "closed";

type Lead = {
  id: string;
  created_at?: string;
  updated_at?: string;
  status?: LeadStatus | string;
  farmer_name?: string;
  farmer_phone?: string;
  crop_name?: string;
  source_mandi?: string;
  destination_mandi?: string;
  destination_state?: string;
  notes?: string;
  admin_note?: string;
};

type CuratedAgent = {
  name: string;
  phone: string;
  license_id: string;
  notes?: string;
  verified_at?: string;
};

type MandiRow = {
  id: number;
  name: string;
  state: string;
  district: string;
  curated_agents: CuratedAgent[];
  official_contact_count: number;
};

const emptyAgent = (): CuratedAgent => ({
  name: "",
  phone: "",
  license_id: "",
  notes: "",
});

export default function AdminPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [mandis, setMandis] = useState<MandiRow[]>([]);
  const [leadFilter, setLeadFilter] = useState<LeadStatus | "all">("pending");
  const [selectedMandiId, setSelectedMandiId] = useState<number | null>(null);
  const [draftAgents, setDraftAgents] = useState<CuratedAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedMandi = useMemo(
    () => mandis.find((m) => m.id === selectedMandiId) ?? null,
    [mandis, selectedMandiId],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const leadQuery =
        leadFilter === "all" ? "" : `?status=${encodeURIComponent(leadFilter)}`;
      const [leadsRes, mandisRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/admin/leads${leadQuery}`, {
          headers: apiHeaders(),
        }),
        fetch(`${API_BASE_URL}/api/admin/mandis`, { headers: apiHeaders() }),
      ]);

      if (!leadsRes.ok) {
        throw new Error(`Leads API ${leadsRes.status}`);
      }
      if (!mandisRes.ok) {
        throw new Error(`Mandis API ${mandisRes.status}`);
      }

      const leadsData = (await leadsRes.json()) as { leads: Lead[] };
      const mandisData = (await mandisRes.json()) as { mandis: MandiRow[] };
      setLeads(leadsData.leads ?? []);
      setMandis(mandisData.mandis ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, [leadFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!selectedMandi) {
      setDraftAgents([]);
      return;
    }
    setDraftAgents(
      selectedMandi.curated_agents.length > 0
        ? selectedMandi.curated_agents.map((a) => ({ ...a }))
        : [emptyAgent()],
    );
  }, [selectedMandi]);

  async function updateLeadStatus(id: string, status: LeadStatus) {
    setNotice(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/leads/${id}`, {
        method: "PATCH",
        headers: apiHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ status }),
      });
      if (!response.ok) {
        throw new Error(`Update lead failed (${response.status})`);
      }
      setNotice(`Lead marked ${status}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update lead");
    }
  }

  async function saveAgents() {
    if (!selectedMandiId) return;
    setSaving(true);
    setNotice(null);
    setError(null);
    try {
      const cleaned = draftAgents
        .map((a) => ({
          name: a.name.trim(),
          phone: a.phone.trim(),
          license_id: a.license_id.trim(),
          notes: (a.notes ?? "").trim(),
        }))
        .filter((a) => a.name && a.phone && a.license_id);

      const response = await fetch(
        `${API_BASE_URL}/api/admin/mandis/${selectedMandiId}/agents`,
        {
          method: "PUT",
          headers: apiHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ agents: cleaned }),
        },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        throw new Error(payload?.detail ?? `Save failed (${response.status})`);
      }
      setNotice(
        cleaned.length === 0
          ? "Cleared curated agents for this mandi."
          : `Saved ${cleaned.length} verified agent(s). Live routes will show Call/WhatsApp.`,
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save agents");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4 sm:px-6 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-amber-400">
              Ops
            </p>
            <h1 className="font-display mt-1 text-xl text-slate-50 sm:text-2xl">
              MandiSync Admin
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-400">
              Review intro requests and attach verified commission agents.
              Curated agents appear on live routes with Call / WhatsApp.
            </p>
          </div>
          <Link
            href="/"
            className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 transition hover:border-sky-400 hover:text-sky-200"
          >
            ← Farmer dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-6 sm:px-6 md:px-8 lg:grid-cols-2">
        {(error || notice) && (
          <div className="lg:col-span-2">
            {error && (
              <p className="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-100">
                {error}
              </p>
            )}
            {notice && (
              <p className="mt-2 rounded-xl border border-emerald-500/30 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-100">
                {notice}
              </p>
            )}
          </div>
        )}

        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-lg text-slate-50">
              Agent intro leads
            </h2>
            <div className="flex gap-1 rounded-lg border border-slate-700 p-1 text-xs">
              {(["pending", "contacted", "closed", "all"] as const).map(
                (value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setLeadFilter(value)}
                    className={`rounded-md px-2.5 py-1.5 capitalize ${
                      leadFilter === value
                        ? "bg-slate-700 text-white"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {value}
                  </button>
                ),
              )}
            </div>
          </div>

          {loading ? (
            <p className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </p>
          ) : leads.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-700 px-4 py-8 text-sm text-slate-400">
              No leads in this filter. Farmers submit via “Request agent intro”
              on a selected route.
            </p>
          ) : (
            <ul className="space-y-3">
              {leads.map((lead) => (
                <li
                  key={lead.id}
                  className="rounded-xl border border-slate-700/80 bg-slate-900/80 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-slate-50">
                        {lead.farmer_name} · {lead.farmer_phone}
                      </p>
                      <p className="mt-1 text-sm text-slate-400">
                        {lead.crop_name}: {lead.source_mandi} →{" "}
                        {lead.destination_mandi} ({lead.destination_state})
                      </p>
                      {lead.notes && (
                        <p className="mt-2 text-sm text-slate-300">
                          {lead.notes}
                        </p>
                      )}
                      <p className="mt-2 text-[11px] text-slate-500">
                        {lead.created_at
                          ? new Date(lead.created_at).toLocaleString("en-IN")
                          : "—"}{" "}
                        · {lead.status ?? "pending"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {(
                        [
                          ["pending", "Pending"],
                          ["contacted", "Contacted"],
                          ["closed", "Closed"],
                        ] as const
                      ).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => void updateLeadStatus(lead.id, value)}
                          className={`rounded-md px-2 py-1 text-xs ${
                            (lead.status ?? "pending") === value
                              ? "bg-sky-700 text-white"
                              : "border border-slate-600 text-slate-300 hover:border-sky-400"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2 className="font-display mb-3 text-lg text-slate-50">
            Curate verified agents
          </h2>
          <label className="block text-sm text-slate-400">
            Mandi
            <select
              className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
              value={selectedMandiId ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                setSelectedMandiId(value ? Number(value) : null);
              }}
            >
              <option value="">Select a mandi…</option>
              {mandis.map((mandi) => (
                <option key={mandi.id} value={mandi.id}>
                  {mandi.name} ({mandi.state})
                  {mandi.curated_agents.length > 0
                    ? ` · ${mandi.curated_agents.length} curated`
                    : ""}
                </option>
              ))}
            </select>
          </label>

          {!selectedMandi ? (
            <p className="mt-4 rounded-xl border border-dashed border-slate-700 px-4 py-8 text-sm text-slate-400">
              Pick a destination mandi, then add licensed commission agents you
              have verified offline (license ID + phone).
            </p>
          ) : (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-slate-400">
                {selectedMandi.district}, {selectedMandi.state} ·{" "}
                {selectedMandi.official_contact_count} official APMC office
                contact(s) already loaded.
              </p>

              {draftAgents.map((agent, index) => (
                <div
                  key={index}
                  className="rounded-xl border border-slate-700 bg-slate-950/60 p-3"
                >
                  <div className="grid gap-2 sm:grid-cols-2">
                    <input
                      value={agent.name}
                      onChange={(event) => {
                        const next = [...draftAgents];
                        next[index] = { ...agent, name: event.target.value };
                        setDraftAgents(next);
                      }}
                      placeholder="Agent / firm name"
                      className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm"
                    />
                    <input
                      value={agent.phone}
                      onChange={(event) => {
                        const next = [...draftAgents];
                        next[index] = { ...agent, phone: event.target.value };
                        setDraftAgents(next);
                      }}
                      placeholder="Phone"
                      className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm"
                    />
                    <input
                      value={agent.license_id}
                      onChange={(event) => {
                        const next = [...draftAgents];
                        next[index] = {
                          ...agent,
                          license_id: event.target.value,
                        };
                        setDraftAgents(next);
                      }}
                      placeholder="License ID"
                      className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm"
                    />
                    <div className="flex gap-2">
                      <input
                        value={agent.notes ?? ""}
                        onChange={(event) => {
                          const next = [...draftAgents];
                          next[index] = { ...agent, notes: event.target.value };
                          setDraftAgents(next);
                        }}
                        placeholder="Notes (optional)"
                        className="min-w-0 flex-1 rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm"
                      />
                      <button
                        type="button"
                        aria-label="Remove agent"
                        onClick={() =>
                          setDraftAgents(
                            draftAgents.filter((_, i) => i !== index),
                          )
                        }
                        className="rounded-lg border border-slate-600 px-2 text-slate-400 hover:border-rose-400 hover:text-rose-300"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setDraftAgents([...draftAgents, emptyAgent()])}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:border-sky-400"
                >
                  <Plus className="h-4 w-4" />
                  Add agent
                </button>
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => void saveAgents()}
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
                >
                  {saving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  Save verified agents
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
