/** Shared API contracts for the MandiSync arbitrage dashboard. */

export type CropName = "Onion" | "Tomato" | "Potato";

export type SourceState =
  | "Punjab"
  | "Haryana"
  | "Uttar Pradesh"
  | "Maharashtra"
  | "Madhya Pradesh"
  | "Rajasthan"
  | "Gujarat"
  | "Karnataka"
  | "Andhra Pradesh"
  | "West Bengal";

export interface VerifiedAgent {
  name: string;
  phone: string;
  license_id: string;
}

/** Government-published APMC office contact (not a licensed commission agent). */
export interface MandiContact {
  name: string;
  phone: string;
  role: string;
  contact_type?: "apmc_office" | "commission_agent" | string;
}

/** How destination contacts should be treated in the UI. */
export type AgentsStatus = "unavailable" | "demo" | "verified" | "official";

export interface ArbitrageRoute {
  crop_name: string;
  source_mandi: string;
  destination_mandi: string;
  source_state: string;
  destination_state: string;
  source_price_per_quintal: number;
  destination_price_per_quintal: number;
  gross_spread: number;
  distance_km: number;
  transit_cost: number;
  /** ~7% APMC + commission haircut on destination modal. */
  mandi_fee_per_quintal?: number;
  /** Crop-specific spoilage estimate vs distance. */
  perishability_cost_per_quintal?: number;
  net_profit: number;
  /** Leaflet order: [latitude, longitude] */
  source_coordinates: [number, number];
  /** Leaflet order: [latitude, longitude] */
  destination_coordinates: [number, number];
  destination_verified_agents: VerifiedAgent[];
  /** Official APMC office contacts when agents_status is "official". */
  destination_contacts?: MandiContact[];
  destination_profile_url?: string | null;
  destination_maps_url?: string | null;
  destination_contact_source?: string | null;
  /** e-NAM mandi directory — user picks state/APMC on the portal. */
  destination_enam_url?: string | null;
  destination_enam_apmc_search?: string | null;
  source_price_date?: string;
  destination_price_date?: string;
  agents_status?: AgentsStatus | string;
}

export interface ArbitrageResponse {
  crop_name: string;
  route_count: number;
  /** "agmarknet" when fresh live quotes exist; "none" when live-only and stale. */
  data_source_used?: "agmarknet" | "seed" | "none" | string;
  /** "ok" or "no_fresh_prices" when Agmarknet is missing/stale in live mode. */
  status?: "ok" | "no_fresh_prices" | string;
  message?: string;
  /** Live markets: official APMC office, unavailable, or demo seed. */
  agents_status?: AgentsStatus | string;
  max_staleness_days?: number;
  /** Toll-free e-NAM helpdesk (1800 270 0224). */
  enam_helpline?: string;
  routes: ArbitrageRoute[];
}

export interface LiveBriefing {
  on_screen_caption: string;
  audio_speech_text: string;
  source?: "gemini" | "fallback" | string;
  warning?: string;
  model?: string;
  cached?: boolean;
}

/** Shared with FastAPI only as a legacy machine key. Browser auth uses JWT. */
export const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export const CROPS: CropName[] = ["Onion", "Tomato", "Potato"];

/** Farmer-facing source states aligned with the seeded pan-India mandi set. */
export const SOURCE_STATES: SourceState[] = [
  "Punjab",
  "Haryana",
  "Uttar Pradesh",
  "Maharashtra",
  "Madhya Pradesh",
  "Rajasthan",
  "Gujarat",
  "Karnataka",
  "Andhra Pradesh",
  "West Bengal",
];

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function apiHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  if (typeof window !== "undefined") {
    try {
      const raw = window.localStorage.getItem("mandisync.session");
      if (raw) {
        const parsed = JSON.parse(raw) as { token?: string };
        if (parsed.token) {
          headers.set("Authorization", `Bearer ${parsed.token}`);
        }
      }
    } catch {
      /* ignore broken session JSON */
    }
  }
  return headers;
}

export const INDIA_CENTER: [number, number] = [20.5937, 78.9629];
