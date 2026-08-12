"use client";

/**
 * MandiSync Farmer-First arbitrage dashboard.
 * Phone-first scrolling layout: filters + routes, then map + corridor details.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Loader2,
  MapPin,
  MessageCircle,
  Phone,
  Route,
  Truck,
  IndianRupee,
} from "lucide-react";

import {
  API_BASE_URL,
  apiHeaders,
  CROPS,
  SOURCE_STATES,
  type AgentsStatus,
  type ArbitrageResponse,
  type ArbitrageRoute,
  type CropName,
  type LiveBriefing,
  type SourceState,
  type VerifiedAgent,
} from "@/lib/types";
import AudioBriefing from "@/components/AudioBriefing";

/** Leaflet touches `window` — must never SSR. */
const ArbitrageMap = dynamic(() => import("@/components/ArbitrageMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-slate-950 text-slate-400">
      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
      Loading map…
    </div>
  ),
});

function digitsOnly(phone: string): string {
  return phone.replace(/\D/g, "");
}

function AgentContactCard({
  agent,
  demo,
}: {
  agent: VerifiedAgent;
  demo: boolean;
}) {
  const telHref = `tel:${digitsOnly(agent.phone)}`;
  const waHref = `https://wa.me/${digitsOnly(agent.phone)}`;

  return (
    <article className="rounded-xl border border-slate-700/80 bg-slate-900/90 p-4 shadow-lg shadow-black/20">
      {demo && (
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-amber-300">
          Demo sample — not a real agent
        </p>
      )}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg text-slate-50">{agent.name}</h3>
          <p className="mt-1 text-sm text-slate-400">
            {demo ? `Sample ID ${agent.license_id}` : `License ${agent.license_id}`}
          </p>
          <p className="mt-2 text-sm text-slate-200">
            {demo ? "Phone hidden until verified" : agent.phone}
          </p>
        </div>
      </div>
      {!demo && (
        <div className="mt-4 flex flex-wrap gap-2">
          <a
            href={telHref}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
          >
            <Phone className="h-4 w-4" />
            Call
          </a>
          <a
            href={waHref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-500"
          >
            <MessageCircle className="h-4 w-4" />
            WhatsApp
          </a>
        </div>
      )}
    </article>
  );
}

function RouteCard({
  route,
  selected,
  onSelect,
}: {
  route: ArbitrageRoute;
  selected: boolean;
  onSelect: (route: ArbitrageRoute) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(route)}
      className={`w-full rounded-xl border p-4 text-left transition ${
        selected
          ? "border-sky-400 bg-slate-800/90 ring-1 ring-sky-400/60"
          : "border-slate-700/70 bg-slate-900/70 hover:border-slate-500 hover:bg-slate-800/70"
      }`}
    >
      {/* State-boundary badge — instantly readable transit corridor */}
      <div className="mb-3">
        <span className="inline-flex max-w-full items-center rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-1 text-xs font-medium text-sky-300">
          {route.source_state} to {route.destination_state}
        </span>
      </div>

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">
            Route
          </p>
          <p className="mt-1 font-medium text-slate-50">
            {route.source_mandi}
            <span className="mx-2 text-slate-500">→</span>
            {route.destination_mandi}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">
            Net profit
          </p>
          <p className="mt-1 inline-flex items-center gap-0.5 text-lg font-semibold text-emerald-400">
            <IndianRupee className="h-4 w-4" />
            {route.net_profit.toLocaleString("en-IN")}
            <span className="ml-1 text-xs font-normal text-emerald-300/80">
              /qtl
            </span>
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-slate-300">
        <div className="flex items-center gap-2">
          <Route className="h-4 w-4 text-sky-400" />
          {route.distance_km.toFixed(0)} km
        </div>
        <div className="flex items-center gap-2">
          <Truck className="h-4 w-4 text-amber-300" />
          Transit ₹{route.transit_cost.toLocaleString("en-IN")}/qtl
        </div>
        <div className="col-span-2 flex flex-col gap-1 text-slate-400">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 shrink-0" />
            <span>
              Buy ₹{route.source_price_per_quintal.toLocaleString("en-IN")} · Sell ₹
              {route.destination_price_per_quintal.toLocaleString("en-IN")}
            </span>
          </div>
          {(route.source_price_date || route.destination_price_date) && (
            <p className="pl-6 text-xs text-slate-500">
              Prices as of {route.source_price_date ?? "—"}
              {route.destination_price_date &&
              route.destination_price_date !== route.source_price_date
                ? ` → ${route.destination_price_date}`
                : ""}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}

export default function HomePage() {
  const [selectedState, setSelectedState] = useState<SourceState>("Maharashtra");
  const [crop, setCrop] = useState<CropName>("Onion");
  const [routes, setRoutes] = useState<ArbitrageRoute[]>([]);
  const [agentsStatus, setAgentsStatus] = useState<AgentsStatus | string>(
    "unavailable",
  );
  const [dataSourceUsed, setDataSourceUsed] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<string | null>(null);
  const [apiMessage, setApiMessage] = useState<string | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<ArbitrageRoute | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveBriefing, setLiveBriefing] = useState<LiveBriefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);

  const fetchRoutes = useCallback(async (cropName: CropName) => {
    setLoading(true);
    setError(null);
    setSelectedRoute(null);
    setLiveBriefing(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/arbitrage/?crop_name=${encodeURIComponent(cropName)}`,
        { headers: apiHeaders() },
      );

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        throw new Error(payload?.detail ?? `API error ${response.status}`);
      }

      const data = (await response.json()) as ArbitrageResponse;
      setRoutes(data.routes ?? []);
      setAgentsStatus(data.agents_status ?? "unavailable");
      setDataSourceUsed(data.data_source_used ?? null);
      setApiStatus(data.status ?? "ok");
      setApiMessage(data.message ?? null);
    } catch (err) {
      setRoutes([]);
      setAgentsStatus("unavailable");
      setDataSourceUsed(null);
      setApiStatus(null);
      setApiMessage(null);
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load arbitrage routes.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchRoutes(crop);
  }, [crop, fetchRoutes]);

  // Clear map selection when the farmer changes their home state.
  useEffect(() => {
    setSelectedRoute(null);
    setLiveBriefing(null);
  }, [selectedState]);

  // Live Gemini briefing for the selected corridor.
  useEffect(() => {
    if (!selectedRoute) {
      setLiveBriefing(null);
      return;
    }

    const controller = new AbortController();
    setBriefingLoading(true);

    void (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/arbitrage/briefing`, {
          method: "POST",
          headers: apiHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            ...selectedRoute,
            agents_status:
              selectedRoute.agents_status ?? agentsStatus ?? "unavailable",
            // Never send seeded phones into the LLM prompt path as actionable.
            destination_verified_agents:
              (selectedRoute.agents_status ?? agentsStatus) === "verified"
                ? selectedRoute.destination_verified_agents
                : [],
          }),
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Briefing API ${response.status}`);
        }
        const data = (await response.json()) as LiveBriefing;
        setLiveBriefing(data);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setLiveBriefing(null);
      } finally {
        if (!controller.signal.aborted) {
          setBriefingLoading(false);
        }
      }
    })();

    return () => controller.abort();
  }, [selectedRoute, agentsStatus]);

  // On phones, jump to map/details after a route is tapped.
  useEffect(() => {
    if (!selectedRoute || typeof window === "undefined") return;
    if (window.matchMedia("(min-width: 1024px)").matches) return;
    document.getElementById("route-details")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, [selectedRoute]);

  /**
   * Farmer-First filter: keep API profit sort, then show only routes
   * originating from the selected source state.
   */
  const filteredRoutes = useMemo(() => {
    return routes.filter((route) => route.source_state === selectedState);
  }, [routes, selectedState]);

  const agents = useMemo(
    () => selectedRoute?.destination_verified_agents ?? [],
    [selectedRoute],
  );
  const routeAgentsStatus =
    selectedRoute?.agents_status ?? agentsStatus ?? "unavailable";
  const showDemoAgents = routeAgentsStatus === "demo" && agents.length > 0;

  return (
    <main className="min-h-screen bg-slate-900 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4 sm:px-6 md:px-8">
        <p className="text-xs uppercase tracking-[0.22em] text-sky-400">
          MandiSync
        </p>
        <h1 className="font-display mt-1 text-xl text-slate-50 sm:text-2xl">
          Crop Arbitrage
        </h1>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-400">
          Pick your home state and crop to see corridors that start where you
          farm. Net profit is an estimate after transit, ~7% mandi fees, and
          spoilage risk — not a guaranteed payout.
          {dataSourceUsed === "agmarknet"
            ? " Prices are from live Agmarknet (gov API)."
            : dataSourceUsed === "seed"
              ? " Demo seed prices (ALLOW_SEED_FALLBACK is on)."
              : apiStatus === "no_fresh_prices"
                ? " No fresh Agmarknet prices right now."
                : ""}
        </p>
      </header>

      {/* Phone-first: one scrolling column. Desktop: filters+routes | map+details */}
      <div className="mx-auto grid max-w-7xl gap-0 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <aside className="border-b border-slate-800 lg:border-b-0 lg:border-r">
          <div className="sticky top-0 z-20 space-y-4 border-b border-slate-800 bg-slate-900/95 p-4 backdrop-blur sm:p-5">
            <div className="space-y-2">
              <label
                htmlFor="state-select"
                className="block text-xs uppercase tracking-[0.16em] text-slate-400"
              >
                Your location (source state)
              </label>
              <select
                id="state-select"
                value={selectedState}
                onChange={(event) =>
                  setSelectedState(event.target.value as SourceState)
                }
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-3 text-base text-slate-100 outline-none ring-sky-400/40 focus:ring-2 sm:py-2.5 sm:text-sm"
              >
                {SOURCE_STATES.map((state) => (
                  <option key={state} value={state}>
                    {state}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label
                htmlFor="crop-select"
                className="block text-xs uppercase tracking-[0.16em] text-slate-400"
              >
                Crop
              </label>
              <div className="grid grid-cols-3 gap-2">
                {CROPS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setCrop(option)}
                    className={`rounded-xl border px-2 py-3 text-sm font-medium transition ${
                      crop === option
                        ? "border-sky-400 bg-sky-500/15 text-sky-200"
                        : "border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-500"
                    }`}
                  >
                    {option}
                  </button>
                ))}
              </div>
              <select
                id="crop-select"
                value={crop}
                onChange={(event) => setCrop(event.target.value as CropName)}
                className="sr-only"
                aria-hidden
                tabIndex={-1}
              >
                {CROPS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>

            {!loading && !error && (
              <p className="text-xs text-slate-500">
                {filteredRoutes.length} of {routes.length} profitable{" "}
                {crop.toLowerCase()} corridors from {selectedState}.
              </p>
            )}
          </div>

          <div className="space-y-3 p-4 sm:p-5">
            {loading && (
              <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-6 text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                Fetching {crop} routes for {selectedState}…
              </div>
            )}

            {!loading && error && (
              <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-4 text-sm text-rose-200">
                {error}
              </div>
            )}

            {!loading && !error && apiStatus === "no_fresh_prices" && (
              <div className="rounded-xl border border-amber-500/40 bg-amber-950/40 px-4 py-6 text-sm leading-relaxed text-amber-50">
                <p className="font-medium text-amber-100">No fresh market prices</p>
                <p className="mt-2 text-amber-100/90">
                  {apiMessage ??
                    `Agmarknet has no usable ${crop} quotes within the last few days. We do not show fake seed prices in live mode.`}
                </p>
                <p className="mt-3 text-xs text-amber-200/80">
                  Fix: run{" "}
                  <code className="rounded bg-black/30 px-1 py-0.5">
                    python ingest_prices.py --ingest
                  </code>{" "}
                  (or wait for the daily scheduled pull).
                </p>
              </div>
            )}

            {!loading &&
              !error &&
              apiStatus !== "no_fresh_prices" &&
              filteredRoutes.length === 0 && (
              <div className="rounded-xl border border-amber-500/25 bg-amber-950/25 px-4 py-6 text-sm leading-relaxed text-amber-100/90">
                No profitable routes found from this state today. Try another
                crop or check nearby regions.
              </div>
            )}

            {!loading &&
              apiStatus !== "no_fresh_prices" &&
              filteredRoutes.map((route) => {
                const key = `${route.source_mandi}-${route.destination_mandi}-${route.net_profit}`;
                return (
                  <RouteCard
                    key={key}
                    route={route}
                    selected={
                      selectedRoute?.source_mandi === route.source_mandi &&
                      selectedRoute?.destination_mandi ===
                        route.destination_mandi
                    }
                    onSelect={setSelectedRoute}
                  />
                );
              })}
          </div>
        </aside>

        <section className="bg-slate-950/40">
          <div className="relative h-[42vh] min-h-[220px] overflow-hidden border-b border-slate-800 bg-slate-950 sm:h-[48vh] lg:sticky lg:top-0 lg:h-[45vh]">
            <div className="absolute inset-0">
              <ArbitrageMap selectedRoute={selectedRoute} />
            </div>
            {!selectedRoute && (
              <div className="pointer-events-none absolute inset-x-3 bottom-3 z-[500] rounded-xl border border-slate-700/80 bg-slate-950/85 px-3 py-2 text-center text-sm text-slate-300 backdrop-blur sm:inset-x-auto sm:left-1/2 sm:max-w-md sm:-translate-x-1/2 sm:rounded-full sm:px-4">
                Tap a route to plot the haul on the map.
              </div>
            )}
          </div>

          <div className="space-y-4 p-4 sm:p-5" id="route-details">
            {selectedRoute && (
              <AudioBriefing
                routeData={selectedRoute}
                isActive
                liveBriefing={liveBriefing}
              />
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-violet-500/30 bg-violet-950/20 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-violet-300">
                  Corridor summary
                </p>
                <h2 className="font-display mt-1 text-lg text-slate-50">
                  {selectedRoute
                    ? `${selectedRoute.source_mandi} → ${selectedRoute.destination_mandi}`
                    : "Select a route"}
                </h2>

                {!selectedRoute ? (
                  <p className="mt-3 text-sm leading-relaxed text-slate-400">
                    Choose a corridor from the list to see haul distance,
                    transit cost, and estimated net profit.
                  </p>
                ) : (
                  <div className="mt-3 space-y-3 text-sm text-slate-300">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-violet-300/80">
                      {briefingLoading
                        ? "Gemini drafting live briefing…"
                        : liveBriefing?.source === "gemini"
                          ? "Live Gemini briefing"
                          : "Simulation briefing"}
                    </p>
                    <p className="leading-relaxed text-slate-200">
                      {briefingLoading && !liveBriefing
                        ? "Generating route strategy from live market + monsoon context…"
                        : liveBriefing?.on_screen_caption ??
                          `Moving ${selectedRoute.crop_name.toLowerCase()} from ${selectedRoute.source_mandi} to ${selectedRoute.destination_mandi}.`}
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg border border-slate-700/70 bg-slate-900/70 p-3">
                        <p className="text-xs text-slate-500">Gross spread</p>
                        <p className="mt-1 font-medium text-slate-100">
                          ₹{selectedRoute.gross_spread.toLocaleString("en-IN")}
                          /qtl
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-700/70 bg-slate-900/70 p-3">
                        <p className="text-xs text-slate-500">Transit</p>
                        <p className="mt-1 font-medium text-amber-200">
                          ₹{selectedRoute.transit_cost.toLocaleString("en-IN")}
                          /qtl
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-700/70 bg-slate-900/70 p-3">
                        <p className="text-xs text-slate-500">
                          Mandi fees (~7%)
                        </p>
                        <p className="mt-1 font-medium text-amber-200">
                          ₹
                          {(
                            selectedRoute.mandi_fee_per_quintal ?? 0
                          ).toLocaleString("en-IN")}
                          /qtl
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-700/70 bg-slate-900/70 p-3">
                        <p className="text-xs text-slate-500">Spoilage risk</p>
                        <p className="mt-1 font-medium text-amber-200">
                          ₹
                          {(
                            selectedRoute.perishability_cost_per_quintal ?? 0
                          ).toLocaleString("en-IN")}
                          /qtl
                        </p>
                      </div>
                      <div className="col-span-2 rounded-lg border border-emerald-500/30 bg-emerald-950/30 p-3">
                        <p className="text-xs text-emerald-300/80">
                          Estimated net after fees & spoilage
                        </p>
                        <p className="mt-1 text-lg font-semibold text-emerald-400">
                          ₹{selectedRoute.net_profit.toLocaleString("en-IN")}/qtl
                        </p>
                        <p className="mt-2 text-[11px] leading-relaxed text-emerald-200/70">
                          Estimate only — great-circle distance, assumes a full
                          truck, and does not include backhaul or load-fill time.
                          {(selectedRoute.source_price_date ||
                            selectedRoute.destination_price_date) && (
                            <>
                              {" "}
                              Prices dated{" "}
                              {selectedRoute.source_price_date ?? "—"}
                              {selectedRoute.destination_price_date &&
                              selectedRoute.destination_price_date !==
                                selectedRoute.source_price_date
                                ? ` / ${selectedRoute.destination_price_date}`
                                : ""}
                              .
                            </>
                          )}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div>
                <div className="mb-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-slate-400">
                    Destination contacts
                  </p>
                  <h2 className="font-display text-lg text-slate-50">
                    {selectedRoute
                      ? selectedRoute.destination_mandi
                      : "Awaiting route selection"}
                  </h2>
                  {selectedRoute && (
                    <p className="mt-1 text-sm text-slate-400">
                      {selectedRoute.source_state} to{" "}
                      {selectedRoute.destination_state}
                    </p>
                  )}
                </div>

                {!selectedRoute && (
                  <p className="rounded-xl border border-dashed border-slate-700 px-4 py-6 text-sm text-slate-400">
                    Select a profitable route to see arrival guidance for the
                    destination market.
                  </p>
                )}

                {selectedRoute && routeAgentsStatus === "unavailable" && (
                  <p className="rounded-xl border border-amber-500/30 bg-amber-950/30 px-4 py-4 text-sm leading-relaxed text-amber-100">
                    We do not publish phone numbers for live markets yet. On
                    arrival, confirm a licensed commission agent at the
                    destination APMC office before unloading — do not rely on
                    unverified contacts from any app.
                  </p>
                )}

                {selectedRoute && showDemoAgents && (
                  <>
                    <p className="mb-3 rounded-xl border border-amber-500/30 bg-amber-950/30 px-4 py-3 text-sm leading-relaxed text-amber-100">
                      Sample layout only — these names and numbers are demo
                      placeholders from seed data, not real agents. Call and
                      WhatsApp are disabled.
                    </p>
                    <div className="grid gap-3">
                      {agents.map((agent) => (
                        <AgentContactCard
                          key={`${agent.license_id}-${agent.phone}`}
                          agent={agent}
                          demo
                        />
                      ))}
                    </div>
                  </>
                )}

                {selectedRoute &&
                  routeAgentsStatus === "verified" &&
                  agents.length > 0 && (
                    <div className="grid gap-3">
                      {agents.map((agent) => (
                        <AgentContactCard
                          key={`${agent.license_id}-${agent.phone}`}
                          agent={agent}
                          demo={false}
                        />
                      ))}
                    </div>
                  )}
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
