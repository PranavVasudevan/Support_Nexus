from fastapi import APIRouter, BackgroundTasks, Request, Depends
from services.trainer import retrain_model
from db.postgres import get_feedback_count, list_users_with_counts, list_teams_with_counts
from core.auth import require_admin

router = APIRouter()


@router.get("/users")
async def list_users(_admin: dict = Depends(require_admin)):
    """Admin-only: all users with ticket counts — powers Users → Tickets view."""
    return await list_users_with_counts()


@router.get("/teams")
async def list_teams(_admin: dict = Depends(require_admin)):
    """Admin-only: departments/teams with ticket counts — powers Teams → Tickets view."""
    return await list_teams_with_counts()


@router.post("/retrain")
async def trigger_retrain(request: Request, background_tasks: BackgroundTasks,
                          _admin: dict = Depends(require_admin)):
    """Manually trigger DistilBERT retraining."""
    count = await get_feedback_count()
    classifier = request.app.state.classifier
    if count < 50:
        return {
            "status": "skipped",
            "reason": f"Only {count} feedback samples. Need at least 50.",
        }
    background_tasks.add_task(retrain_model, classifier)
    return {"status": "started", "feedback_samples": count}


@router.get("/audit")
async def audit_log(limit: int = 100, ticket_id: str = None,
                    _admin: dict = Depends(require_admin)):
    """Immutable action history for compliance / audit readiness."""
    from db.postgres import list_audit
    return await list_audit(limit=limit, ticket_id=ticket_id)


@router.get("/model-status")
async def model_status(request: Request, _admin: dict = Depends(require_admin)):
    classifier = request.app.state.classifier
    return {
        "distilbert_loaded": classifier._model_loaded,
        "device": classifier.device,
        "model_path": classifier.model_path if hasattr(classifier, "model_path") else "N/A",
        "feedback_samples": await get_feedback_count(),
    }
