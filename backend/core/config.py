from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Optional

# Project root + .env resolved absolutely so they load no matter which
# directory the server is started from (backend/, repo root, etc.). In Docker
# this file won't exist, but env vars are injected by docker-compose instead.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # ── Databases ──────────────────────────────────────────────────────────────
    # Default = SQLite (no-Docker local mode). Docker-compose overrides this with
    # a real Postgres URL via environment variables.
    #   • sqlite+aiosqlite:///./data/app.db   → local file, zero install
    #   • postgresql://user:pass@host/db       → auto-upgraded to asyncpg driver
    postgres_url: str = "sqlite+aiosqlite:///./data/app.db"

    # Leave blank to disable. Mongo only stores optional chat-event logs.
    mongo_url: str = ""

    # Leave blank to use the in-process in-memory session store (local mode).
    # Docker-compose sets redis://redis:6379 for multi-replica safety.
    redis_url: str = ""

    # ── LLM — local Ollama (replaces Gemini, fully offline) ───────────────────
    # Runs against a local Ollama server — no API key, no rate limits, no cloud.
    #   Install:  https://ollama.com/download
    #   Pull:     ollama pull qwen2.5:7b
    # Used for intent detection (ambiguous messages) and classification fallback.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    # Master switch — set false to force the rule-based / keyword-only path
    # (e.g. if the Ollama server isn't running and you want to skip the retries).
    ollama_enabled: bool = True
    # Embedding model for duplicate/similar-ticket detection (small + fast).
    embed_model: str = "nomic-embed-text"
    # Cosine-similarity threshold above which two tickets are "similar".
    similar_threshold: float = 0.70
    # Path to the Tesseract OCR binary (screenshot → text). Blank = auto-detect.
    tesseract_cmd: str = ""

    # ── Model ──────────────────────────────────────────────────────────────────
    # Local default lives under the repo. Docker sets /app/distilbert_models/...
    model_path: str = "./models/distilbert_finetuned"
    base_model: str = "distilbert-base-uncased"
    # DistilBERT below this confidence → defer to the local LLM (the documented
    # "confidence < 0.70 → LLM fallback" behaviour, now actually wired up).
    distilbert_fallback_threshold: float = 0.70

    # ── Confidence thresholds (routing) ────────────────────────────────────────
    # ≥ autonomous + autonomous-category → auto-resolve
    # ≥ hitl                              → HITL queue (AI suggestion attached)
    # <  hitl                             → full human escalation
    confidence_autonomous: float = 0.95
    confidence_hitl: float = 0.80

    # ── SLA (hours until deadline, by priority) ─────────────────────────────────
    sla_hours_critical: float = 1.0
    sla_hours_high: float = 4.0
    sla_hours_medium: float = 24.0
    sla_hours_low: float = 72.0

    @property
    def sla_hours_by_priority(self):
        return {
            "critical": self.sla_hours_critical,
            "high": self.sla_hours_high,
            "medium": self.sla_hours_medium,
            "low": self.sla_hours_low,
        }

    # ── Retraining ─────────────────────────────────────────────────────────────
    retrain_min_samples: int = 100
    retrain_schedule_hour: int = 2        # 2 AM local nightly
    # Nightly retrain is opt-in; off by default so local runs don't fire training.
    enable_scheduler: bool = False

    # ── MLflow ─────────────────────────────────────────────────────────────────
    # Blank → MLflow tracking is skipped (training still works locally).
    mlflow_uri: str = ""

    # ── Auth (JWT) ──────────────────────────────────────────────────────────────
    # Secret used to sign JWTs. OVERRIDE in production via env (JWT_SECRET=...).
    jwt_secret: str = "dev-secret-change-me-in-production-please-0192837465"
    jwt_expire_hours: int = 12
    # Seeded accounts (created on first startup if absent). Self-registration
    # creates additional client-role users; admin is provisioned here only.
    seed_admin_password: str = "admin123"
    seed_client_password: str = "user123"

    # ── App ────────────────────────────────────────────────────────────────────
    environment: str = "development"

    # ── Scalability ────────────────────────────────────────────────────────────
    # Max concurrent classification requests (tune for your CPU/GPU)
    max_classify_concurrency: int = 50
    # Redis key TTL for session state (seconds) — also used by the in-memory store
    session_ttl_seconds: int = 3600       # 1 hour

    class Config:
        env_file = str(_ENV_FILE)
        extra = "ignore"
        protected_namespaces = ()

    # ── Validators ────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _anchor_sqlite_path(self):
        """
        Anchor a RELATIVE sqlite path to the project root so there is always ONE
        database file regardless of the directory the server is launched from.
        (Previously './data/app.db' resolved against the CWD, silently creating
        stray, out-of-sync databases under backend/, frontend/, etc.)
        """
        prefix = "sqlite+aiosqlite:///"
        url = self.postgres_url
        if url.startswith(prefix):
            raw = url[len(prefix):]
            p = Path(raw)
            if not p.is_absolute():
                abs_path = (_PROJECT_ROOT / raw.lstrip("./").lstrip("/")).resolve()
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                self.postgres_url = f"{prefix}{abs_path.as_posix()}"

        # Anchor the DistilBERT model path to the project root too, so the model
        # always loads regardless of the launch directory (it's relative by
        # default and would otherwise silently fall back to LLM-only).
        mp = Path(self.model_path)
        if not mp.is_absolute():
            anchored = (_PROJECT_ROOT / self.model_path.lstrip("./").lstrip("/")).resolve()
            if anchored.exists():
                self.model_path = str(anchored)
        return self

    # ── Derived flags ───────────────────────────────────────────────────────────
    @property
    def is_sqlite(self) -> bool:
        return self.postgres_url.startswith("sqlite")

    @property
    def use_redis(self) -> bool:
        return bool(self.redis_url.strip())

    @property
    def use_mongo(self) -> bool:
        return bool(self.mongo_url.strip())

    @property
    def categories(self):
        return [
            "VPN", "Password_Reset", "Hardware", "Software_Install",
            "Payroll", "Network", "Security", "Email", "Printer",
            "Access_Request", "Data_Recovery", "Performance", "Onboarding",
            "Offboarding", "Compliance", "Cloud_Storage", "Mobile_Device",
            "Database", "Application_Error", "Billing"
        ]

    @property
    def num_labels(self):
        return len(self.categories)

    @property
    def label2id(self):
        return {cat: i for i, cat in enumerate(self.categories)}

    @property
    def id2label(self):
        return {i: cat for i, cat in enumerate(self.categories)}


settings = Settings()
