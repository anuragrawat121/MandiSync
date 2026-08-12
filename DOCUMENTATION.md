# MandiSync — Deep Technical Documentation

**Version:** 1.0.0  
**Audience:** engineers, product, and operators who need to understand the full stack: database, arbitrage math, FastAPI, Next.js dashboard, speech companion, and Gemini live briefings.

This document describes the system **as implemented in this repository**, not a future roadmap dressed up as current behavior.

---

## 1. Product thesis

MandiSync is a **pan-India crop arbitrage and logistics advisor** for Farmer Producer Organizations (FPOs) and regional transporters.

It answers three farmer-first questions:

1. **Where should I sell this crop today?**  
   Compare modal wholesale prices across APMC hubs.
2. **Is the spread still profitable after trucking?**  
   Subtract a realistic FTL haul cost from the price gap.
3. **Who do I call when the truck arrives?**  
   Surface verified commission agents at the destination mandi, plus a spoken briefing.

The product is **not** a generic price ticker. A route is only shown if **net profit after transit is positive**. A briefing is only generated for a **single selected corridor**, not for the entire nationwide list.

### 1.1 What “AI” means in this app

There are **two layers** people casually call AI:

| Layer | What it actually is | Generates new decisions? |
|---|---|---|
| **Arbitrage engine** | Deterministic SQL + PostGIS + decimal math | No. Same inputs always yield the same routes. |
| **Gemini briefing** | Live LLM (`gemini-3.5-flash`) | Yes, for *language and logistics advice only*. It must not invent new prices. |
| **Audio Companion** | Browser `SpeechSynthesis` + Google Hindi TTS | No. It reads text. |

Gemini **narrates** a route the math engine already computed. It does **not** pick the route, compute distance, or invent agent phone numbers.

---

## 2. System architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser  (Next.js 15 + React 19 + Leaflet + Web Speech API)    │
│  http://localhost:3000                                          │
│                                                                 │
│  page.tsx ──GET /api/arbitrage/?crop_name=Onion                 │
│           ──POST /api/arbitrage/briefing   (selected route)     │
│           ──SpeechSynthesis.speak(Devanagari Hindi)             │
└────────────────────────────┬────────────────────────────────────┘
                             │ CORS open for local Next.js
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI  (Uvicorn)  http://127.0.0.1:8000                      │
│                                                                 │
│  routers/arbitrage.py                                           │
│     ├─ calculate_crop_arbitrage()   services/arbitrage_engine.py│
│     └─ generate_live_briefing()     services/gemini_agent.py    │
│              │                              │                   │
│              ▼                              ▼                   │
│        PostgreSQL + PostGIS          Google Gemini API          │
│        mandis / crop_prices          gemini-3.5-flash           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Why the API key lives on the backend

`GEMINI_API_KEY` is loaded from `Backend/.env` via `python-dotenv`.  
The Next.js client **never** receives the key. The browser only posts route facts and receives two strings.

If the key were placed in `NEXT_PUBLIC_*`, anyone could extract it from the JS bundle.

---

## 3. Repository map

```
MandiSync/
├── docker-compose.yml          PostGIS 15 container
├── README.md                   Short product intro
├── DOCUMENTATION.md            This file
├── Backend/
│   ├── .env                    GEMINI_API_KEY (gitignored)
│   ├── .gitignore
│   ├── requirements.txt
│   ├── main.py                 FastAPI app + CORS + dotenv
│   ├── database.py             Engine, SessionLocal, create_all
│   ├── models.py               Mandi, CropPrice
│   ├── seed.py                 Pan-India market simulator
│   ├── routers/arbitrage.py    HTTP surface
│   └── services/
│       ├── arbitrage_engine.py Deterministic optimizer
│       └── gemini_agent.py     Live LLM + fallback templates
└── frontend/
    ├── package.json
    ├── next.config.ts
    ├── tailwind.config.ts
    ├── app/
    │   ├── layout.tsx          Fonts + Leaflet CSS CDN
    │   ├── globals.css         Viewport lock + Leaflet fill
    │   └── page.tsx            Farmer-first dashboard
    ├── components/
    │   ├── ArbitrageMap.tsx    Client-only Leaflet map
    │   └── AudioBriefing.tsx   TTS controller
    ├── lib/types.ts            Shared TypeScript contracts
    └── utils/speechUtils.ts    Local Hinglish / Hindi templates
```

Windows paths are case-insensitive; the folders may appear as `Backend` / `backend` or `Frontend` / `frontend`.

---

## 4. Data layer (PostgreSQL + PostGIS)

### 4.1 Runtime

| Item | Value |
|---|---|
| Image | `postgis/postgis:15-3.3` |
| Container | `mandisync_postgres` |
| Database | `mandisync_db` |
| User / password | `postgres` / `mandisync_password` |
| Port | `5432` |
| Connection URL | `postgresql://postgres:mandisync_password@localhost:5432/mandisync_db` |

`database.py` creates a SQLAlchemy engine, a `SessionLocal` factory (`autocommit=False`, `autoflush=False`), and a `get_db()` context manager that always closes the session.

On import it runs `Base.metadata.create_all(bind=engine)`. That **creates missing tables**; it does **not** migrate existing columns. `seed.py` therefore runs `ALTER TABLE mandis ADD COLUMN IF NOT EXISTS verified_agents ...`.

### 4.2 Table: `mandis`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Identity |
| `name` | String | e.g. `Lasalgaon APMC` |
| `state` | String | Farmer filter key |
| `district` | String | Administrative district |
| `coordinates` | `Geometry(POINT, 4326)` | **WKT order is longitude, latitude** |
| `verified_agents` | JSON / JSONB | Array of `{name, phone, license_id}` |

Bidirectional relationship: `Mandi.crop_prices` ↔ `CropPrice.mandi`.

### 4.3 Table: `crop_prices`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `mandi_id` | FK → `mandis.id` | |
| `crop_name` | String | `Onion`, `Tomato`, `Potato` |
| `variety` | String | e.g. `Red Nasik`, `Hybrid`, `Jyoti` |
| `modal_price_per_quintal` | Numeric | INR / quintal |
| `price_date` | Date | Seeded as “today” |
| `updated_at` | DateTime | UTC |

### 4.4 The PostGIS coordinate trap

Humans say Delhi as **28.71°N, 77.18°E** (lat, lon).  
PostGIS WKT is **`POINT(longitude latitude)`** → `POINT(77.18 28.71)`.

If inverted, Leaflet markers land in the Indian Ocean or Antarctica.

- Storage / WKT: **lon, lat**
- Leaflet / API payload: **`[lat, lng]`** via `ST_Y` then `ST_X`

### 4.5 Seeded universe (`seed.py`)

The “Advanced Indian Agricultural Market Simulator” truncates `crop_prices` and `mandis`, then inserts:

- **18 APMC hubs** across **10 states** (the listed coordinate set has 18 markets, not 15)
- **2–3 verified agents** per hub, regionally named
- **54 price rows** (3 crops × 18 mandis)

Hardcoded surplus / deficit corridors:

| Crop | Cheap origins | Expensive destinations |
|---|---|---|
| Onion | Lasalgaon, Mandsaur (~₹1,050–1,180) | Sahibabad, Bengaluru, Howrah (~₹2,780–3,100) |
| Potato | Khanna, Agra (~₹820–950) | Vashi, Guntur (~₹2,380–2,450) |
| Tomato | Kolar, Pune (~₹1,420–1,550) | Jaipur, Sahibabad (~₹3,050–3,200) |

Re-seed:

```bash
cd Backend
python seed.py
```

---

## 5. Arbitrage engine (deterministic core)

File: `Backend/services/arbitrage_engine.py`  
Entry: `calculate_crop_arbitrage(db_session, crop_name) -> list[dict]`

### 5.1 Algorithm

1. Load all `CropPrice` rows for `crop_name`, `joinedload` the parent `Mandi`.
2. For every ordered pair `(source, destination)` where `mandi_id` differs:
   - `gross_spread = dest_modal − source_modal`
   - Skip if `gross_spread ≤ 0` (not buy-low / sell-high).
   - `distance_km = ST_DistanceSphere(src.geom, dst.geom) / 1000`
   - `total_truck_cost = distance_km × ₹25`
   - `transit_cost_per_quintal = total_truck_cost / 100`
   - `net_profit = gross_spread − transit_cost_per_quintal`
   - Keep only if `net_profit > 0`.
3. Sort by `net_profit` descending.

### 5.2 Constants and why they exist

| Constant | Value | Meaning |
|---|---|---|
| `TRUCK_RATE_PER_KM_INR` | `25` | Commercial truck hire, INR / km |
| `TRUCK_CAPACITY_QUINTALS` | `100` | ~10 MT FTL (1 tonne = 10 quintals) |

Prices are **per quintal**. A full truck trip of 1,000 km costs ~₹25,000. Subtracting that from a ₹1,600/qtl spread would always look unprofitable. Amortizing over 100 quintals makes the comparison economically honest:

```
transit/qtl = (km × 25) / 100 = km × 0.25
```

Example: Lasalgaon → Sahibabad ~1,100 km → transit ≈ ₹275/qtl.

### 5.3 Distance model

`ST_DistanceSphere` is **great-circle**, not road network distance. It is good enough for ranking corridors. It will understate real NH/state-highway km, especially around ghats or flooded monsoon stretches. Gemini’s briefing may mention monsoon delay; the **numeric km on the card is still spherical**.

### 5.4 Output object (`ArbitrageOpportunity`)

```json
{
  "crop_name": "Onion",
  "source_mandi": "Lasalgaon APMC",
  "destination_mandi": "Sahibabad APMC",
  "source_state": "Maharashtra",
  "destination_state": "Uttar Pradesh",
  "source_price_per_quintal": 1050.0,
  "destination_price_per_quintal": 2950.0,
  "gross_spread": 1900.0,
  "distance_km": 1100.12,
  "transit_cost": 275.03,
  "net_profit": 1624.97,
  "source_coordinates": [20.14, 74.23],
  "destination_coordinates": [28.66, 77.34],
  "destination_verified_agents": [
    { "name": "Gupta Fresh Mandi", "phone": "+91 ...", "license_id": "APMC-UP-SHB-2024-44A" }
  ]
}
```

`source_coordinates` / `destination_coordinates` are Leaflet order: **`[latitude, longitude]`**.

---

## 6. Backend HTTP API

Entrypoint: `Backend/main.py`

- Loads `.env` **before** importing routers (so Gemini sees `GEMINI_API_KEY`).
- CORS: all origins, all methods, all headers, `allow_credentials=False` (required when origins are `*`).
- Router prefix: `/api/arbitrage`.

### 6.1 `GET /health`

```json
{ "status": "ok" }
```

Does not check Postgres or Gemini.

### 6.2 `GET /api/arbitrage/?crop_name=Onion`

**Query**

| Param | Required | Rules |
|---|---|---|
| `crop_name` | yes | Non-empty after strip |

**Behavior**

- 422 if empty
- 404 if no `crop_prices` row exists for that name
- 500 on unexpected engine errors
- 200 with `{ crop_name, route_count, routes }`

This endpoint is **intentionally not** calling Gemini. A nationwide Onion query can return 100+ routes. Invoking an LLM per route would be slow and expensive. Gemini runs only on **one selected card**.

### 6.3 `POST /api/arbitrage/briefing`

**Body** (`RouteBriefingRequest`)

Required: crop, mandi names/states, prices, `distance_km`, `transit_cost`, `net_profit`.  
Optional: `gross_spread`, `destination_verified_agents`, `agent_name`.

**Response**

```json
{
  "crop_name": "Onion",
  "source_mandi": "Lasalgaon APMC",
  "destination_mandi": "Sahibabad APMC",
  "on_screen_caption": "Roman Hinglish strategy...",
  "audio_speech_text": "देवनागरी हिंदी...",
  "source": "gemini",
  "model": "gemini-3.5-flash"
}
```

If Gemini is down:

```json
{
  "source": "fallback",
  "warning": "Gemini unavailable — using simulation text (ClientError).",
  "on_screen_caption": "...",
  "audio_speech_text": "..."
}
```

HTTP status stays **200** on fallback. The UI must never crash because the LLM failed.

---

## 7. AI integration (Gemini) — deep dive

File: `Backend/services/gemini_agent.py`  
SDK: `google-genai==2.17.0` (`from google import genai`)

### 7.1 Model choice

| Tried | Result on a new API key |
|---|---|
| `gemini-2.5-flash` | `404` — “no longer available to new users” |
| `gemini-3.5-flash` | **Works** — current stable Flash |
| `gemini-3.1-flash-lite` | Works (cheaper alternative) |

Constant: `GEMINI_MODEL = "gemini-3.5-flash"`.

### 7.2 Client initialization

```python
client = genai.Client()  # reads GEMINI_API_KEY from the environment
response = await client.aio.models.generate_content(...)
```

Async is used so FastAPI does not block the event loop during the network call.

### 7.3 Prompt contract

The model is instructed to act as an **Indian Agri-Logistics Agent** for FPOs.

It receives **only facts the math engine already computed**:

- crop, source/destination mandi + state
- buy / sell / transit / net profit
- first destination agent name
- seasonal / monsoon context from calendar month

It is **forbidden** to invent different numbers.

Season helper (`_current_season_context`):

| Months | Context injected into the prompt |
|---|---|
| Jun–Sep | Southwest monsoon — wet highways, tomato spoilage |
| Oct–Nov | Post-monsoon / Kharif arrivals |
| Dec–Feb | Winter / Rabi; North India fog |
| Mar–May | Pre-monsoon heat; early-morning tomato dispatch |

### 7.4 Required JSON fields

| Field | Script | Consumer |
|---|---|---|
| `on_screen_caption` | Roman Hinglish | Insights panel + caption box |
| `audio_speech_text` | Devanagari Hindi | `SpeechSynthesisUtterance` |

Why two fields? Latin Hinglish read by a US/UK voice sounds foreign. Devanagari + `hi-IN` / Google Hindi TTS sounds native.

Constraints in the prompt: max 3 sentences each, JSON under ~700 characters. Gemini 3.5 Flash otherwise spends a large **thinking** budget and can emit truncated JSON (extra `}` or cut strings).

Generation config:

- `temperature=0.6`
- `response_mime_type="application/json"`
- `max_output_tokens=2048`
- `thinking_config=ThinkingConfig(thinking_budget=0)` — disables hidden reasoning tokens that starved the visible JSON

### 7.5 Parser resilience

`_parse_model_json`:

1. Strip markdown fences if present
2. `json.loads`
3. On failure, `JSONDecoder().raw_decode` from the first `{` (tolerates a trailing extra `}`)
4. Regex object extract as last resort
5. Accept a one-element list of objects
6. Require both strings non-empty

`_response_text` reads `response.text` or walks `candidates[].content.parts[].text`.

### 7.6 Fallback simulation

`fallback_briefing()` is the original dialect engine:

- **Haryana** — Haryanvi-style Hinglish + matching Devanagari
- **Punjab** — Punjabi-style Hinglish + Devanagari
- **Default** — standard conversational Hinglish + Devanagari

Triggered when:

- `GEMINI_API_KEY` missing
- HTTP 429 / quota / rate limit
- unusable JSON
- any other `ClientError` / network exception

The router has a **second** try/except that also calls `fallback_briefing`.

### 7.7 What Gemini is allowed to add

Allowed: monsoon warning, tarpaulin / spoilage advice, “call this agent on arrival”, urgency of dispatch.

Not allowed: changing ₹ figures, inventing a different destination, inventing phone numbers (phones stay on the agent cards from the database).

### 7.8 Cost / latency characteristics

- One Gemini call **per route card click**
- AbortController on the frontend cancels the HTTP request if the user clicks another card (the server may still complete the Gemini call)
- No caching yet — clicking the same card again re-bills

---

## 8. Frontend architecture

Stack: **Next.js 15 App Router**, **React 19**, **TypeScript**, **Tailwind 3**, **Leaflet 1.9** via **react-leaflet 5**, **lucide-react**.

### 8.1 Viewport lock (critical UX)

The dashboard is a **laptop-screen app**, not a scrolling marketing page.

| Element | Layout rule |
|---|---|
| `html, body` | `height: 100%; overflow: hidden` |
| `main` | `h-screen w-screen overflow-hidden flex flex-col` |
| Left panel | `lg:w-1/3`, filters `shrink-0`, list `overflow-y-auto` |
| Right panel | `lg:w-2/3 h-full overflow-hidden` |
| Map | fixed `h-[60%]` with `absolute inset-0` Leaflet fill |
| Insights / agents | `h-[40%] overflow-y-auto` |

If you use `min-h-screen` without `overflow-hidden`, scrolling the page **shifts the map** and leaves a blank band. That bug was fixed by locking the viewport and scrolling only inner panes.

### 8.2 Farmer-first filtering

Nationwide Onion can exceed **130 routes**. The sidebar would be unusable.

State in `page.tsx`:

- `selectedState` — default `Maharashtra`
- `crop` — `Onion` | `Tomato` | `Potato`
- `routes` — full API list (already profit-sorted)
- `filteredRoutes` — `routes.filter(r => r.source_state === selectedState)`
- `selectedRoute` — clicked card

Empty copy: *“No profitable routes found from this state today…”*

Cards show a badge: **`[Source State] to [Destination State]`**.

### 8.3 Data fetching

**Routes**

```
GET http://localhost:8000/api/arbitrage/?crop_name=Onion
```

Triggered when `crop` changes. Clears `selectedRoute` and `liveBriefing`.

**Live briefing**

```
POST http://localhost:8000/api/arbitrage/briefing
body: selectedRoute (full JSON)
```

Triggered when `selectedRoute` is set. `briefingLoading` drives “Gemini drafting live briefing…”.  
`liveBriefing.source === "gemini"` vs `"fallback"` is shown in the insights header.

`API_BASE_URL` defaults to `http://localhost:8000` (`lib/types.ts`). Override with `NEXT_PUBLIC_API_BASE_URL` if needed.

### 8.4 Map (`components/ArbitrageMap.tsx`)

Loaded with:

```ts
dynamic(() => import("@/components/ArbitrageMap"), { ssr: false })
```

Leaflet touches `window`. SSR would crash the Next build.

Behavior:

- Center India `[20.5937, 78.9629]`, zoom 5
- OSM tile layer
- On selection: `flyToBounds` between source and dest
- Green pin **S** = buy / source
- Red pin **D** = sell / destination
- Blue polyline = haul corridor

Leaflet CSS is injected in `app/layout.tsx` from the unpkg CDN so markers/grids render.

### 8.5 Contact cards

`destination_verified_agents` → Call (`tel:`) and WhatsApp (`https://wa.me/<digits>`).  
Field name is **`phone`**, not `mobile`.

### 8.6 Audio Companion (`AudioBriefing.tsx`)

Props: `routeData`, `isActive`, optional `liveBriefing`.

Playback:

1. If speaking → `speechSynthesis.cancel()`
2. Else speak `liveBriefing.audio_speech_text` **or** local `getRegionalSpeechUtteranceText(route)`
3. Rate `0.92`, lang `hi-IN`
4. Voice filter: **Google Hindi only** (`name` contains `google` and Hindi/`hi-IN`)
5. Cleanup on route change / unmount / `isActive=false`

Why Google Hindi only: Microsoft Hemant/Kalpana and `en-IN` still often read mixed copy with a foreign cadence. Google हिंदी + Devanagari is the most reliable on Chrome.

If that voice is missing, the widget warns the user to add Hindi in Chrome language settings.

### 8.7 Local speech templates (`utils/speechUtils.ts`)

Still used when:

- briefing has not returned yet and the user hits Listen early
- Gemini fell back and the frontend still wants a local caption
- offline / API down (caption only if the POST failed entirely)

`getRegionalSpeechText` = on-screen Hinglish  
`getRegionalSpeechUtteranceText` = Devanagari for TTS

---

## 9. End-to-end user journey

```
Farmer opens localhost:3000
        │
        ├─ Selects Source State = Haryana
        ├─ Selects Crop = Potato
        │
        ▼
GET /api/arbitrage/?crop_name=Potato
        │
        ▼
Sidebar shows only routes with source_state === "Haryana"
sorted by net_profit
        │
        ├─ Clicks "Sirsa APMC → Vashi APMC"
        │
        ├─ Map flies: green Sirsa, red Vashi, blue line
        ├─ Agent cards render Vashi traders
        │
        └─ POST /api/arbitrage/briefing
                 │
                 ├─ Gemini 3.5 Flash (or fallback)
                 ▼
           Insights show Hinglish strategy
           Listen speaks Devanagari with Google Hindi
```

---

## 10. Local runbook

### 10.1 Prerequisites

- Docker Desktop
- Python 3.12+ (developed against 3.14 locally; pin SQLAlchemy ≥ 2.0.40 on 3.14)
- Node.js 20+
- Chrome recommended for Google Hindi TTS
- Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### 10.2 Database

```bash
docker compose up -d
```

### 10.3 Backend

```bash
cd Backend
python -m pip install -r requirements.txt
# create Backend/.env:
# GEMINI_API_KEY=your_key_here
python seed.py
uvicorn main:app --reload --port 8000
```

Correct binary name is **`uvicorn`**, not `unicorn`.  
Flag is **`--reload`**, not `--reaload`.

### 10.4 Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 10.5 Verify

| Check | Expected |
|---|---|
| `GET http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| `GET .../api/arbitrage/?crop_name=Onion` | `route_count` > 0 |
| Click a card | Insights say **Live Gemini briefing** |
| Listen | Hindi voice, not US/UK English |

---

## 11. Environment and secrets

| Variable | Where | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | `Backend/.env` | Gemini Developer API |
| `DATABASE_URL` | hardcoded in `database.py` | Local Docker Postgres |
| `NEXT_PUBLIC_API_BASE_URL` | optional frontend env | Override API host |

`Backend/.gitignore` excludes `.env`. **Never commit keys. Never paste keys into chat.** If a key was exposed, revoke it in AI Studio and issue a new one.

---

## 12. Error catalogue

| Symptom | Likely cause | Fix |
|---|---|---|
| `unicorn` not recognized | Typo | Use `uvicorn` |
| Empty compose / Docker pipe error | Docker Desktop off | Start Docker, then `docker compose up -d` |
| `pg_config` / psycopg2 build fail | Python 3.14 + old pin | Install newer `psycopg2-binary` wheel |
| SQLAlchemy `Can't replace canonical symbol` | SQLAlchemy 2.0.30 on 3.14 | Upgrade SQLAlchemy |
| Markers in the ocean | lon/lat swapped | WKT must be `POINT(lon lat)` |
| 131 cards, unusable sidebar | No state filter | Use Source State dropdown |
| Map jumps / blank bottom | Page scroll | Viewport lock classes |
| `/_next/static/... 404` | Stale `.next` after HMR | Delete `.next`, restart `npm run dev`, hard refresh |
| 404 crop | Unknown `crop_name` | Use Onion / Tomato / Potato |
| Briefing says Simulation | Missing key, quota, or parse fail | Check `.env`, restart uvicorn |
| `gemini-2.5-flash` 404 | New-user block | App already uses `gemini-3.5-flash` |
| US accent on Listen | Latin Hinglish + English voice | Need Devanagari + Google Hindi voice pack |
| CORS errors | API not on 8000 | Start uvicorn; check `API_BASE_URL` |

---

## 13. Security and production gaps

This is a **local production-grade prototype**, not a hardened SaaS.

Still missing for production:

- AuthN/AuthZ (anyone can hit `/api/arbitrage`)
- Rate limiting on `/briefing` (LLM cost abuse)
- Input size limits / schema hardening on agent JSON
- Secrets manager instead of `.env` on disk
- Restricted CORS origins
- TLS
- Road-network distances (OSRM / Google Routes)
- Live Agmarknet/eNAM ingestion instead of seeded prices
- Briefing cache keyed by `(crop, source, dest, price_date)`
- Structured logging and tracing of Gemini latency/tokens
- Tests (engine unit tests, router contract tests, TTS-less frontend tests)

---

## 14. Design decisions (why it is built this way)

1. **Math first, language second.** Farmers must trust the ₹ figures. An LLM that “optimizes” prices would hallucinate profit.
2. **Gemini only on the selected route.** Cost, latency, and UX all demand it.
3. **Fallback templates are first-class.** The dashboard stays useful offline / over quota.
4. **Devanagari for speech, Hinglish for reading.** Two audiences: ears vs. screen literacy.
5. **State filter before crop list.** A Haryana potato farmer does not need Bengaluru→Guntur onion routes.
6. **Agents on the destination, not the source.** The farmer already knows their home yard; they need the buyer at the far end.
7. **₹25/km amortized over 100 qtl.** Matches how FPOs think about a full truck, not a single bag.

---

## 15. API quick reference

```
GET  /health
GET  /api/arbitrage/?crop_name={Onion|Tomato|Potato}
POST /api/arbitrage/briefing
     {
       crop_name, source_mandi, destination_mandi,
       source_state, destination_state,
       source_price_per_quintal, destination_price_per_quintal,
       distance_km, transit_cost, net_profit,
       destination_verified_agents?
     }
```

Interactive docs while Uvicorn is running: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 16. Glossary

| Term | Meaning |
|---|---|
| APMC | Agricultural Produce Market Committee yard |
| Modal price | Typical traded wholesale price (not min/max) |
| Quintal | 100 kg |
| FTL | Full truck load |
| Mandi | Wholesale market |
| Commission agent | Licensed trader who takes delivery / pays the farmer |
| SRID 4326 | WGS84 lon/lat used by GPS and Leaflet |
| Gross spread | Destination price − source price |
| Net profit (app) | Gross spread − transit per quintal |

---

*End of document. For a one-page overview see `README.md`.*
