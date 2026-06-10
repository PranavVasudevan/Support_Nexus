from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class ResolutionType(str, Enum):
    autonomous = "autonomous"
    hitl = "hitl"
    human = "human"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class IntentType(str, Enum):
    """What the user's message actually is."""
    greeting = "greeting"   # small talk / greeting / thanks / bye → just reply
    vague = "vague"         # a bare topic/keyword (e.g. "VPN") → ask them to explain
    ticket = "ticket"       # a real, described problem → gather details + classify


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: List[ChatMessage] = []


class IntentResult(BaseModel):
    is_ticket: bool
    intent: IntentType = IntentType.ticket
    confidence: float
    needs_detail: bool = False   # ticket recognised but description too thin → ask for more
    missing_fields: List[str] = []
    extracted: dict = {}
    reply: Optional[str] = None  # conversational reply for greeting / vague


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    is_ticket: bool
    ticket_id: Optional[str] = None
    classification: Optional["ClassificationResult"] = None
    routing: Optional[str] = None                       # autonomous | hitl | human
    resolution: Optional["AutonomousResolution"] = None  # populated on the autonomous path
    # Conversational intake: clarifying questions to render as a box, and a flag
    # that we're still gathering details (no ticket created yet this turn).
    questions: List[str] = []
    questions_title: Optional[str] = None                # localized header for the question box
    awaiting_details: bool = False
    stage: Optional[str] = None                          # greeting | clarify | resolved
    similar_tickets: list = []                           # recent similar/duplicate tickets


# ── Ticket ─────────────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    title: str
    description: str
    priority: Priority = Priority.medium
    department: Optional[str] = None
    user_role: Optional[str] = None
    source: str = "chat"  # chat | email | portal


class TicketInDB(TicketCreate):
    ticket_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "open"           # open | in_review | resolved | escalated
    session_id: Optional[str] = None
    user_id: Optional[str] = None  # owner (logged-in user)
    # Enriched fields surfaced in the ticket-tracking portal / dashboards
    category: Optional[str] = None
    resolution_type: Optional[str] = None
    model_used: Optional[str] = None
    confidence: Optional[float] = None
    sla_deadline: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


# ── Classification ─────────────────────────────────────────────────────────────

class ClassificationResult(BaseModel):
    category: str
    resolution_type: ResolutionType
    confidence: float
    all_scores: dict = {}
    model_used: str = "distilbert"  # distilbert | ollama_fallback | keyword_fallback


# ── Autonomous resolution ────────────────────────────────────────────────────────

class ResolutionStep(BaseModel):
    """A single automated action the resolver executed."""
    step: int
    action: str                       # what was attempted
    status: str = "done"              # done | skipped | failed
    detail: Optional[str] = None      # extra context / result


class AutonomousResolution(BaseModel):
    """
    The full record of how a ticket was solved automatically — surfaced to the
    user (chat) and stored on the decision for audit.
    """
    automated: bool                   # True if no human needed
    category: str
    status: str = "resolved"          # resolved | in_progress | failed
    summary: str                      # one-line outcome
    steps: List[ResolutionStep] = []  # the workflow that ran
    reference_id: str                 # work-order / automation run id
    system: Optional[str] = None      # backend system the workflow targets
    eta: Optional[str] = None         # when completion is expected (if not instant)
    follow_up: Optional[str] = None   # what the user should do / expect next


class DecisionResult(BaseModel):
    ticket_id: str
    classification: ClassificationResult
    routing: ResolutionType
    action_taken: Optional[str] = None
    requires_review: bool = False
    resolution: Optional[AutonomousResolution] = None


# ── HITL Review ────────────────────────────────────────────────────────────────

class ReviewQueue(BaseModel):
    queue_id: str
    ticket_id: str
    ticket: TicketInDB
    ai_prediction: ClassificationResult
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending | approved | overridden
    priority: str = "normal"
    sla_deadline: Optional[datetime] = None


class ReviewDecision(BaseModel):
    queue_id: str
    agent_id: str
    approved: bool
    override_category: Optional[str] = None
    override_resolution: Optional[ResolutionType] = None
    notes: Optional[str] = None


class FeedbackLog(BaseModel):
    ticket_id: str
    predicted_category: str
    predicted_resolution: str
    predicted_confidence: float
    final_category: str
    final_resolution: str
    was_corrected: bool
    agent_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
