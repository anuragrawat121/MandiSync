/**
 * Regional audio companion copy for selected arbitrage corridors.
 * Pure helpers only — no browser SpeechSynthesis side effects here.
 *
 * Important: Latin-script Hinglish is read like English by most TTS engines.
 * Spoken playback must use Devanagari Hindi (`getRegionalSpeechUtteranceText`)
 * with a hi-IN voice for a natural Indian accent.
 */

import type { ArbitrageRoute } from "@/lib/types";

/** Minimal shape required to build a spoken route narrative. */
export interface SpeechRouteInput {
  source_state: string;
  source_mandi: string;
  destination_mandi: string;
  /** Preferred field from API (`distance_km`). */
  distance_km?: number | null;
  /** Alias accepted for older callers / templates. */
  distance?: number | null;
  transit_cost?: number | null;
  net_profit?: number | null;
  agent_name?: string | null;
  destination_verified_agents?: Array<{ name?: string | null }> | null;
}

export interface ResolvedSpeechFields {
  sourceState: string;
  sourceMandi: string;
  destinationMandi: string;
  distance: string;
  transitCost: string;
  netProfit: string;
  agentName: string;
}

function safeText(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

function safeAmount(value: unknown, fallback = 0): string {
  const numeric =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number(value)
        : Number.NaN;

  if (!Number.isFinite(numeric)) {
    return fallback.toLocaleString("en-IN");
  }

  return Math.round(numeric).toLocaleString("en-IN");
}

function resolveDistanceKm(route: SpeechRouteInput): string {
  return safeAmount(route.distance_km ?? route.distance, 0);
}

function resolveAgentName(route: SpeechRouteInput): string {
  if (route.agent_name && route.agent_name.trim()) {
    return route.agent_name.trim();
  }

  const firstAgent = route.destination_verified_agents?.[0]?.name;
  return safeText(firstAgent, "मंडी कमीशन एजेंट");
}

export function resolveSpeechFields(
  route: SpeechRouteInput | ArbitrageRoute,
): ResolvedSpeechFields {
  return {
    sourceState: safeText(route.source_state, "India"),
    sourceMandi: safeText(route.source_mandi, "सोर्स मंडी"),
    destinationMandi: safeText(route.destination_mandi, "डेस्टिनेशन मंडी"),
    distance: resolveDistanceKm(route),
    transitCost: safeAmount(route.transit_cost, 0),
    netProfit: safeAmount(route.net_profit, 0),
    agentName: resolveAgentName(route),
  };
}

/**
 * On-screen Hinglish narrative (for captions / reading).
 * Dialect switches on `source_state` (Haryana / Punjab / default).
 */
export function getRegionalSpeechText(
  route: SpeechRouteInput | ArbitrageRoute,
): string {
  const {
    sourceState,
    sourceMandi,
    destinationMandi,
    distance,
    transitCost,
    netProfit,
    agentName,
  } = resolveSpeechFields(route);

  if (sourceState === "Haryana") {
    return (
      `Ram Ram bhaiya! Dekho, aapka maal ${sourceMandi} se ${destinationMandi} ja raha hai. ` +
      `Total distance hai ${distance} kilometer aur truck ka kharcha aayega lagbhag ${transitCost} rupaye. ` +
      `Par dilli ka bazaar bohot tight hai mittar, sab kat-pitat ke aapko har quintal par pure ${netProfit} rupaye ka tagda munafa dikh raha hai! ` +
      `Wahan pahunchte hi seedha ${agentName} se baat kar lena.`
    );
  }

  if (sourceState === "Punjab") {
    return (
      `Sat Sri Akal bhaiya! Tussi ${sourceMandi} ton ${destinationMandi} da route select kiya hai. ` +
      `Bhaada lagega ${transitCost} rupaye, par net profit hai pure ${netProfit} rupaye per quintal! ` +
      `Khush ho jao, aur mandi pahunch ke sidha ${agentName} nu call mila lena.`
    );
  }

  return (
    `Namaste! Aapne ${sourceMandi} se ${destinationMandi} ka route choose kiya hai. ` +
    `Yeh lagbhag ${distance} kilometer ka safar hai. Truck ka kharcha around ${transitCost} rupaye per quintal padega. ` +
    `Iske baad bhi aapko har quintal par lagbhag ${netProfit} rupaye ka net profit mil sakta hai. ` +
    `Destination pahunchte hi verified agent ${agentName} se contact kar lijiye.`
  );
}

/**
 * Devanagari Hindi script for TTS.
 * hi-IN voices pronounce this naturally; Latin Hinglish always sounds foreign.
 */
export function getRegionalSpeechUtteranceText(
  route: SpeechRouteInput | ArbitrageRoute,
): string {
  const {
    sourceState,
    sourceMandi,
    destinationMandi,
    distance,
    transitCost,
    netProfit,
    agentName,
  } = resolveSpeechFields(route);

  if (sourceState === "Haryana") {
    return (
      `राम राम भैया! देखो, आपका माल ${sourceMandi} से ${destinationMandi} जा रहा है। ` +
      `कुल दूरी है ${distance} किलोमीटर, और ट्रक का खर्चा लगेगा लगभग ${transitCost} रुपये। ` +
      `पर दिल्ली का बाज़ार बहुत टाइट है मित्तर — कट-पिटट के बाद भी हर क्विंटल पर पूरे ${netProfit} रुपये का तगड़ा मुनाफा दिख रहा है! ` +
      `वहाँ पहुँचते ही सीधा ${agentName} से बात कर लेना।`
    );
  }

  if (sourceState === "Punjab") {
    return (
      `सत श्री अकाल भैया! तुसीं ${sourceMandi} तों ${destinationMandi} दा रूट चुन्या है। ` +
      `भाड़ा लगेगा ${transitCost} रुपये, पर नेट प्रॉफिट है पूरे ${netProfit} रुपये प्रति क्विंटल! ` +
      `खुश हो जाओ, और मंडी पहुँच के सीधा ${agentName} नूं कॉल मिला लेना।`
    );
  }

  return (
    `नमस्ते! आपने ${sourceMandi} से ${destinationMandi} का रूट चुना है। ` +
    `यह लगभग ${distance} किलोमीटर का सफर है। ट्रक का खर्चा करीब ${transitCost} रुपये प्रति क्विंटल पड़ेगा। ` +
    `इसके बाद भी आपको हर क्विंटल पर लगभग ${netProfit} रुपये का नेट मुनाफा मिल सकता है। ` +
    `मंज़िल पहुँचते ही वेरिफाइड एजेंट ${agentName} से संपर्क कर लीजिए।`
  );
}
