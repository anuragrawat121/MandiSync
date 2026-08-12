"""
Live Gemini briefing engine for MandiSync route analysis.

Falls back to the original regional templates if the API key is missing,
rate-limited, or the model returns unusable JSON.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from cachetools import TTLCache
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# In-process TTL cache. Prices are seeded once per day, so 6 hours is enough to
# stop repeat Gemini spend when a farmer re-clicks the same corridor, without
# serving yesterday's briefing into the next market session.
# Later swap: replace this TTLCache with Redis get/set (same key + TTL) when
# Redis is added to docker-compose.yml — one-line storage change, not a rewrite.
_BRIEFING_CACHE: TTLCache = TTLCache(maxsize=256, ttl=6 * 60 * 60)

# 2.5 Flash is blocked for new API keys; 3.5 Flash is the current stable flash model.
GEMINI_MODEL = "gemini-3.5-flash"

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _current_season_context() -> str:
    month = date.today().month
    if month in (6, 7, 8, 9):
        return (
            "Southwest monsoon (June-September). Expect wet highways, "
            "possible delays on NH corridors, and higher spoilage risk for tomato."
        )
    if month in (10, 11):
        return (
            "Post-monsoon / Kharif arrivals. Roads usually clearer; "
            "onion and potato stocks start building in surplus belts."
        )
    if month in (12, 1, 2):
        return (
            "Winter / Rabi harvest window. Fog can slow North India night trucking; "
            "potato movement from Punjab-UP is typically strong."
        )
    return (
        "Pre-monsoon summer. Heat stress on perishable tomato loads; "
        "plan early-morning dispatch and avoid long uncovered hauls."
    )


def _first_agent_name(route_data: dict[str, Any]) -> str:
    """
    Never treat seeded fiction as a real person to call.
    Live / unavailable / demo statuses all fall back to a generic label.
    """
    status = str(route_data.get("agents_status") or "").strip().lower()
    if status in {"unavailable", "demo", ""}:
        return "the destination APMC office (confirm a licensed commission agent on arrival)"
    if route_data.get("agent_name"):
        return str(route_data["agent_name"])
    agents = route_data.get("destination_verified_agents") or []
    if agents and isinstance(agents[0], dict) and agents[0].get("name"):
        return str(agents[0]["name"])
    return "the destination APMC office (confirm a licensed commission agent on arrival)"


def _distance_value(route_data: dict[str, Any]) -> str:
    raw = route_data.get("distance_km", route_data.get("distance", 0))
    try:
        return f"{round(float(raw)):,}"
    except (TypeError, ValueError):
        return "0"


def _money(route_data: dict[str, Any], key: str) -> str:
    try:
        return f"{round(float(route_data.get(key, 0))):,}"
    except (TypeError, ValueError):
        return "0"


def fallback_briefing(route_data: dict[str, Any]) -> dict[str, str]:
    """Original reliable simulation text used when Gemini is unavailable."""
    source_state = str(route_data.get("source_state") or "India")
    source_mandi = str(route_data.get("source_mandi") or "source mandi")
    dest_mandi = str(route_data.get("destination_mandi") or "destination mandi")
    distance = _distance_value(route_data)
    transit = _money(route_data, "transit_cost")
    profit = _money(route_data, "net_profit")
    agent = _first_agent_name(route_data)

    if source_state == "Haryana":
        caption = (
            f"Ram Ram bhaiya! Dekho, aapka maal {source_mandi} se {dest_mandi} ja raha hai. "
            f"Total distance hai {distance} kilometer aur truck ka kharcha aayega lagbhag {transit} rupaye. "
            f"Par dilli ka bazaar bohot tight hai mittar, sab kat-pitat ke aapko har quintal par pure {profit} "
            f"rupaye ka tagda munafa dikh raha hai! Wahan pahunchte hi seedha {agent} se baat kar lena."
        )
        audio = (
            f"राम राम भैया! देखो, आपका माल {source_mandi} से {dest_mandi} जा रहा है। "
            f"कुल दूरी है {distance} किलोमीटर, और ट्रक का खर्चा लगेगा लगभग {transit} रुपये। "
            f"पर दिल्ली का बाज़ार बहुत टाइट है मित्तर — कट-पिटट के बाद भी हर क्विंटल पर पूरे {profit} "
            f"रुपये का तगड़ा मुनाफा दिख रहा है! वहाँ पहुँचते ही सीधा {agent} से बात कर लेना।"
        )
    elif source_state == "Punjab":
        caption = (
            f"Sat Sri Akal bhaiya! Tussi {source_mandi} ton {dest_mandi} da route select kiya hai. "
            f"Bhaada lagega {transit} rupaye, par net profit hai pure {profit} rupaye per quintal! "
            f"Khush ho jao, aur mandi pahunch ke sidha {agent} nu call mila lena."
        )
        audio = (
            f"सत श्री अकाल भैया! तुसीं {source_mandi} तों {dest_mandi} दा रूट चुन्या है। "
            f"भाड़ा लगेगा {transit} रुपये, पर नेट प्रॉफिट है पूरे {profit} रुपये प्रति क्विंटल! "
            f"खुश हो जाओ, और मंडी पहुँच के सीधा {agent} नूं कॉल मिला लेना।"
        )
    else:
        caption = (
            f"Namaste! Aapne {source_mandi} se {dest_mandi} ka route choose kiya hai. "
            f"Yeh lagbhag {distance} kilometer ka safar hai. Truck ka kharcha around {transit} "
            f"rupaye per quintal padega. Iske baad bhi aapko har quintal par lagbhag {profit} "
            f"rupaye ka net profit mil sakta hai. Destination pahunchte hi verified agent {agent} "
            f"se contact kar lijiye."
        )
        audio = (
            f"नमस्ते! आपने {source_mandi} से {dest_mandi} का रूट चुना है। "
            f"यह लगभग {distance} किलोमीटर का सफर है। ट्रक का खर्चा करीब {transit} रुपये प्रति क्विंटल पड़ेगा। "
            f"इसके बाद भी आपको हर क्विंटल पर लगभग {profit} रुपये का नेट मुनाफा मिल सकता है। "
            f"मंज़िल पहुँचते ही वेरिफाइड एजेंट {agent} से संपर्क कर लीजिए।"
        )

    return {
        "on_screen_caption": caption,
        "audio_speech_text": audio,
        "source": "fallback",
    }


def _build_prompt(route_data: dict[str, Any]) -> str:
    agent = _first_agent_name(route_data)
    season = _current_season_context()
    return f"""
You are an expert Indian Agri-Logistics Agent advising Farmer Producer Organizations.
Speak like a trusted mandi advisor: practical, urgent, and specific.

ROUTE FACTS (do not invent different numbers):
- Crop: {route_data.get("crop_name", "crop")}
- Source mandi: {route_data.get("source_mandi")} ({route_data.get("source_state")})
- Destination mandi: {route_data.get("destination_mandi")} ({route_data.get("destination_state")})
- Distance: {route_data.get("distance_km", route_data.get("distance"))} km
- Buy price: Rs {route_data.get("source_price_per_quintal")} / quintal
- Sell price: Rs {route_data.get("destination_price_per_quintal")} / quintal
- Transit cost: Rs {route_data.get("transit_cost")} / quintal
- Net profit: Rs {route_data.get("net_profit")} / quintal
- Destination contact guidance: {agent}
- Today's seasonal / monsoon context: {season}

Return ONLY valid JSON with exactly these two string fields:
{{
  "on_screen_caption": "...",
  "audio_speech_text": "..."
}}

Rules:
- on_screen_caption: Roman Hinglish. Actionable logistics warning + strategy
  (timing, spoilage, unloading, who to confirm on arrival). Maximum 3 short sentences.
- Do NOT invent named commission agents, phone numbers, or license IDs.
  If contact guidance is generic, tell the farmer to confirm a licensed agent
  at the destination APMC — never invent a person to call.
- audio_speech_text: The SAME briefing meaning, written strictly in Devanagari Hindi
  so a hi-IN TTS voice sounds native. Maximum 3 short sentences.
  Proper nouns (mandi names) may stay in Latin script.
- Keep the whole JSON under 700 characters. Do not wrap JSON in markdown fences.
""".strip()


def _parse_model_json(raw: str) -> dict[str, str] | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            return None
        try:
            payload, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            match = _JSON_OBJECT_RE.search(text)
            if not match:
                return None
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        payload = payload[0]
    if not isinstance(payload, dict):
        return None

    caption = str(payload.get("on_screen_caption") or "").strip()
    audio = str(payload.get("audio_speech_text") or "").strip()
    if not caption or not audio:
        return None
    return {"on_screen_caption": caption, "audio_speech_text": audio}


def _response_text(response: Any) -> str:
    direct = getattr(response, "text", None)
    if isinstance(direct, str) and direct.strip():
        return direct
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                return part_text
    return ""


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in ("429", "resource_exhausted", "rate limit", "quota", "too many requests")
    )


def _briefing_cache_key(route_data: dict[str, Any]) -> tuple[str, str, str, str]:
    price_date = str(route_data.get("price_date") or date.today().isoformat())
    return (
        str(route_data.get("crop_name") or ""),
        str(route_data.get("source_mandi") or ""),
        str(route_data.get("destination_mandi") or ""),
        price_date,
    )


def _cache_put(key: tuple[str, str, str, str], result: dict[str, Any]) -> None:
    stored = {k: v for k, v in result.items() if k != "cached"}
    _BRIEFING_CACHE[key] = stored


async def generate_live_briefing(route_data: dict[str, Any]) -> dict[str, Any]:
    """Call Gemini Flash for a live briefing; fall back to templates on failure."""
    cache_key = _briefing_cache_key(route_data)
    cached = _BRIEFING_CACHE.get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}

    if not os.getenv("GEMINI_API_KEY"):
        result = fallback_briefing(route_data)
        result["warning"] = "GEMINI_API_KEY missing — using simulation text."
        result["cached"] = False
        _cache_put(cache_key, result)
        return result

    try:
        from google import genai
        from google.genai import types

        client = genai.Client()
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=_build_prompt(route_data),
            config=types.GenerateContentConfig(
                temperature=0.6,
                response_mime_type="application/json",
                max_output_tokens=2048,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        parsed = _parse_model_json(_response_text(response))
        if parsed is None:
            result = fallback_briefing(route_data)
            result["warning"] = "Gemini returned unusable JSON — using simulation text."
            result["cached"] = False
            _cache_put(cache_key, result)
            return result

        result = {
            **parsed,
            "source": "gemini",
            "model": GEMINI_MODEL,
            "cached": False,
        }
        _cache_put(cache_key, result)
        return result
    except Exception as exc:
        result = fallback_briefing(route_data)
        if _is_rate_limit_error(exc):
            result["warning"] = "Gemini rate limit hit — using simulation text."
        else:
            result["warning"] = f"Gemini unavailable — using simulation text ({exc.__class__.__name__})."
        result["cached"] = False
        _cache_put(cache_key, result)
        return result
