# MandiSync - Indian Crop Arbitrage & Logistics Router

## Project Goal
An application designed for Indian Farmer Producer Organizations (FPOs) and regional logistics providers. It tracks daily government wholesale market (Mandi) crop prices via Agmarknet/eNAM concepts, identifies profitable price differences across regions, calculates transportation overheads, and provides actionable logistics insights.

## Core Architecture
- **Backend**: FastAPI (Python) — arbitrage math, PostGIS distances, Gemini live briefings.
- **Frontend**: Next.js (TypeScript) + Leaflet — farmer-first split-screen dashboard, map corridors, audio companion.
- **Database**: PostgreSQL + PostGIS — APMC coordinates, daily crop prices, verified commission agents.
- **AI**: Google Gemini 3.5 Flash — Hinglish on-screen strategy + Devanagari speech text. Deterministic math is never delegated to the LLM.

## Deep documentation
Read **[DOCUMENTATION.md](./DOCUMENTATION.md)** for the full stack: schema, seed corridors, arbitrage formulas, API contracts, dashboard layout, TTS accent design, Gemini prompt/fallback, runbook, and production gaps.

## Quick start
```bash
docker compose up -d
cd Backend
# Optional offline demo only — product paths use Agmarknet:
# python seed.py
uvicorn main:app --reload --port 8000

# Pull live prices (requires AGMARKNET_API_KEY in Backend/.env):
python ingest_prices.py --ingest

cd ../Frontend
npm install
npm run dev
```

### Keep prices fresh (Windows)
```powershell
cd Backend\scripts
powershell -ExecutionPolicy Bypass -File .\install_daily_ingest_task.ps1
# Runs daily at 06:30. Logs: Backend\logs\ingest_YYYY-MM-dd.log
```

Live mode does **not** fall back to seed data when Agmarknet is stale
(`ALLOW_SEED_FALLBACK=false`). Set that env var to `true` only for offline demos.

- API: http://127.0.0.1:8000/docs
- UI: http://localhost:3000

Put `GEMINI_API_KEY` and `AGMARKNET_API_KEY` in `Backend/.env` (never commit them).
