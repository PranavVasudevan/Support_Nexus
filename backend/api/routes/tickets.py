from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from models.schemas import TicketCreate, TicketInDB, FeedbackLog
from db.postgres import (
    create_ticket, get_ticket, list_tickets, save_feedback_log,
    update_ticket_status,
)
from core.auth import get_current_user, require_admin, require_staff
from core.teams import categories_for

router = APIRouter()


class FeedbackIn(BaseModel):
    helpful: bool
    notes: Optional[str] = None


# ── Specific paths first (so they don't match /{ticket_id}) ──────────────────────

@router.get("/mine", response_model=List[TicketInDB])
async def my_tickets(user: dict = Depends(get_current_user),
                     limit: int = Query(100, le=500)):
    """Tickets owned by the logged-in user (persists across sessions)."""
    return await list_tickets(user_id=user["id"], limit=limit)


@router.get("/", response_model=List[TicketInDB])
async def list_all_tickets(
    user: dict = Depends(require_staff),
    status: Optional[str] = None,
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = Query(200, le=500),
    offset: int = 0,
):
    """Staff tickets. Admin sees everything (optionally filtered by user/department);
    a department agent is hard-scoped to their own categories."""
    if user["role"] == "department":
        category_in = categories_for(user.get("department"))
        user_id = None          # department agents can't browse by arbitrary user
    else:
        category_in = categories_for(department) if department else None
    return await list_tickets(status=status, category=category, user_id=user_id,
                              category_in=category_in, limit=limit, offset=offset)


@router.post("/", response_model=TicketInDB)
async def submit_ticket(ticket: TicketCreate, user: dict = Depends(get_current_user)):
    """Submit a ticket directly (non-chat portal)."""
    return await create_ticket(ticket, user_id=user["id"])


@router.get("/{ticket_id}", response_model=TicketInDB)
async def get_ticket_by_id(ticket_id: str, user: dict = Depends(get_current_user)):
    ticket = await get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    # Owner or admin only.
    if user["role"] != "admin" and ticket.user_id and ticket.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not your ticket")
    return ticket


@router.post("/{ticket_id}/feedback")
async def submit_feedback(ticket_id: str, body: FeedbackIn,
                          user: dict = Depends(get_current_user)):
    """End-user 👍/👎 on a resolution. Stored in feedback_logs → feeds retraining."""
    ticket = await get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    cat = ticket.category or "unknown"
    res = ticket.resolution_type or "unknown"
    note = (body.notes or "").strip()
    await save_feedback_log(FeedbackLog(
        ticket_id=ticket_id,
        predicted_category=cat,
        predicted_resolution=res,
        predicted_confidence=ticket.confidence or 0.0,
        final_category=cat,
        final_resolution=res,
        was_corrected=not body.helpful,
        agent_id=user["username"],
        notes=f"helpful={body.helpful}" + (f" | {note}" if note else ""),
    ))
    return {"status": "recorded", "ticket_id": ticket_id, "helpful": body.helpful}


@router.post("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, user: dict = Depends(require_staff)):
    """Admin or the owning department marks a ticket resolved."""
    if user["role"] == "department":
        t = await get_ticket(ticket_id)
        if not t:
            raise HTTPException(status_code=404, detail="Ticket not found")
        if t.category not in categories_for(user.get("department")):
            raise HTTPException(status_code=403, detail="Not in your department")
    ok = await update_ticket_status(ticket_id, "resolved", resolved=True)
    if not ok:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"status": "resolved", "ticket_id": ticket_id}
