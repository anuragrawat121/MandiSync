# Deploy MandiSync

## Option A — Docker Compose on a VPS (recommended first deploy)

Works on any Linux VPS with Docker (DigitalOcean, Hetzner, AWS Lightsail, etc.).

### 1. Server prep
```bash
# Ubuntu example
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER   # then re-login
```

### 2. Clone & configure
```bash
git clone https://github.com/anuragrawat121/MandiSync.git
cd MandiSync
cp .env.production.example .env.production
nano .env.production
```

Set at least:
- `POSTGRES_PASSWORD` — strong random string
- `API_KEY` — strong random string (same value used by the UI)
- `AGMARKNET_API_KEY` — from data.gov.in
- `GEMINI_API_KEY` — optional, for live briefings
- `NEXT_PUBLIC_API_BASE_URL` — public API URL, e.g. `http://YOUR_SERVER_IP:8000`
- `ALLOWED_ORIGINS` — public UI origin, e.g. `http://YOUR_SERVER_IP:3000`

### 3. Build & run
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

### 4. Verify
```bash
curl http://YOUR_SERVER_IP:8000/health
# open http://YOUR_SERVER_IP:3000
# admin: http://YOUR_SERVER_IP:3000/admin
```

### 5. Logs
```bash
docker compose -f docker-compose.prod.yml logs -f api ingest web
```

Services:
| Service | Role |
|---------|------|
| `db` | PostGIS |
| `api` | FastAPI (seeds mandis + official contacts on first boot) |
| `ingest` | Daily Agmarknet pull |
| `web` | Next.js UI |

### HTTPS later
Put Caddy/Nginx in front of `:3000` and `:8000`, then update `ALLOWED_ORIGINS` and rebuild `web` with the HTTPS API URL.

---

## Option B — Local production smoke test
```powershell
cd MandiSync
copy .env.production.example .env.production
# edit .env.production with your real keys
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

---

## Option C — Split cloud (later)
- **Frontend** → Vercel (set `NEXT_PUBLIC_API_BASE_URL` + `NEXT_PUBLIC_API_KEY`)
- **API + ingest** → Railway/Render Docker from `Backend/`
- **Database** → managed Postgres **with PostGIS** (Railway plugin, or Supabase with PostGIS, or Neon + extension)

PostGIS is required — plain Postgres without the extension will fail distance queries.

---

## Rotate keys
If `API_KEY`, `GEMINI_API_KEY`, or `AGMARKNET_API_KEY` ever appeared in chat or git history, rotate them before a public deploy.
