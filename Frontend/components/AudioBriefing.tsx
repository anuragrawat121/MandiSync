"use client";

/**
 * Browser SpeechSynthesis controller for MandiSync route briefings.
 *
 * Speaks Devanagari Hindi with a hi-IN voice so the accent stays Indian.
 * Latin Hinglish is kept only as an on-screen caption.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Square, Volume2 } from "lucide-react";

import type { ArbitrageRoute, LiveBriefing } from "@/lib/types";
import {
  getRegionalSpeechText,
  getRegionalSpeechUtteranceText,
  type SpeechRouteInput,
} from "@/utils/speechUtils";

interface AudioBriefingProps {
  routeData: ArbitrageRoute | SpeechRouteInput | null;
  isActive: boolean;
  liveBriefing?: LiveBriefing | null;
}

interface RankedVoice {
  voice: SpeechSynthesisVoice;
  score: number;
  label: string;
}

function canUseSpeechSynthesis(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.speechSynthesis !== "undefined" &&
    typeof window.SpeechSynthesisUtterance !== "undefined"
  );
}

function isGoogleHindiVoice(voice: SpeechSynthesisVoice): boolean {
  const name = voice.name.toLowerCase();
  const lang = voice.lang.toLowerCase();
  const isGoogle = name.includes("google");
  const isHindi =
    name.includes("hindi") ||
    name.includes("हिंदी") ||
    name.includes("हिन्दी") ||
    lang === "hi-in" ||
    lang.startsWith("hi-");
  return isGoogle && isHindi;
}

function scoreIndianVoice(voice: SpeechSynthesisVoice): number {
  // Only Google Hindi is allowed for MandiSync audio briefings.
  if (!isGoogleHindiVoice(voice)) return -1000;

  const name = voice.name.toLowerCase();
  let score = 200;
  if (name.includes("google हिंदी") || name.includes("google hindi")) score += 50;
  return score;
}

function rankVoices(voices: SpeechSynthesisVoice[]): RankedVoice[] {
  return voices
    .filter(isGoogleHindiVoice)
    .map((voice) => ({
      voice,
      score: scoreIndianVoice(voice),
      label: `${voice.name} (${voice.lang})`,
    }))
    .sort((a, b) => b.score - a.score);
}

export default function AudioBriefing({
  routeData,
  isActive,
  liveBriefing = null,
}: AudioBriefingProps) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceURI, setSelectedVoiceURI] = useState<string>("");

  const ranked = useMemo(() => rankVoices(voices), [voices]);
  // Only Google Hindi — exclude Microsoft / other system Indian voices.
  const indianRanked = useMemo(() => ranked, [ranked]);

  const selectedVoice = useMemo(() => {
    if (!selectedVoiceURI) return indianRanked[0]?.voice ?? null;
    return (
      voices.find(
        (voice) =>
          voice.voiceURI === selectedVoiceURI && isGoogleHindiVoice(voice),
      ) ??
      indianRanked[0]?.voice ??
      null
    );
  }, [indianRanked, selectedVoiceURI, voices]);

  const hasIndianVoice = Boolean(selectedVoice && isGoogleHindiVoice(selectedVoice));

  const hydrateVoices = useCallback(() => {
    if (!canUseSpeechSynthesis()) return;
    const next = window.speechSynthesis.getVoices();
    setVoices(next);

    setSelectedVoiceURI((current) => {
      const googleHindi = rankVoices(next);
      if (current && googleHindi.some((entry) => entry.voice.voiceURI === current)) {
        return current;
      }
      return googleHindi[0]?.voice.voiceURI ?? "";
    });
  }, []);

  useEffect(() => {
    if (!canUseSpeechSynthesis()) return;

    hydrateVoices();

    const synth = window.speechSynthesis;
    const handleVoicesChanged = () => hydrateVoices();

    synth.addEventListener("voiceschanged", handleVoicesChanged);
    synth.onvoiceschanged = handleVoicesChanged;

    // Chromium sometimes needs an extra tick before voices appear.
    const timer = window.setTimeout(hydrateVoices, 250);

    return () => {
      window.clearTimeout(timer);
      synth.removeEventListener("voiceschanged", handleVoicesChanged);
      if (synth.onvoiceschanged === handleVoicesChanged) {
        synth.onvoiceschanged = null;
      }
    };
  }, [hydrateVoices]);

  const stopSpeaking = useCallback(() => {
    if (canUseSpeechSynthesis()) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  const handlePlayback = useCallback(() => {
    if (!canUseSpeechSynthesis() || !routeData || !isActive) {
      return;
    }

    if (isSpeaking) {
      stopSpeaking();
      return;
    }

    hydrateVoices();

    // Prefer live Gemini Devanagari; fall back to local templates.
    const spokenText =
      liveBriefing?.audio_speech_text ||
      getRegionalSpeechUtteranceText(routeData);
    const utterance = new window.SpeechSynthesisUtterance(spokenText);
    utterance.rate = 0.92;
    utterance.pitch = 1;
    utterance.lang = "hi-IN";

    const voice =
      voices.find(
        (item) =>
          item.voiceURI === selectedVoiceURI && isGoogleHindiVoice(item),
      ) ??
      rankVoices(window.speechSynthesis.getVoices())[0]?.voice ??
      null;

    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang.toLowerCase().startsWith("hi") ? voice.lang : "hi-IN";
    }

    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setIsSpeaking(true);
  }, [
    hydrateVoices,
    isActive,
    isSpeaking,
    routeData,
    selectedVoiceURI,
    stopSpeaking,
    voices,
    liveBriefing,
  ]);

  useEffect(() => {
    stopSpeaking();
    return () => {
      if (canUseSpeechSynthesis()) {
        window.speechSynthesis.cancel();
      }
    };
  }, [routeData, stopSpeaking]);

  useEffect(() => {
    if (!isActive) stopSpeaking();
  }, [isActive, stopSpeaking]);

  if (!isActive || !routeData) {
    return null;
  }

  const caption =
    liveBriefing?.on_screen_caption || getRegionalSpeechText(routeData);

  return (
    <div className="gov-card p-4">
      <p className="gov-kicker">Audio briefing</p>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Hindi (Devanagari) readout with an Indian voice. Install Google Hindi
        in Chrome if the list is empty.
      </p>

      <label htmlFor="indian-voice-select" className="gov-label mt-3">
        Voice
      </label>
      <select
        id="indian-voice-select"
        value={selectedVoiceURI}
        onChange={(event) => setSelectedVoiceURI(event.target.value)}
        className="gov-select"
      >
        {indianRanked.length === 0 && (
          <option value="">Google Hindi voice not found</option>
        )}
        {indianRanked.map((entry) => (
          <option key={entry.voice.voiceURI} value={entry.voice.voiceURI}>
            {entry.label}
          </option>
        ))}
      </select>

      {!hasIndianVoice && (
        <div className="gov-notice gov-notice-warn mt-3 flex gap-2 text-xs">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            Google हिंदी voice not detected. In Chrome: Settings → Languages →
            add Hindi, then refresh this page.
          </p>
        </div>
      )}

      {selectedVoice && (
        <p className="gov-meta mt-2">
          Active: {selectedVoice.name} · {selectedVoice.lang}
        </p>
      )}

      <button
        type="button"
        onClick={handlePlayback}
        className="gov-btn gov-btn-primary mt-4 w-full"
      >
        {isSpeaking ? (
          <Square className="h-4 w-4 fill-current" aria-hidden />
        ) : (
          <Volume2 className="h-4 w-4" aria-hidden />
        )}
        {isSpeaking ? "Stop briefing" : "Listen to briefing"}
      </button>

      <p className="mt-3 border border-[var(--line)] bg-white p-3 text-xs leading-relaxed text-[var(--muted)]">
        {caption}
      </p>
    </div>
  );
}
