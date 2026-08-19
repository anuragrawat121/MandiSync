"use client";

/**
 * MandiSync ops console — triage agent-intro leads and curate verified
 * commission agents per mandi. Protected by the same X-API-Key as the API.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Plus, Save, Trash2 } from "lucide-react";

import { apiHeaders } from "@/lib/types";
import {
  apiRoot,
  fetchWithTimeout,
  friendlyApiError,
  wakeApi,
} from "@/lib/apiClient";
import SiteShell from "@/components/SiteShell";

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
      await wakeApi();
      const leadQuery =
        leadFilter === "all" ? "" : `?status=${encodeURIComponent(leadFilter)}`;
      const [leadsRes, mandisRes] = await Promise.all([
        fetchWithTimeout(`${apiRoot()}/api/admin/leads${leadQuery}`, {
          headers: apiHeaders(),
          timeoutMs: 45_000,
        }),
        fetchWithTimeout(`${apiRoot()}/api/admin/mandis`, {
          headers: apiHeaders(),
          timeoutMs: 45_000,
        }),
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
      setError(friendlyApiError(err));
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
      const response = await fetch(`${apiRoot()}/api/admin/leads/${id}`, {
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
        `${apiRoot()}/api/admin/mandis/${selectedMandiId}/agents`,
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
    <SiteShell current="admin">
      <main id="main-content" className="gov-page">
        <p className="gov-kicker">Staff operations</p>
        <h1 className="gov-title">Admin console</h1>
        <p className="gov-lede">
          Review introduction requests and attach verified commission agents.
          Curated agents appear on live corridors with Call and WhatsApp.
        </p>

        <div className="mt-6 grid gap-8 lg:grid-cols-2">
          {(error || notice) && (
            <div className="lg:col-span-2">
              {error && <p className="gov-notice gov-notice-error">{error}</p>}
              {notice && (
                <p className="gov-notice gov-notice-ok mt-2">{notice}</p>
              )}
            </div>
          )}

          <section>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-serif text-lg text-navy-dark">
                Agent intro leads
              </h2>
              <div className="flex border border-[#b7b0a4] text-xs">
                {(["pending", "contacted", "closed", "all"] as const).map(
                  (value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setLeadFilter(value)}
                      className={`border-r border-[#b7b0a4] px-2.5 py-1.5 capitalize last:border-r-0 ${
                        leadFilter === value
                          ? "bg-navy text-white"
                          : "bg-white text-navy hover:bg-[#eef3f8]"
                      }`}
                    >
                      {value}
                    </button>
                  ),
                )}
              </div>
            </div>

            {loading ? (
              <p className="flex items-center gap-2 text-sm text-[var(--muted)]">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading
              </p>
            ) : leads.length === 0 ? (
              <p className="gov-notice border-dashed">
                No leads in this filter. Farmers submit via “Request an
                introduction” on a selected corridor.
              </p>
            ) : (
              <ul className="space-y-2">
                {leads.map((lead) => (
                  <li key={lead.id} className="gov-card p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="font-medium text-navy-dark">
                          {lead.farmer_name} · {lead.farmer_phone}
                        </p>
                        <p className="mt-1 text-sm text-[var(--muted)]">
                          {lead.crop_name}: {lead.source_mandi} →{" "}
                          {lead.destination_mandi} ({lead.destination_state})
                        </p>
                        {lead.notes && (
                          <p className="mt-2 text-sm">{lead.notes}</p>
                        )}
                        <p className="gov-meta mt-2">
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
                            className={
                              (lead.status ?? "pending") === value
                                ? "gov-btn gov-btn-primary px-2 py-1 text-xs"
                                : "gov-btn px-2 py-1 text-xs"
                            }
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
            <h2 className="mb-3 font-serif text-lg text-navy-dark">
              Curate verified agents
            </h2>
            <label className="block">
              <span className="gov-label">Mandi</span>
              <select
                className="gov-select"
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
              <p className="gov-notice mt-4 border-dashed">
                Pick a destination mandi, then add licensed commission agents
                you have verified offline (license ID and phone).
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                <p className="gov-meta">
                  {selectedMandi.district}, {selectedMandi.state} ·{" "}
                  {selectedMandi.official_contact_count} official APMC office
                  contact(s) already loaded.
                </p>

                {draftAgents.map((agent, index) => (
                  <div key={index} className="gov-card p-3">
                    <div className="grid gap-2 sm:grid-cols-2">
                      <input
                        value={agent.name}
                        onChange={(event) => {
                          const next = [...draftAgents];
                          next[index] = { ...agent, name: event.target.value };
                          setDraftAgents(next);
                        }}
                        placeholder="Agent / firm name"
                        className="gov-input text-sm"
                      />
                      <input
                        value={agent.phone}
                        onChange={(event) => {
                          const next = [...draftAgents];
                          next[index] = { ...agent, phone: event.target.value };
                          setDraftAgents(next);
                        }}
                        placeholder="Phone"
                        className="gov-input text-sm"
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
                        className="gov-input text-sm"
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
                          className="gov-input min-w-0 flex-1 text-sm"
                        />
                        <button
                          type="button"
                          aria-label="Remove agent"
                          onClick={() =>
                            setDraftAgents(
                              draftAgents.filter((_, i) => i !== index),
                            )
                          }
                          className="gov-btn px-2 text-[var(--danger)]"
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
                    className="gov-btn"
                  >
                    <Plus className="h-4 w-4" />
                    Add agent
                  </button>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={() => void saveAgents()}
                    className="gov-btn gov-btn-success"
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
    </SiteShell>
  );
}
