"use client";

/**
 * MandiSync Farmer-First arbitrage dashboard.
 * Phone-first scrolling layout: filters + routes, then map + corridor details.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ExternalLink,
  Loader2,
  MapPin,
  MessageCircle,
  Phone,
} from "lucide-react";

import {
  apiHeaders,
  CROPS,
  SOURCE_STATES,
  type AgentsStatus,
  type ArbitrageResponse,
  type ArbitrageRoute,
  type CropName,
  type LiveBriefing,
  type MandiContact,
  type SourceState,
  type VerifiedAgent,
} from "@/lib/types";
import {
  apiRoot,
  fetchWithTimeout,
  friendlyApiError,
  wakeApi,
} from "@/lib/apiClient";
import AudioBriefing from "@/components/AudioBriefing";
import AgentIntroForm from "@/components/AgentIntroForm";
import SiteShell from "@/components/SiteShell";

const ArbitrageMap = dynamic(() => import("@/components/ArbitrageMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-[#e8e4dc] text-sm text-[var(--muted)]">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      Loading map
    </div>
  ),
});

function loadingHint(
  seconds: number,
  cropName: CropName,
  state: SourceState,
): { title: string; detail: string } {
  if (seconds < 10) {
    return {
      title: `Fetching ${cropName} corridors for ${state}…`,
      detail: "",
    };
  }
  if (seconds < 35) {
    return {
      title: "Connecting to the service…",
      detail:
        "The free host sleeps after idle. The first open can take about a minute.",
    };
  }
  if (seconds < 75) {
    return {
      title: "Still starting the service…",
      detail: "Stay on this page. A cold start can take up to two minutes.",
    };
  }
  return {
    title: "This is taking longer than usual…",
    detail: "If it does not finish soon, tap retry.",
  };
}

function digitsOnly(phone: string): string {
  return phone.replace(/\D/g, "");
}

function rupee(value: number): string {
  return `₹${value.toLocaleString("en-IN")}`;
}

function OfficialContactCard({ contact }: { contact: MandiContact }) {
  const telHref = `tel:${digitsOnly(contact.phone)}`;
  const waHref = `https://wa.me/${digitsOnly(contact.phone)}`;

  return (
    <article className="gov-card p-4">
      <p className="gov-kicker">APMC office — government published</p>
      <h3 className="mt-1 font-serif text-lg text-navy-dark">{contact.name}</h3>
      <p className="mt-1 text-sm text-[var(--muted)]">{contact.role}</p>
      <p className="gov-money mt-2 text-sm">{contact.phone}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <a href={telHref} className="gov-btn gov-btn-success">
          <Phone className="h-4 w-4" />
          Call
        </a>
        <a
          href={waHref}
          target="_blank"
          rel="noopener noreferrer"
          className="gov-btn"
        >
          <MessageCircle className="h-4 w-4" />
          WhatsApp
        </a>
      </div>
    </article>
  );
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
    <article className="gov-card p-4">
      {demo && (
        <p className="gov-kicker text-[var(--saffron)]">
          Demo sample — not a real agent
        </p>
      )}
      <h3 className="mt-1 font-serif text-lg text-navy-dark">{agent.name}</h3>
      <p className="mt-1 text-sm text-[var(--muted)]">
        {demo ? `Sample ID ${agent.license_id}` : `License ${agent.license_id}`}
      </p>
      <p className="mt-2 text-sm">
        {demo ? "Phone hidden until verified" : agent.phone}
      </p>
      {!demo && (
        <div className="mt-3 flex flex-wrap gap-2">
          <a href={telHref} className="gov-btn gov-btn-success">
            <Phone className="h-4 w-4" />
            Call
          </a>
          <a
            href={waHref}
            target="_blank"
            rel="noopener noreferrer"
            className="gov-btn"
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
      className={`w-full border p-3 text-left transition-colors ${
        selected
          ? "border-navy bg-white shadow-[inset_3px_0_0_0_#c45c0a]"
          : "border-[var(--line)] bg-[var(--panel)] hover:border-navy/40 hover:bg-white"
      }`}
    >
      <p className="text-xs text-[var(--muted)]">
        {route.source_state} to {route.destination_state}
      </p>
      <div className="mt-1 flex items-start justify-between gap-3">
        <p className="min-w-0 text-sm font-medium text-navy-dark">
          {route.source_mandi}
          <span className="mx-1.5 text-[var(--muted)]">→</span>
          {route.destination_mandi}
        </p>
        <p className="gov-money shrink-0 text-harvest">
          {rupee(route.net_profit)}
          <span className="ml-1 text-xs font-normal text-[var(--muted)]">
            /qtl
          </span>
        </p>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-[var(--muted)]">
        <div>
          Distance {route.distance_km.toFixed(0)} km
        </div>
        <div>Transit {rupee(route.transit_cost)}/qtl</div>
        <div className="col-span-2">
          Buy {rupee(route.source_price_per_quintal)} · Sell{" "}
          {rupee(route.destination_price_per_quintal)}
        </div>
        {(route.source_price_date || route.destination_price_date) && (
          <div className="col-span-2">
            Prices as of {route.source_price_date ?? "—"}
            {route.destination_price_date &&
            route.destination_price_date !== route.source_price_date
              ? ` → ${route.destination_price_date}`
              : ""}
          </div>
        )}
      </dl>
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
  const [waitSeconds, setWaitSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [liveBriefing, setLiveBriefing] = useState<LiveBriefing | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [enamHelpline, setEnamHelpline] = useState("18002700224");

  const fetchRoutes = useCallback(async (cropName: CropName, signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    setSelectedRoute(null);
    setLiveBriefing(null);

    try {
      await wakeApi(signal);
      const response = await fetchWithTimeout(
        `${apiRoot()}/api/arbitrage/?crop_name=${encodeURIComponent(cropName)}`,
        { headers: apiHeaders(), timeoutMs: 45_000, signal },
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
      if (data.enam_helpline) {
        setEnamHelpline(data.enam_helpline);
      }
    } catch (err) {
      if (signal.aborted || (err instanceof DOMException && err.name === "AbortError")) {
        return;
      }
      setRoutes([]);
      setAgentsStatus("unavailable");
      setDataSourceUsed(null);
      setApiStatus(null);
      setApiMessage(null);
      setError(friendlyApiError(err));
    } finally {
      if (!signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void fetchRoutes(crop, controller.signal);
    return () => controller.abort();
  }, [crop, fetchRoutes]);

  useEffect(() => {
    if (!loading) {
      setWaitSeconds(0);
      return;
    }
    const timer = window.setInterval(() => {
      setWaitSeconds((seconds) => seconds + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    setSelectedRoute(null);
    setLiveBriefing(null);
  }, [selectedState]);

  useEffect(() => {
    if (!selectedRoute) {
      setLiveBriefing(null);
      return;
    }

    const controller = new AbortController();
    setBriefingLoading(true);

    void (async () => {
      try {
        const response = await fetchWithTimeout(
          `${apiRoot()}/api/arbitrage/briefing`,
          {
            method: "POST",
            headers: apiHeaders({ "Content-Type": "application/json" }),
            timeoutMs: 45_000,
            signal: controller.signal,
            body: JSON.stringify({
              ...selectedRoute,
              agents_status:
                selectedRoute.agents_status ?? agentsStatus ?? "unavailable",
              destination_verified_agents:
                (selectedRoute.agents_status ?? agentsStatus) === "verified"
                  ? selectedRoute.destination_verified_agents
                  : [],
              destination_contacts:
                (selectedRoute.agents_status ?? agentsStatus) === "official"
                  ? selectedRoute.destination_contacts ?? []
                  : [],
            }),
          },
        );
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

  useEffect(() => {
    if (!selectedRoute || typeof window === "undefined") return;
    if (window.matchMedia("(min-width: 1024px)").matches) return;
    document.getElementById("route-details")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, [selectedRoute]);

  const filteredRoutes = useMemo(() => {
    return routes.filter((route) => route.source_state === selectedState);
  }, [routes, selectedState]);

  const agents = useMemo(
    () => selectedRoute?.destination_verified_agents ?? [],
    [selectedRoute],
  );
  const officialContacts = useMemo(
    () => selectedRoute?.destination_contacts ?? [],
    [selectedRoute],
  );
  const routeAgentsStatus =
    selectedRoute?.agents_status ?? agentsStatus ?? "unavailable";
  const showDemoAgents = routeAgentsStatus === "demo" && agents.length > 0;
  const showOfficialContacts =
    (routeAgentsStatus === "official" || routeAgentsStatus === "verified") &&
    officialContacts.length > 0;
  const showVerifiedAgents =
    routeAgentsStatus === "verified" && agents.length > 0;
  const waitHint = loadingHint(waitSeconds, crop, selectedState);

  const sourceNote =
    dataSourceUsed === "agmarknet"
      ? "Prices are from live Agmarknet."
      : dataSourceUsed === "seed"
        ? "Demo seed prices are in use."
        : apiStatus === "no_fresh_prices"
          ? "No fresh Agmarknet prices right now."
          : "";

  return (
    <SiteShell current="home">
      <main id="main-content" className="gov-page">
        <p className="gov-kicker">For Farmer Producer Organisations</p>
        <h1 className="gov-title">Crop arbitrage corridors</h1>
        <p className="gov-lede">
          Choose your home state and crop. Only routes with estimated net profit
          after transit, about 7% mandi fees, and spoilage are listed.{" "}
          {sourceNote}
        </p>

        <div className="mt-6 grid gap-0 border border-[var(--line)] bg-[var(--panel)] lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <aside className="border-b border-[var(--line)] lg:border-b-0 lg:border-r">
            <div className="sticky top-0 z-20 space-y-4 border-b border-[var(--line)] bg-[var(--panel)] p-4">
              <div>
                <label htmlFor="state-select" className="gov-label">
                  Source state
                </label>
                <select
                  id="state-select"
                  value={selectedState}
                  onChange={(event) =>
                    setSelectedState(event.target.value as SourceState)
                  }
                  className="gov-select"
                >
                  {SOURCE_STATES.map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <p className="gov-label" id="crop-label">
                  Crop
                </p>
                <div
                  className="grid grid-cols-3 border border-[#b7b0a4]"
                  role="group"
                  aria-labelledby="crop-label"
                >
                  {CROPS.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setCrop(option)}
                      className={`border-r border-[#b7b0a4] px-2 py-2 text-sm last:border-r-0 ${
                        crop === option
                          ? "bg-navy text-white"
                          : "bg-white text-navy hover:bg-[#eef3f8]"
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
                <p className="gov-meta">
                  {filteredRoutes.length} of {routes.length} profitable{" "}
                  {crop.toLowerCase()} corridors from {selectedState}.
                </p>
              )}
            </div>

            <div className="space-y-2 p-4">
              {loading && (
                <div className="gov-notice">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                    <p>{waitHint.title}</p>
                  </div>
                  {waitHint.detail ? (
                    <p className="gov-meta mt-2">
                      {waitHint.detail} {waitSeconds > 0 ? `${waitSeconds}s` : ""}
                    </p>
                  ) : null}
                </div>
              )}

              {!loading && error && (
                <div className="gov-notice gov-notice-error">
                  <p>{error}</p>
                  <button
                    type="button"
                    onClick={() =>
                      void fetchRoutes(crop, new AbortController().signal)
                    }
                    className="gov-btn mt-3"
                  >
                    Retry
                  </button>
                </div>
              )}

              {!loading && !error && apiStatus === "no_fresh_prices" && (
                <div className="gov-notice gov-notice-warn">
                  <p className="font-semibold">No fresh market prices</p>
                  <p className="mt-2">
                    {apiMessage ??
                      `Agmarknet has no usable ${crop} quotes within the last few days. Seed prices are not shown in live mode.`}
                  </p>
                </div>
              )}

              {!loading &&
                !error &&
                apiStatus !== "no_fresh_prices" &&
                filteredRoutes.length === 0 && (
                  <div className="gov-notice gov-notice-warn">
                    No profitable routes found from this state today. Try another
                    crop or a nearby state.
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

          <section>
            <div className="relative h-[42vh] min-h-[220px] overflow-hidden border-b border-[var(--line)] bg-[#e8e4dc] sm:h-[48vh] lg:sticky lg:top-0 lg:h-[45vh]">
              <div className="absolute inset-0">
                <ArbitrageMap selectedRoute={selectedRoute} />
              </div>
              {!selectedRoute && (
                <div className="pointer-events-none absolute inset-x-3 bottom-3 z-[500] border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-center text-sm text-[var(--muted)] sm:inset-x-auto sm:left-1/2 sm:max-w-md sm:-translate-x-1/2">
                  Select a corridor to plot the haul.
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
                <div className="gov-card p-4">
                  <p className="gov-kicker">Corridor summary</p>
                  <h2 className="mt-1 font-serif text-lg text-navy-dark">
                    {selectedRoute
                      ? `${selectedRoute.source_mandi} → ${selectedRoute.destination_mandi}`
                      : "Select a route"}
                  </h2>

                  {!selectedRoute ? (
                    <p className="mt-3 text-sm leading-relaxed text-[var(--muted)]">
                      Choose a corridor from the list to see haul distance,
                      transit cost, and estimated net profit.
                    </p>
                  ) : (
                    <div className="mt-3 space-y-3 text-sm">
                      <p className="gov-meta">
                        {briefingLoading
                          ? "Preparing briefing…"
                          : liveBriefing?.source === "gemini"
                            ? "Live briefing"
                            : "Template briefing"}
                      </p>
                      <p className="leading-relaxed">
                        {briefingLoading && !liveBriefing
                          ? "Generating route notes from market context…"
                          : liveBriefing?.on_screen_caption ??
                            `Moving ${selectedRoute.crop_name.toLowerCase()} from ${selectedRoute.source_mandi} to ${selectedRoute.destination_mandi}.`}
                      </p>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="border border-[var(--line)] bg-white p-3">
                          <p className="gov-meta">Gross spread</p>
                          <p className="gov-money mt-1">
                            {rupee(selectedRoute.gross_spread)}/qtl
                          </p>
                        </div>
                        <div className="border border-[var(--line)] bg-white p-3">
                          <p className="gov-meta">Transit</p>
                          <p className="gov-money mt-1">
                            {rupee(selectedRoute.transit_cost)}/qtl
                          </p>
                        </div>
                        <div className="border border-[var(--line)] bg-white p-3">
                          <p className="gov-meta">Mandi fees (~7%)</p>
                          <p className="gov-money mt-1">
                            {rupee(selectedRoute.mandi_fee_per_quintal ?? 0)}/qtl
                          </p>
                        </div>
                        <div className="border border-[var(--line)] bg-white p-3">
                          <p className="gov-meta">Spoilage risk</p>
                          <p className="gov-money mt-1">
                            {rupee(
                              selectedRoute.perishability_cost_per_quintal ?? 0,
                            )}
                            /qtl
                          </p>
                        </div>
                        <div className="col-span-2 border border-[#b5d4c0] bg-[var(--ok-bg)] p-3">
                          <p className="gov-meta text-[#14532d]">
                            Estimated net after fees &amp; spoilage
                          </p>
                          <p className="gov-money mt-1 text-lg text-harvest">
                            {rupee(selectedRoute.net_profit)}/qtl
                          </p>
                          <p className="mt-2 text-xs leading-relaxed text-[#14532d]/80">
                            Estimate only — great-circle distance, assumes a full
                            truck, and does not include backhaul or waiting time.
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
                  <p className="gov-kicker">Destination contacts</p>
                  <h2 className="mt-1 font-serif text-lg text-navy-dark">
                    {selectedRoute
                      ? selectedRoute.destination_mandi
                      : "Awaiting route selection"}
                  </h2>
                  {selectedRoute && (
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      {selectedRoute.source_state} to{" "}
                      {selectedRoute.destination_state}
                    </p>
                  )}

                  {!selectedRoute && (
                    <p className="gov-notice mt-3 border-dashed">
                      Select a profitable route to see arrival guidance for the
                      destination market.
                    </p>
                  )}

                  {selectedRoute && (
                    <div className="gov-card mt-3 p-4">
                      <p className="gov-kicker">Find traders on e-NAM</p>
                      <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">
                        Search for{" "}
                        <span className="font-medium text-ink">
                          {selectedRoute.destination_enam_apmc_search ??
                            selectedRoute.destination_mandi}
                        </span>{" "}
                        on the official e-NAM mandi directory, or call the
                        national helpdesk.
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <a
                          href={
                            selectedRoute.destination_enam_url ??
                            "https://enam.gov.in/web/apmc-contact-details"
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className="gov-btn gov-btn-primary"
                        >
                          <ExternalLink className="h-4 w-4" />
                          e-NAM mandi list
                        </a>
                        <a href={`tel:${enamHelpline}`} className="gov-btn">
                          <Phone className="h-4 w-4" />
                          Helpline {enamHelpline}
                        </a>
                      </div>
                    </div>
                  )}

                  {selectedRoute && routeAgentsStatus === "unavailable" && (
                    <p className="gov-notice gov-notice-warn mt-3">
                      No official APMC phone number is loaded for this
                      destination yet. On arrival, ask at the market committee
                      office before unloading.
                    </p>
                  )}

                  {selectedRoute && showVerifiedAgents && (
                    <>
                      <p className="gov-notice gov-notice-ok mt-3">
                        Verified commission agents for this yard — curated after
                        offline license checks. Still confirm unloading terms at
                        the APMC office on arrival.
                      </p>
                      <div className="mt-3 grid gap-3">
                        {agents.map((agent) => (
                          <AgentContactCard
                            key={`${agent.license_id}-${agent.phone}`}
                            agent={agent}
                            demo={false}
                          />
                        ))}
                      </div>
                    </>
                  )}

                  {selectedRoute && showOfficialContacts && (
                    <>
                      <p className="gov-notice gov-notice-ok mt-3">
                        These numbers are from official APMC or state marketing
                        board directories — market office staff, not individual
                        commission agents.
                        {selectedRoute.destination_contact_source && (
                          <> Source: {selectedRoute.destination_contact_source}.</>
                        )}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {selectedRoute.destination_maps_url && (
                          <a
                            href={selectedRoute.destination_maps_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="gov-btn"
                          >
                            <MapPin className="h-4 w-4" />
                            Open in Maps
                          </a>
                        )}
                        {selectedRoute.destination_profile_url && (
                          <a
                            href={selectedRoute.destination_profile_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="gov-btn"
                          >
                            Official mandi page
                          </a>
                        )}
                      </div>
                      <div className="mt-3 grid gap-3">
                        {officialContacts.map((contact) => (
                          <OfficialContactCard
                            key={`${contact.name}-${contact.phone}`}
                            contact={contact}
                          />
                        ))}
                      </div>
                    </>
                  )}

                  {selectedRoute && <AgentIntroForm route={selectedRoute} />}

                  {selectedRoute && showDemoAgents && (
                    <>
                      <p className="gov-notice gov-notice-warn mt-3">
                        Sample layout only — these names and numbers are demo
                        placeholders, not real agents. Call and WhatsApp are
                        disabled.
                      </p>
                      <div className="mt-3 grid gap-3">
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
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </SiteShell>
  );
}
