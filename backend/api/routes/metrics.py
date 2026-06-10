from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST,
)
from db.postgres import get_routing_stats
from core.auth import require_staff
from core.teams import categories_for

router = APIRouter()


def _scope(user: dict):
    """Category scope for a department agent (None = admin/everything)."""
    if user.get("role") == "department":
        return categories_for(user.get("department"))
    return None

# Prometheus metrics
tickets_total = Counter("tickets_total", "Total tickets processed", ["routing", "category"])
classification_confidence = Histogram(
    "classification_confidence",
    "Confidence score distribution",
    buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.90, 0.95, 0.99, 1.0],
)
hitl_queue_size = Gauge("hitl_queue_size", "Current HITL queue depth")
correction_rate = Gauge("correction_rate", "Human override rate (last 100)")


def record_decision(routing: str, category: str, confidence: float):
    """Called by the decision engine for every processed ticket."""
    try:
        tickets_total.labels(routing=routing, category=category).inc()
        classification_confidence.observe(confidence)
    except Exception:
        # Metrics must never break the request path.
        pass


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus scrape endpoint."""
    # Refresh gauges from the DB so a scrape reflects live queue/correction state.
    try:
        from db.postgres import get_hitl_stats
        stats = await get_hitl_stats()
        hitl_queue_size.set(stats.get("pending", 0))
        correction_rate.set(stats.get("correction_rate", 0))
    except Exception:
        pass
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/dashboard")
async def dashboard_stats(user: dict = Depends(require_staff)):
    """Stats for the frontend dashboard (scoped to dept for department agents)."""
    return await get_routing_stats(categories_filter=_scope(user))


@router.get("/analytics")
async def analytics(user: dict = Depends(require_staff)):
    """Trends, priority mix, SLA compliance, feedback ratio (dept-scoped)."""
    from db.postgres import get_analytics
    return await get_analytics(categories_filter=_scope(user))


@router.get("/model-performance")
async def model_performance(user: dict = Depends(require_staff)):
    """Model F1/accuracy history (global — the model is shared)."""
    from db.postgres import get_model_perf
    return await get_model_perf()
