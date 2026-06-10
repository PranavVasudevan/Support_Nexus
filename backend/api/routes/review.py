"""
HITL Review Routes
Agents use this to see the review queue, approve/override AI predictions,
and store feedback which feeds the retraining pipeline.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models.schemas import ReviewQueue, ReviewDecision, FeedbackLog
from db.postgres import (
    get_review_queue,
    get_review_item,
    submit_review_decision,
    save_feedback_log,
)
from core.auth import require_staff
from core.teams import categories_for

router = APIRouter()


def _dept_categories(user: dict):
    """Category scope for a department agent (None = admin, sees everything)."""
    if user.get("role") == "department":
        return categories_for(user.get("department"))
    return None


@router.get("/queue", response_model=List[ReviewQueue])
async def get_queue(
    status: str = "pending",
    category: str = None,
    priority: str = None,
    limit: int = 100,
    user: dict = Depends(require_staff),
):
    """Get HITL items for review — scoped to the agent's department categories."""
    if category == "all":
        category = None
    if priority == "all":
        priority = None
    return await get_review_queue(
        status=status, category=category, priority=priority, limit=limit,
        categories=_dept_categories(user),
    )


@router.get("/queue/{queue_id}", response_model=ReviewQueue)
async def get_queue_item(queue_id: str, user: dict = Depends(require_staff)):
    item = await get_review_item(queue_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    cats = _dept_categories(user)
    if cats is not None and item.ai_prediction.category not in cats:
        raise HTTPException(status_code=403, detail="Not in your department")
    return item


@router.post("/decide", response_model=FeedbackLog)
async def submit_decision(decision: ReviewDecision, user: dict = Depends(require_staff)):
    """
    Agent submits their decision on a queued ticket.
    This is stored as training data for retraining.
    """
    item = await get_review_item(decision.queue_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    cats = _dept_categories(user)
    if cats is not None and item.ai_prediction.category not in cats:
        raise HTTPException(status_code=403, detail="Not in your department")

    ai_pred = item.ai_prediction
    was_corrected = (
        not decision.approved
        and (
            decision.override_category != ai_pred.category
            or decision.override_resolution != ai_pred.resolution_type
        )
    )

    final_category = (
        decision.override_category if decision.override_category
        else ai_pred.category
    )
    final_resolution = (
        str(decision.override_resolution.value) if decision.override_resolution
        else str(ai_pred.resolution_type.value)
    )

    feedback = FeedbackLog(
        ticket_id=item.ticket_id,
        predicted_category=ai_pred.category,
        predicted_resolution=str(ai_pred.resolution_type.value),
        predicted_confidence=ai_pred.confidence,
        final_category=final_category,
        final_resolution=final_resolution,
        was_corrected=was_corrected,
        agent_id=decision.agent_id,
        notes=decision.notes,
    )

    await submit_review_decision(decision, item)
    await save_feedback_log(feedback)

    return feedback


@router.get("/stats")
async def review_stats(user: dict = Depends(require_staff)):
    """HITL queue statistics for dashboard."""
    from db.postgres import get_hitl_stats
    return await get_hitl_stats(categories=_dept_categories(user))
