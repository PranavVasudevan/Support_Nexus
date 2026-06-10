# TicketAI v2 — Autonomous + HITL Ticket Classification System

An IT-support assistant that **chats with users, classifies their tickets, and
autonomously resolves the ones it safely can** — routing everything else to a
human-in-the-loop (HITL) review queue. Primary classifier is an on-prem,
zero-cost **DistilBERT**; **Gemini Flash 2.0** (free tier) is the fallback.

This build runs **with zero external services** (SQLite + in-memory) so you can
start it on a laptop with just Python + Node — no Docker required. A full
Docker stack (Postgres/Mongo/Redis/MLflow/Grafana) is also included for
production-style scaling.

---

## ⭐ What's new in this build

- **Autonomous resolution that actually *does* something.** When a ticket is an
  auto-resolvable category at high confidence, the system runs a real
  category-specific workflow, records **every step it executed**, and shows the
  user exactly *how* it was fixed (steps, reference id, ETA, follow-up). See
  [How autonomous resolution works](#how-autonomous-resolution-works).
- **Runs without Docker.** SQLite replaces Postgres, an in-memory store replaces
  Redis, Mongo/MLflow are optional. One `pip install`, one `npm start`.
- **Real DistilBERT → Gemini fallback.** The documented "confidence < 0.70 →
  Gemini" behaviour is now actually wired up (it wasn't before).
- **A clean, realistic 130k dataset.** The old dataset leaked the label (the
  category name was literally in every title). The new generator writes tickets
  in natural symptom language so the model learns real signal.
- **Lazy ML imports.** The API boots and serves Gemini-only classification with
  **no torch installed**; install the ML extras only when you want the on-prem
  model.

---

## How it works

```
User message (chat / portal)
        │
        ▼
Intent Detector  ──►  not a ticket?  ──►  friendly conversational reply
        │ (Gemini Flash + rules)
        ▼  ticket  (gather missing fields if needed)
DistilBERT Classifier  (primary — on-prem, $0)
        │  confidence ≥ 0.70 → trust it
        │  confidence < 0.70 → Gemini Flash second opinion
        ▼
Decision Engine
   ├── ≥95% conf  + autonomous category → 🤖 AUTO-RESOLVE (runs workflow, shows steps)
   ├── ≥80% conf                        → 📋 HITL queue (AI suggestion attached)
   └── <80% conf  OR sensitive category → 🔔 Human escalation
        │
        ▼
Agent feedback ──► nightly / manual retraining ──► better model
```

**Sensitive categories** (Payroll, Security, Compliance, Offboarding, Billing)
are **always** sent to a human, regardless of confidence.

---

## How autonomous resolution works

When the Decision Engine picks the autonomous path, `AutonomousResolver`
(`backend/services/autonomous_resolver.py`) runs a workflow for that category and
returns a structured record that the chat UI renders. Example for a VPN ticket:

```
✅ Resolved automatically — here's how:
   Your VPN profile has been reset and fresh credentials issued.
   ✓ Cleared stale VPN session     — removed the locked/half-open tunnel server-side
   ✓ Rotated VPN certificate       — issued a new client certificate
   ✓ Rebuilt your VPN profile      — regenerated the connection profile
   ✓ Emailed the new profile       — sent to your corporate mailbox
   Ref: AUTO-VPN-3F9A21 · VPN Controller
   Next: Re-import the emailed VPN profile and reconnect.
```

Auto-resolvable categories and the system each workflow targets:

| Category | Simulated integration | Outcome |
|----------|----------------------|---------|
| Password_Reset | Okta / Active Directory | Secure reset link emailed |
| Email | Microsoft 365 / Exchange | Mailbox repaired + re-synced |
| Printer | Print server | Queue cleared + spooler restarted |
| Cloud_Storage | OneDrive / SharePoint | Quota raised + access restored |
| VPN | VPN controller | Profile reset + creds re-issued |
| Software_Install | Intune / SCCM | Install job queued (in-progress) |
| Mobile_Device | MDM (Intune / Jamf) | Device sync command sent |
| Performance | Monitoring agent | Diagnostic + cleanup started |

Each workflow is marked with `# → REAL:` comments showing exactly where to drop
in live API calls (ServiceNow, Okta, Intune, M365, …). If a workflow fails, the
ticket automatically falls back to a human queue. Every resolution (with all its
steps) is stored on the `decisions` table for audit.

---

## 🚀 Run it locally (no Docker) — recommended

**Prerequisites:** Python 3.10+ and Node.js 18+. Your Gemini key is already in
`.env`.

### Easiest: the launch scripts

Two PowerShell scripts handle the venv, dependencies, paths, and startup. In
**two separate PowerShell windows** from the project root:

```powershell
.\run_backend.ps1     # window 1 — API on http://localhost:8000 (first run sets up the venv)
.\run_frontend.ps1    # window 2 — UI  on http://localhost:3000 (first run runs npm install)
```

Then open **http://localhost:3000**. Prefer to do it by hand? Use the manual
steps below.

### 1. Backend

```powershell
# from the project root: C:\Users\Suman S A\Desktop\TICKET_UPS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

# start the API (SQLite is created automatically under .\data\app.db)
cd backend
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir .
```

The API is now at **http://localhost:8000** (docs at `/docs`). With no trained
model yet, it classifies via **Gemini Flash** automatically.

### 2. Frontend (new terminal)

```powershell
cd "C:\Users\Suman S A\Desktop\TICKET_UPS\frontend"
npm install
npm start
```

Open **http://localhost:3000**.

### 3. Log in

| User | Password | Sees |
|------|----------|------|
| `client` | `user123` | Support chat (raise & auto-resolve tickets) |
| `admin` | `admin123` | HITL review queue + dashboard |

> **Try it:** log in as `client` and type *"I forgot my password and I'm locked
> out"* → watch it auto-resolve with steps. Then try *"my laptop won't turn on"*
> (HITL) and *"my payslip is wrong"* (human escalation). Log in as `admin` to
> review the queued ones.

---

## 🧠 Train the on-prem DistilBERT model (optional, GPU recommended)

This makes DistilBERT the primary classifier so most tickets cost **$0** (no API
call). A clean dataset is already generated under `./data`.

### 1. Install the ML extras (GPU build of PyTorch)

```powershell
.\.venv\Scripts\Activate.ps1
# NVIDIA GPU (e.g. RTX 3050): install the CUDA build first
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r backend\requirements-ml.txt
```
(No GPU? Skip the CUDA line — `pip install torch` gets the CPU build; training is
slower but works.)

### 2. (Re)generate the dataset if you want — already done for you

```powershell
python scripts\generate_dataset.py          # 100k train / 15k val / 15k test
```

### 3. Train

```powershell
$env:PYTHONPATH = "C:\Users\Suman S A\Desktop\TICKET_UPS\backend"
python scripts\initial_train.py `
  --train-csv data\ticket_train.csv `
  --val-csv   data\ticket_val.csv `
  --epochs 2 --batch-size 16 --max-length 128 `
  --output .\models\distilbert_finetuned
```

> **Flaky network?** If the base-model download from Hugging Face keeps
> resetting, fetch it once with the resilient (resumable) downloader, then point
> training at the local copy:
> ```powershell
> python scripts\download_base_model.py            # → models\base-distilbert
> python scripts\initial_train.py --base-model .\models\base-distilbert `
>   --train-csv data\ticket_train.csv --val-csv data\ticket_val.csv `
>   --epochs 2 --batch-size 16 --max-length 128 --output .\models\distilbert_finetuned
> ```

On an RTX 3050 (4 GB) this takes roughly 20–40 minutes for 2 epochs. For a quick
trial, add `--limit 20000`. When it finishes, **restart the backend** — it will
detect the model and load it (`/health` shows `"model_loaded": true`). From then
on DistilBERT handles classification and Gemini only fires on low confidence.

---

## 🐳 Run the full stack with Docker (optional, for scaling)

```powershell
docker-compose up --build
# scale the API to 4 replicas sharing Redis session state + model volume:
docker-compose up --scale backend=4
```

Docker uses Postgres + MongoDB + Redis + MLflow + Grafana. It injects its own DB
hostnames, so your local `.env` SQLite settings don't interfere.

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat/` | Main chat endpoint (intent → classify → resolve) |
| POST | `/api/tickets/` | Direct ticket submission (non-chat) |
| GET | `/api/review/queue` | HITL pending queue |
| POST | `/api/review/decide` | Agent approve/override decision |
| GET | `/api/review/stats` | HITL stats |
| POST | `/api/admin/retrain` | Manual retrain trigger |
| GET | `/api/admin/model-status` | Model + device status |
| GET | `/api/metrics/dashboard` | Dashboard stats |
| GET | `/api/metrics/prometheus` | Prometheus scrape |
| GET | `/health` | Health check (`model_loaded`) |

## Confidence thresholds

| Confidence | Category type | Action |
|------------|--------------|--------|
| ≥ 95% | autonomous-eligible | 🤖 Auto-resolve (runs workflow) |
| ≥ 80% | any | 📋 HITL queue with AI suggestion |
| < 80% | any | 🔔 Human escalation |

Sensitive categories (Payroll, Security, Compliance, Offboarding, Billing) always
go to a human regardless of confidence. DistilBERT predictions below
`DISTILBERT_FALLBACK_THRESHOLD` (0.70) defer to Gemini Flash.

## Configuration (`.env`)

| Variable | Local default | Meaning |
|----------|---------------|---------|
| `GEMINI_API_KEY` | *(your key)* | Free Gemini Flash key |
| `POSTGRES_URL` | `sqlite+aiosqlite:///./data/app.db` | DB; set a `postgresql://…` URL for Postgres |
| `REDIS_URL` | *(blank)* | blank → in-memory session store |
| `MONGO_URL` | *(blank)* | blank → event logging disabled |
| `MODEL_PATH` | `./models/distilbert_finetuned` | where the trained model is loaded from |
| `DISTILBERT_FALLBACK_THRESHOLD` | `0.70` | below this → Gemini fallback |
| `CONFIDENCE_AUTONOMOUS` / `CONFIDENCE_HITL` | `0.95` / `0.80` | routing thresholds |
| `ENABLE_SCHEDULER` | `false` | nightly auto-retrain |
| `MLFLOW_URI` | *(blank)* | blank → MLflow tracking off |

## Cost

| Component | Cost |
|-----------|------|
| DistilBERT inference | Free (your CPU/GPU) |
| Gemini Flash fallback | Free (1,500 req/day) |
| Databases (SQLite local, or self-hosted Postgres/Mongo/Redis) | Free |
| **Total** | **$0** |
