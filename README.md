# TicketAI — Hybrid AI Ticket Triage, Routing & Auto-Resolution

A fully **local, zero-cloud** IT-support assistant that **chats with users,
understands their problem, classifies the ticket, routes it to the right
department, and autonomously resolves the ones it safely can** — sending
everything else to a human-in-the-loop (HITL) queue or escalating to a person.

Everything runs on your own machine. **No API keys, no cloud, no per-request
cost** — a fine-tuned **DistilBERT** does fast category classification on CPU,
and a **local Ollama LLM (`qwen2.5:3b`)** handles conversation, solutions, and
translation on your GPU.

---

## ✨ What it does

- **3-way intent detection.** Tells apart a *greeting* ("hi", "bye"), a *bare
  keyword* ("vpn", "payment", "laptop" → asks for details), and a *real ticket*
  → so it never raises a ticket from a single word.
- **Conversational intake with a clarify loop.** After the first message it
  shows a question card tailored to the problem, and keeps asking until it
  genuinely understands the issue (up to 3 rounds) before classifying.
- **Hybrid classification.** Fine-tuned **DistilBERT** (20 categories, ~36 ms on
  CPU) is the primary classifier; the local **Ollama** model is a second opinion
  whenever DistilBERT's confidence is below the threshold (0.70).
- **Department routing.** Every ticket's category maps to one of **5
  departments** (TSG, BASE, HR-GO, HR-BP, Finance). Department agents only ever
  see *their own* categories; shared categories (e.g. Onboarding) appear for all
  owning departments.
- **Autonomous resolution.** For safe, auto-resolvable categories at high
  confidence, the local LLM generates a real step-by-step solution in the user's
  language. Physical-damage / non-IT problems are *never* auto-resolved.
- **Smart guards.** A domain guard catches out-of-domain requests (HR conflicts,
  facilities, etc.) and routes them to a human; a `needs_human` guard catches
  physical damage ("my phone is broken") and sends it to HITL instead of giving
  a useless "go to settings" answer.
- **Full localization.** The *entire* reply — not just the AI content — is
  translated into the user's language.
- **Screenshot OCR.** Users can attach a screenshot; Tesseract extracts the text
  and feeds it into intake.
- **Self-registration.** Each user signs up and sets their own password (JWT +
  bcrypt). Roles: `client`, `department`, `admin`.
- **Rich dashboard.** Trends, category donut, priority mix, SLA gauge, and
  feedback ratio — scoped per department for department agents, global for admin.
- **Operational extras.** SLA watchdog (auto-escalates overdue tickets),
  Prometheus metrics, duplicate detection via embeddings, and an optional
  nightly retrain scheduler.

---

## How it works

```
User message (chat)
        │
        ▼
Intent Detector ──► greeting?      ──► friendly reply
        │         └► bare keyword? ──► "tell me more" (asks for details)
        ▼  real ticket
Intake / Clarify loop  ──► asks tailored questions until the problem is understood
        │
        ▼
Domain guard ──► not an IT issue?  ──► Other / HR / Facilities → 🔔 human
        │
        ▼
DistilBERT Classifier  (primary — on-prem, CPU, $0)
        │  confidence ≥ 0.70 → trust it
        │  confidence < 0.70 → Ollama qwen2.5 second opinion
        ▼
needs_human guard ──► physical damage? ──► 📋 HITL (no auto-resolve)
        │
        ▼
Decision Engine  ──►  routing + department  ──►  one of:
   🤖 AUTONOMOUS   — Ollama generates the solution steps (in the user's language)
   📋 HITL         — queued for the owning department with an AI suggestion
   🔔 HUMAN        — sensitive/out-of-domain → escalated to a person
        │
        ▼
Agent feedback ──► (optional) nightly / manual retraining ──► better model
```

**Sensitive categories** (Payroll, Security, Compliance, Offboarding, Billing,
HR, Facilities, Other) always go to a human regardless of confidence.

---

## 🧱 Tech stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Category classifier** | DistilBERT (fine-tuned, 20 categories) | Fast, on-prem classification on CPU |
| **Conversational LLM** | Ollama `qwen2.5:3b` (GPU) | Intent, clarifying questions, solutions, translation |
| **Embeddings** | Ollama `nomic-embed-text` (768-dim) | Duplicate / similar-ticket detection |
| **Backend** | FastAPI + Uvicorn (async) | REST API, state machine, background tasks |
| **Database** | PostgreSQL 17 (SQLAlchemy async + asyncpg) | Tickets, users, queue, feedback, audit |
| **Frontend** | React (Create React App, single `App.jsx`) | Chat UI, dashboards, admin/department views |
| **Auth** | JWT (PyJWT) + bcrypt | Self-registration, role-based access |
| **OCR** | Tesseract + pytesseract + Pillow | Screenshot → text extraction |
| **Ops** | Prometheus client, APScheduler, asyncio SLA watchdog | Metrics, retrain, escalation |

> The `qwen2.5:3b` model fits entirely in an RTX 3050's 4 GB VRAM → ~64 tok/s on
> GPU. Swap to `qwen2.5:7b` in `.env` for higher accuracy at lower speed.

---

## 🚀 Run it locally

**Prerequisites**

1. **Python 3.11+** and **Node.js 18+**
2. **PostgreSQL 17** running locally with a `tickets_db` database
   (or use the SQLite fallback — see Configuration below).
3. **Ollama** with the models pulled:
   ```powershell
   # install from https://ollama.com/download, then:
   ollama pull qwen2.5:3b
   ollama pull nomic-embed-text
   ```
4. *(Optional, for screenshot OCR)* **Tesseract OCR** installed, with its path
   set in `TESSERACT_CMD`.

### Easiest: the launch scripts

From the project root, in **two separate PowerShell windows**:

```powershell
.\run_backend.ps1     # window 1 — API on http://localhost:8000 (first run builds the venv)
.\run_frontend.ps1    # window 2 — UI  on http://localhost:3000 (first run runs npm install)
```

Then open **http://localhost:3000**.

### Manual backend

```powershell
# from the project root: C:\Users\sanjisuman\Desktop\TICKET_UPS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

cd backend
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir .
```

API docs live at **http://localhost:8000/docs**. On first start the schema is
created and the seed users below are inserted.

### Manual frontend (new terminal)

```powershell
cd "C:\Users\sanjisuman\Desktop\TICKET_UPS\frontend"
npm install
npm start
```

Open **http://localhost:3000**.

---

## 🔑 Seed logins

New users can **self-register** from the login screen. These accounts are seeded
automatically on first startup:

| User | Password | Role | Sees |
|------|----------|------|------|
| `admin` | `admin123` | admin | Everything — all tickets, users, teams, full dashboard, review queue |
| `client` | `user123` | client | Support chat + "My Tickets" (grouped by department) |
| `tsg` | `tsg123` | department (TSG) | Tech Support Group categories only |
| `base` | `base123` | department (BASE) | Facilities categories only |
| `hrgo` | `hrgo123` | department (HR-GO) | HR Global Operations categories only |
| `hrbp` | `hrbp123` | department (HR-BP) | HR Business Partner categories only |
| `finance` | `finance123` | department (Finance) | Billing only |

> **Try it:** log in as `client` and type *"I forgot my password and I'm locked
> out"* → watch it auto-resolve with steps. Then try *"my laptop won't turn on"*
> (HITL) and *"my payslip is wrong"* (human escalation). Log in as a department
> or `admin` account to review and resolve the queued ones.

---

## 🏢 Department routing

Each department owns a set of ticket categories. A `department`-role user is
hard-scoped to those categories everywhere — tickets, dashboard, and resolve
actions.

| Department | Code | Categories |
|-----------|------|-----------|
| Tech Support Group | `TSG` | VPN, Network, Email, Password_Reset, Printer, Software_Install, Application_Error, Performance, Mobile_Device, Hardware, Database, Cloud_Storage, Security, Data_Recovery, Access_Request |
| Facilities | `BASE` | Facilities, Access_Request, Onboarding, Offboarding |
| HR Global Operations | `HR-GO` | Payroll, Compliance, Onboarding, Offboarding |
| HR Business Partner | `HR-BP` | HR, Compliance, Onboarding, Offboarding |
| Finance | `Finance` | Billing |

Shared categories (e.g. **Onboarding**, **Compliance**) appear for every owning
department. The domain-guard catch-all **Other** belongs to no department and is
admin-only.

---

## 🧠 Train the DistilBERT model (optional, GPU recommended)

A trained model already ships under `./models/distilbert_finetuned`. To
retrain on your own data:

```powershell
.\.venv\Scripts\Activate.ps1
# NVIDIA GPU (e.g. RTX 3050): install the CUDA build of PyTorch first
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r backend\requirements-ml.txt

$env:PYTHONPATH = "C:\Users\sanjisuman\Desktop\TICKET_UPS\backend"
python scripts\initial_train.py `
  --train-csv data\ticket_train.csv `
  --val-csv   data\ticket_val.csv `
  --epochs 2 --batch-size 16 --max-length 128 `
  --output .\models\distilbert_finetuned
```

When it finishes, **restart the backend** — `/health` will show
`"model_loaded": true` and DistilBERT becomes the primary classifier, with
Ollama only firing on low confidence.

Check accuracy any time with `python scripts\accuracy_test.py`.

---

## 🔌 Key API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Self-registration (client) |
| POST | `/api/auth/login` | Login → JWT |
| GET | `/api/auth/me` | Current user |
| POST | `/api/chat/` | Main chat (intent → intake → classify → route/resolve) |
| POST | `/api/chat/extract` | OCR text from an uploaded screenshot |
| GET | `/api/tickets/mine` | The logged-in user's tickets |
| GET | `/api/tickets/` | Staff ticket list (department-scoped / admin-wide) |
| POST | `/api/tickets/{id}/resolve` | Admin or owning department marks resolved |
| POST | `/api/tickets/{id}/feedback` | End-user 👍/👎 → feeds retraining |
| GET | `/api/review/queue` | HITL queue (department-scoped) |
| POST | `/api/review/decide` | Agent approve/override |
| GET | `/api/metrics/dashboard` | Dashboard routing stats |
| GET | `/api/metrics/analytics` | Trends, priority mix, SLA, feedback ratio |
| GET | `/api/admin/users` · `/api/admin/teams` | Admin user/team overview |
| GET | `/api/metrics/prometheus` | Prometheus scrape |
| GET | `/health` | Health check (`model_loaded`) |

---

## ⚙️ Configuration (`.env`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Conversational / solution / translation model |
| `POSTGRES_URL` | `postgresql://postgres:postgres@localhost:5432/tickets_db` | DB (auto-upgraded to asyncpg). For zero-install local use: `sqlite+aiosqlite:///./data/app.db` |
| `MODEL_PATH` | `./models/distilbert_finetuned` | Trained classifier location |
| `DISTILBERT_FALLBACK_THRESHOLD` | `0.70` | Below this → Ollama second opinion |
| `CONFIDENCE_AUTONOMOUS` / `CONFIDENCE_HITL` | `0.95` / `0.80` | Routing thresholds |
| `TESSERACT_CMD` | *(blank)* | Path to `tesseract.exe` for screenshot OCR |
| `ENABLE_SCHEDULER` | `false` | Nightly auto-retrain |

> Paths in `config.py` are anchored to the project root, so the app finds the
> DB and model regardless of which directory you launch it from.

---

## 💰 Cost

| Component | Cost |
|-----------|------|
| DistilBERT inference | Free (your CPU) |
| Ollama LLM + embeddings | Free (your GPU) |
| PostgreSQL | Free (self-hosted) |
| **Total** | **$0 — fully local, no cloud, no API keys** |
