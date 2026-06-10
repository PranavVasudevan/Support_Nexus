"""
FastAPI application entry point.
Production-grade: connection pooling, graceful shutdown,
Redis-backed session state, semaphore-bounded concurrency.
"""
import asyncio
from contextlib import asynccontextmanager
from loguru import logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, tickets, review, admin, metrics, auth
from db.postgres import init_db
from db.mongo import init_mongo
from db.redis_session import init_redis, close_redis
from services.classifier import ClassifierService
from services.intent_detector import IntentDetector
from services.scheduler import start_scheduler
from core.config import settings
from core.llm import aclose as close_llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Ticket Classification System…")

    await init_db()
    await init_mongo()
    await init_redis()

    # Shared services — instantiated once, reused across all requests
    app.state.classifier = ClassifierService()
    await app.state.classifier.load()

    app.state.intent_detector = IntentDetector()

    # Semaphore: cap concurrent heavy ML inference calls
    app.state.classify_semaphore = asyncio.Semaphore(
        settings.max_classify_concurrency
    )

    if settings.enable_scheduler:
        start_scheduler(app.state.classifier)
    else:
        logger.info("Nightly retrain scheduler disabled (ENABLE_SCHEDULER=false)")

    # SLA watchdog — escalates tickets whose deadline passes. Runs regardless of
    # the retrain scheduler so SLAs are always enforced.
    async def _sla_watchdog():
        from db.postgres import escalate_overdue_tickets
        while True:
            try:
                escalated = await escalate_overdue_tickets()
                if escalated:
                    logger.warning(f"SLA watchdog escalated {len(escalated)} overdue "
                                   f"ticket(s): {', '.join(escalated)}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"SLA watchdog error: {e}")
            await asyncio.sleep(60)

    app.state.sla_task = asyncio.create_task(_sla_watchdog())

    logger.info("System ready.")
    yield

    # Graceful shutdown — close HTTP clients and DB pools
    logger.info("Shutting down…")
    app.state.sla_task.cancel()
    await app.state.classifier.close()
    await app.state.intent_detector.close()
    await close_llm()
    from core.embeddings import aclose as close_embeddings
    await close_embeddings()
    await close_redis()


app = FastAPI(
    title="Ticket Classification System",
    description="Autonomous + HITL ticket classifier — DistilBERT + local LLM (Ollama) fallback",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Locked to the local frontend dev origins. Add your deployed domain here.
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,    prefix="/api/auth",    tags=["Auth"])
app.include_router(chat.router,    prefix="/api/chat",    tags=["Chat"])
app.include_router(tickets.router, prefix="/api/tickets", tags=["Tickets"])
app.include_router(review.router,  prefix="/api/review",  tags=["HITL Review"])
app.include_router(admin.router,   prefix="/api/admin",   tags=["Admin"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "model_loaded": app.state.classifier._model_loaded,
    }
