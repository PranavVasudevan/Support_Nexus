"""
Chat Route — conversational ticket intake.
═══════════════════════════════════════════
Flow (an explicit, multi-turn state machine):

  1. Every fresh message is classified by the IntentDetector into:
       greeting → reply conversationally, no ticket
       vague    → a bare topic ("VPN") → start the clarify loop
       ticket   → a real problem → start the clarify loop (unless already detailed)
  2. CLARIFY LOOP (stage="gathering"): we ask tailored questions (rendered as a
     box in the UI) and keep asking until analyze_problem() decides we understand
     the issue — or we hit MAX_CLARIFY_ATTEMPTS. This prevents bare keywords or
     half-answers from becoming tickets, and lets us derive a real priority.
  3. Once understood → create ticket, classify (Ollama), route:
       autonomous → AI-generated step-by-step solution
       hitl       → review queue
       human      → escalation (sensitive categories)

State lives in the session store (Redis or in-memory) so it survives the
multi-turn exchange and horizontally-scaled replicas.
"""
from fastapi import APIRouter, Request, HTTPException
from loguru import logger

from models.schemas import (
    ChatRequest, ChatResponse, TicketCreate, Priority, IntentType
)
from db.postgres import create_ticket, get_session_history, save_message
from db.mongo import log_chat_event
from db.redis_session import (
    get_session_state, set_session_state, delete_session_state
)
from services.decision_engine import DecisionEngine
from services.intent_detector import _is_dissatisfaction
from core.i18n import translate
from core.auth import get_optional_user
from fastapi import Depends, UploadFile, File
from typing import Optional

router = APIRouter()
_decision_engine = DecisionEngine()

_QUESTIONS_TITLE = "A few details to help me solve this"

_VALID_PRIORITIES = ("low", "medium", "high", "critical")
_PRIO_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
# How many rounds of clarifying questions before we proceed with what we have.
MAX_CLARIFY_ATTEMPTS = 3


def _short_title(text: str) -> str:
    words = text.strip().split()
    title = " ".join(words[:8])
    if len(words) > 8:
        title += "…"
    return title or "Support request"


def _clean_priority(value) -> str:
    return value if value in _VALID_PRIORITIES else "medium"


def _bump_priority(value: str) -> str:
    """A frustrated user → ensure at least 'high' priority."""
    p = _clean_priority(value)
    return p if _PRIO_RANK[p] >= 2 else "high"


def _cap_medium(value: str) -> str:
    """Cap priority at 'medium' (for non-IT / single-device-repair tickets)."""
    p = _clean_priority(value)
    return p if _PRIO_RANK[p] <= _PRIO_RANK["medium"] else "medium"


@router.post("/extract")
async def extract_from_image(file: UploadFile = File(...),
                             user: Optional[dict] = Depends(get_optional_user)):
    """OCR a screenshot → text. The client puts this in the chat box to send."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 8 MB)")
    try:
        from core.ocr import extract_text
        import anyio
        text = await anyio.to_thread.run_sync(extract_text, data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the image: {e}")
    if not text:
        return {"text": "", "note": "No readable text found in the image."}
    return {"text": text}


@router.post("/", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest,
               user: Optional[dict] = Depends(get_optional_user)):
    classifier = request.app.state.classifier
    intent_detector = request.app.state.intent_detector
    semaphore = request.app.state.classify_semaphore
    user_id = user["id"] if user else None

    session_id = body.session_id
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    history = await get_session_history(session_id)
    state = await get_session_state(session_id)
    await save_message(session_id, "user", message)

    # ── Follow-up after a resolved ticket: "it didn't work" → reopen/escalate ─
    if state.get("stage") == "resolved":
        if _is_dissatisfaction(message):
            return await _reopen_ticket(session_id, message, state)
        # A new, unrelated message → clear the resolved marker and continue fresh.
        await delete_session_state(session_id)
        state = {}

    # ── CLARIFY LOOP: user is answering our questions ─────────────────────────
    if state.get("stage") == "gathering":
        return await _continue_gathering(
            session_id, message, state, classifier, intent_detector, semaphore, user_id
        )

    # ── Fresh message → detect intent ─────────────────────────────────────────
    intent = await intent_detector.detect(message, history)
    await log_chat_event(session_id, "intent_detected", {
        "intent": intent.intent.value,
        "is_ticket": intent.is_ticket,
        "confidence": intent.confidence,
    })

    # Greeting / small talk → just reply.
    if intent.intent == IntentType.greeting:
        reply = intent.reply or "Hi! How can I help with your IT issue today?"
        await save_message(session_id, "assistant", reply)
        return ChatResponse(session_id=session_id, reply=reply,
                            is_ticket=False, stage="greeting")

    # Vague topic OR ticket → ALWAYS open the clarify loop with a tailored
    # question box first (we never skip straight to a ticket, even when the first
    # message looks detailed — the questions confirm and fill any gaps).
    extracted = intent.extracted or {}
    context = extracted.get("topic") or extracted.get("title") or message
    title = extracted.get("title") or _short_title(message)

    qa = await intent_detector.intake_questions(context, message)
    frustrated = bool(qa.get("frustrated", False))
    language = qa.get("language") or "English"
    await set_session_state(session_id, {
        "stage": "gathering",
        "context": context,
        "title": qa.get("title") or title,
        "collected": message,
        "attempts": 1,
        "frustrated": frustrated,
        "language": language,
    })
    if intent.intent == IntentType.vague:
        intro = intent.reply or "Happy to help — could you tell me a bit more?"
    else:
        intro = ("Thanks for flagging this — to solve it properly, could you answer "
                 "a few quick questions?")
    if frustrated:
        intro = "I understand this is frustrating, and I'll help you get it sorted. " + intro
    intro = await translate(intro, language)
    await save_message(session_id, "assistant", intro)
    return ChatResponse(
        session_id=session_id, reply=intro,
        is_ticket=(intent.intent == IntentType.ticket),
        questions=qa["questions"],
        questions_title=await translate(_QUESTIONS_TITLE, language),
        awaiting_details=True, stage="clarify",
    )


async def _continue_gathering(session_id, message, state, classifier,
                              intent_detector, semaphore, user_id=None) -> ChatResponse:
    """Process the user's answer in the clarify loop."""
    context = state.get("context", "")
    title = state.get("title") or _short_title(message)
    collected = f"{state.get('collected', '')}\n{message}".strip()
    attempts = int(state.get("attempts", 1)) + 1

    analysis = await intent_detector.analyze_problem(context, collected)
    # Frustration & language are sticky across the conversation.
    frustrated = bool(state.get("frustrated")) or bool(analysis.get("frustrated"))
    language = state.get("language") or analysis.get("language") or "English"
    it_issue = analysis.get("it_issue", True)
    needs_human = bool(analysis.get("needs_human"))
    multi_user = bool(analysis.get("multi_user"))

    # Understood, or we've asked enough times → create + classify the ticket.
    if analysis["understood"] or attempts > MAX_CLARIFY_ATTEMPTS:
        base = _clean_priority(analysis["priority"])
        if not it_issue:
            # Non-IT (HR/Facilities/Other): goes to a human anyway; keep modest.
            priority = _cap_medium(base)
        elif needs_human and not multi_user:
            # A single broken/damaged personal device → medium at most (it needs
            # repair, but isn't a work-stopping outage).
            priority = _cap_medium(base)
        elif frustrated:
            priority = _bump_priority(base)
        else:
            priority = base
        await delete_session_state(session_id)
        return await _finalize_ticket(
            session_id, analysis.get("title") or title, collected,
            priority, None, classifier, semaphore, language, user_id,
            it_issue=it_issue, category_hint=analysis.get("category_hint"),
            needs_human=needs_human,
        )

    # Still too vague → ask the next round of questions.
    await set_session_state(session_id, {
        "stage": "gathering",
        "context": context,
        "title": analysis.get("title") or title,
        "collected": collected,
        "attempts": attempts,
        "frustrated": frustrated,
        "language": language,
    })
    reply = await translate("Thanks — just a little more so I can get this exactly right:", language)
    await save_message(session_id, "assistant", reply)
    return ChatResponse(
        session_id=session_id, reply=reply, is_ticket=True,
        questions=analysis["questions"],
        questions_title=await translate(_QUESTIONS_TITLE, language),
        awaiting_details=True, stage="clarify",
    )


async def _finalize_ticket(session_id, title, description, priority, department,
                           classifier, semaphore, language="English",
                           user_id=None, it_issue=True, category_hint=None,
                           needs_human=False) -> ChatResponse:
    """Create the ticket, classify it, route it, and build the chat reply."""
    # Embed the problem and find recent similar/duplicate tickets BEFORE creating
    # this one (so we don't match against itself).
    from core.embeddings import embed
    from db.postgres import find_similar_tickets
    from core.config import settings as _settings
    from models.schemas import ClassificationResult, ResolutionType
    emb = await embed(f"{title}. {description}")
    similar = await find_similar_tickets(emb, threshold=_settings.similar_threshold) if emb else []

    ticket = await create_ticket(TicketCreate(
        title=title,
        description=description,
        priority=Priority(_clean_priority(priority)),
        department=department,
        source="chat",
    ), session_id=session_id, user_id=user_id, embedding=emb)

    if not it_issue:
        # Out-of-domain guard: not an IT issue → label HR/Facilities/Other and
        # send straight to a human (never let DistilBERT force it into an IT
        # category like "Offboarding").
        cat = category_hint if category_hint in ("HR", "Facilities", "Other") else "Other"
        classification = ClassificationResult(
            category=cat, resolution_type=ResolutionType.human, confidence=0.95,
            all_scores={cat: 0.95}, model_used="domain_guard",
        )
    else:
        # Semaphore ensures we don't overload CPU/GPU with simultaneous inference.
        async with semaphore:
            classification = await classifier.classify(title, description)
        # Physical damage / dead device can't be fixed by software steps → don't
        # auto-resolve; route to a human agent (HITL) instead.
        if needs_human and classification.resolution_type == ResolutionType.autonomous:
            classification.resolution_type = ResolutionType.hitl
            classification.model_used = f"{classification.model_used}+needs_human"

    decision = await _decision_engine.process(ticket, classification, language)
    reply = await _build_reply(ticket, classification, decision, language)
    # If several similar tickets were reported recently, hint at a possible
    # widespread issue (helps spot outages early).
    if len(similar) >= 2:
        note = await translate(
            f"\n\n🔁 Heads-up: {len(similar)} similar issues were reported recently — "
            "this may be a widespread problem we're already aware of.", language)
        reply += note
    await save_message(session_id, "assistant", reply)
    # Remember the resolved ticket (+ language) so a follow-up can reopen it.
    await set_session_state(session_id, {
        "stage": "resolved",
        "last_ticket_id": ticket.ticket_id,
        "last_category": classification.category,
        "last_routing": decision.routing.value if decision else None,
        "language": language,
    })
    return ChatResponse(
        session_id=session_id, reply=reply, is_ticket=True,
        ticket_id=ticket.ticket_id, classification=classification,
        routing=decision.routing.value if decision else None,
        resolution=decision.resolution if decision else None,
        stage="resolved", similar_tickets=similar,
    )


async def _reopen_ticket(session_id, message, state) -> ChatResponse:
    """The previous solution didn't work → escalate the ticket to a human."""
    last_id = state.get("last_ticket_id")
    language = state.get("language") or "English"
    await delete_session_state(session_id)
    # Best-effort: mark the ticket escalated (no-op if the helper isn't present).
    try:
        from db.postgres import update_ticket_status
        await update_ticket_status(last_id, "escalated")
    except Exception:
        pass
    reply = await translate(
        "I'm sorry that didn't resolve it. I've escalated ticket [[ID]] to a human "
        "specialist who will reach out shortly.\n\n"
        "If you can, tell me what happened when you tried the steps (any error, what "
        "changed) and I'll add it to the ticket for them.",
        language, tokens=("[[ID]]",),
    )
    reply = reply.replace("[[ID]]", str(last_id))
    await save_message(session_id, "assistant", reply)
    return ChatResponse(
        session_id=session_id, reply=reply, is_ticket=True,
        ticket_id=last_id, routing="human", stage="reopened",
    )


async def _build_reply(ticket, classification, decision, language="English") -> str:
    """Compose the user-facing chat reply, localized into the user's language."""
    conf = f"{classification.confidence * 100:.0f}%"
    category = classification.category.replace("_", " ")
    pri = await translate(ticket.priority.value, language)

    # Header — translate the template (placeholders preserved), then fill values.
    header_tmpl = await translate(
        "Ticket [[ID]] created\nCategory: [[CAT]]  ·  Priority: [[PRI]]  ·  Confidence: [[CONF]]",
        language, tokens=("[[ID]]", "[[CAT]]", "[[PRI]]", "[[CONF]]"),
    )
    header = (header_tmpl.replace("[[ID]]", ticket.ticket_id)
              .replace("[[CAT]]", category).replace("[[PRI]]", pri)
              .replace("[[CONF]]", conf))

    res = decision.resolution
    if decision.routing.value == "autonomous" and res and res.automated:
        # res.summary / steps / follow_up are already in the user's language.
        lines = [f"{i+1}. {s.action}" + (f" — {s.detail}" if s.detail else "")
                 for i, s in enumerate(res.steps)]
        status_line = await translate(
            "✅ Here's how to resolve it:" if res.status == "resolved"
            else "⚙️ Automated fix in progress — here's what's happening:", language)
        body = f"\n\n{status_line}\n\n{res.summary}\n\n" + "\n".join(lines)
        if res.eta:
            body += "\n\n" + await translate("Estimated time:", language) + f" {res.eta}"
        if res.follow_up:
            body += "\n\n" + await translate("Next:", language) + f" {res.follow_up}"
        return header + body

    if decision.routing.value == "hitl":
        return header + "\n\n" + await translate(
            "📋 Your ticket is queued for review. An agent will follow up shortly. "
            "See the self-help steps below while you wait.", language)

    # human / escalation (sensitive categories and low confidence)
    return header + "\n\n" + await translate(
        "🔔 Your ticket has been escalated to a specialist who will reach out. "
        "See the self-help steps below in the meantime.", language)
