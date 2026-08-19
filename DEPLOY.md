# Deploy MandiSync — free stack (GitHub Pages + Render + Supabase)

Hugging Face **Docker / Gradio Spaces are paid** now. Do not use them.

₹0 path:

| Piece | Host |
|-------|------|
| Website | GitHub Pages |
| API + daily ingest | Render free web service |
| Database | Supabase Postgres + PostGIS |

**Catch:** Render **sleeps after ~15 minutes** with no visitors. The next open can take 30–60 seconds. Supabase can **pause** after about a week unused — click **Resume**.

Do this order: **Supabase → Render → GitHub Pages**.

---

## 1. Supabase — free database

1. Open https://supabase.com → log in with GitHub
2. **New project** → name `mandisync` → invent a database password and **save it** → plan **Free**
3. Wait until **Active**
4. Left menu → **SQL Editor** → **New query** → **Run**:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

5. **Project Settings** (gear) → **Database** → connection **URI**
6. Use **Direct connection** (port **5432**, host like `db.xxxxx.supabase.co`)
   - Do **not** use port **6543**
7. Copy into Notepad:

```text
postgresql://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

---

## 2. Render — free API (not Hugging Face)

1. Open https://render.com → **Get Started** → log in with **GitHub**
2. **New +** → **Web Service**
3. Connect repo **`anuragrawat121/MandiSync`**
4. Fill:

| Field | Value |
|-------|--------|
| Name | `mandisync-api` |
| Language / Runtime | **Python 3** |
| Branch | `main` |
| **Root Directory** | `Backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | `python scripts/entrypoint.py` |
| Instance type | **Free** |

5. **Environment variables** (Add):

| Name | Value |
|------|--------|
| `DATABASE_URL` | Supabase URI from step 1 |
| `API_KEY` | long random secret (same value on GitHub Pages) |
| `AGMARKNET_API_KEY` | data.gov.in key, or empty until the portal is back |
| `ALLOWED_ORIGINS` | `https://anuragrawat121.github.io` |
| `ALLOW_SEED_FALLBACK` | `false` |
| `SKIP_DB_INIT_ON_IMPORT` | `true` |
| `RUN_INGEST_LOOP` | `true` |
| `INGEST_START_DELAY_SECONDS` | `90` |
| `PYTHONPATH` | `.` |
| `DB_WAIT_SECONDS` | `180` |

6. Click **Deploy Web Service**
7. Wait until deploy is **Live** (5–10 minutes)
8. Render shows a URL like:

```text
https://mandisync-api.onrender.com
```

9. Open:

```text
https://mandisync-api.onrender.com/health
```

You want `{"status":"ok"}`.

First request after sleep can be slow. If `/health` fails, open **Logs**.

Common log problems:

- Supabase paused → Resume in Supabase, then **Manual Deploy** on Render
- Wrong `DATABASE_URL` or used port 6543
- PostGIS missing → re-run the SQL in step 1

---

## 3. GitHub Pages — free website

Push latest `main` first (this repo must include the Pages workflow).

1. GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Add:

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://mandisync.onrender.com` (your real Render URL, no slash) |
| `NEXT_PUBLIC_API_KEY` | **same** as Render `API_KEY` |

3. **Settings** → **Pages** → Source: **GitHub Actions**
4. **Actions** → **Deploy GitHub Pages** → **Run workflow**

Site: `https://anuragrawat121.github.io/MandiSync/`  
Admin: `https://anuragrawat121.github.io/MandiSync/admin/`

---

## Checklist

- [ ] Supabase Active + PostGIS SQL ran
- [ ] Render web service **Free**, root `Backend`, `/health` OK
- [ ] GitHub Actions secrets point at the Render URL
- [ ] Pages source = GitHub Actions
- [ ] Site loads (first visit after idle can take 1–2 minutes; later visits should be fast)

A GitHub Action pings `/health` every 10 minutes so Render sleeps less often. It uses the same `NEXT_PUBLIC_API_BASE_URL` secret as Pages.

---

## Limits

| Thing | What happens |
|-------|----------------|
| Render free | Sleeps after ~15 min idle; next visit can take 1–2 minutes unless the keep-alive workflow is running |
| Supabase free | Pauses after ~7 days unused; click Resume |
| Hugging Face Docker/Gradio | **Paid** — skip |
| Live Agmarknet prices | Need `AGMARKNET_API_KEY` when data.gov.in is back |
