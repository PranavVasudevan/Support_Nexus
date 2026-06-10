"""
PostgreSQL database layer using SQLAlchemy async.
"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, Text, JSON, Integer, select, func
)
from loguru import logger

from core.config import settings
from models.schemas import (
    TicketCreate, TicketInDB, ClassificationResult,
    ReviewQueue, ReviewDecision, FeedbackLog,
)

Base = declarative_base()

# ── ORM Models ─────────────────────────────────────────────────────────────────

class TicketORM(Base):
    __tablename__ = "tickets"
    id          = Column(String, primary_key=True)
    title       = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    category    = Column(String)
    priority    = Column(String, default="medium")
    department  = Column(String)
    user_role   = Column(String)
    resolution_type = Column(String)
    confidence  = Column(Float)
    status      = Column(String, default="open")
    source      = Column(String, default="chat")
    session_id  = Column(String)
    created_at  = Column(DateTime, default=datetime.utcnow)
    model_used  = Column(String)
    sla_deadline = Column(DateTime)     # SLA: when this ticket must be resolved by
    resolved_at  = Column(DateTime)     # set when status → resolved/escalated
    user_id     = Column(String, index=True)   # owner (logged-in user); null = anonymous
    embedding   = Column(Text)          # JSON-encoded vector for similarity search


class UserORM(Base):
    __tablename__ = "users"
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username      = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role          = Column(String, default="client")   # client | admin | department
    department    = Column(String)                      # dept code for role=department
    created_at    = Column(DateTime, default=datetime.utcnow)


class ReviewQueueORM(Base):
    __tablename__ = "review_queue"
    id           = Column(String, primary_key=True)
    ticket_id    = Column(String, nullable=False)
    ticket_data  = Column(JSON)
    ai_prediction = Column(JSON)
    status       = Column(String, default="pending")
    priority     = Column(String, default="normal")
    created_at   = Column(DateTime, default=datetime.utcnow)
    resolved_at  = Column(DateTime)


class FeedbackORM(Base):
    __tablename__ = "feedback_logs"
    id                   = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id            = Column(String)
    predicted_category   = Column(String)
    predicted_resolution = Column(String)
    predicted_confidence = Column(Float)
    final_category       = Column(String)
    final_resolution     = Column(String)
    was_corrected        = Column(Boolean, default=False)
    agent_id             = Column(String)
    notes                = Column(Text)
    created_at           = Column(DateTime, default=datetime.utcnow)


class ModelMetricORM(Base):
    """One row per retraining run — powers the Model Performance dashboard."""
    __tablename__ = "model_metrics"
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_date        = Column(DateTime, default=datetime.utcnow)
    f1              = Column(Float)
    accuracy        = Column(Float)
    correction_rate = Column(Float)
    total_samples   = Column(Integer)


class AuditLogORM(Base):
    """Immutable action history for compliance / audit readiness."""
    __tablename__ = "audit_log"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor       = Column(String)        # who/what performed the action
    action      = Column(String)        # ticket_created | decision | review_decision | ...
    ticket_id   = Column(String, index=True)
    detail      = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow)


class ChatMessageORM(Base):
    __tablename__ = "chat_messages"
    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, index=True)
    role       = Column(String)
    content    = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class DecisionORM(Base):
    __tablename__ = "decisions"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id   = Column(String, index=True)
    category    = Column(String)
    routing     = Column(String)
    confidence  = Column(Float)
    action      = Column(String)
    resolution_detail = Column(JSON)   # full autonomous-resolution payload (steps, status…)
    created_at  = Column(DateTime, default=datetime.utcnow)


# ── Engine setup ───────────────────────────────────────────────────────────────

engine = None
AsyncSessionLocal = None


def _resolve_db_url() -> str:
    """Normalise the configured DB URL to an async SQLAlchemy driver URL."""
    url = settings.postgres_url
    if url.startswith("sqlite"):
        # Ensure the async driver is used and the parent dir exists.
        if "+aiosqlite" not in url:
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        path_part = url.split(":///", 1)[-1]
        if path_part and path_part != ":memory:":
            from pathlib import Path
            Path(path_part).parent.mkdir(parents=True, exist_ok=True)
        return url
    # Postgres → async driver
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


async def init_db():
    global engine, AsyncSessionLocal
    db_url = _resolve_db_url()
    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration: add columns introduced after the DB was first
        # created (SQLite's create_all won't ALTER existing tables).
        await _ensure_column(conn, "tickets", "user_id", "VARCHAR")
        await _ensure_column(conn, "tickets", "embedding", "TEXT")
        await _ensure_column(conn, "users", "department", "VARCHAR")
    backend = "SQLite" if settings.is_sqlite else "PostgreSQL"
    logger.info(f"Database initialized ({backend}): {db_url}")
    await _seed_users()


async def _ensure_column(conn, table: str, column: str, coltype: str):
    """Idempotently add a column to an existing table (SQLite/Postgres)."""
    from sqlalchemy import text
    try:
        if settings.is_sqlite:
            rows = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
            cols = [r[1] for r in rows.fetchall()]
            if column not in cols:
                await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                logger.info(f"Migration: added {table}.{column}")
        else:
            await conn.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}")
    except Exception as e:
        logger.warning(f"Migration for {table}.{column} skipped: {e}")


async def _seed_users():
    """Create the seeded admin + client + 5 department accounts on first startup."""
    from core.auth import hash_password
    # (username, password, role, department)
    seeds = [
        ("admin", settings.seed_admin_password, "admin", None),
        ("client", settings.seed_client_password, "client", None),
        ("tsg", "tsg123", "department", "TSG"),
        ("base", "base123", "department", "BASE"),
        ("hrgo", "hrgo123", "department", "HR-GO"),
        ("hrbp", "hrbp123", "department", "HR-BP"),
        ("finance", "finance123", "department", "Finance"),
    ]
    async with get_session() as db:
        for username, pw, role, dept in seeds:
            existing = await db.execute(select(UserORM).where(UserORM.username == username))
            if existing.scalar_one_or_none() is None:
                db.add(UserORM(username=username, password_hash=hash_password(pw),
                               role=role, department=dept))
                logger.info(f"Seeded user: {username} ({role}{'/'+dept if dept else ''})")
        await db.commit()


def get_session():
    return AsyncSessionLocal()


# ── CRUD ───────────────────────────────────────────────────────────────────────

def _sla_deadline_for(priority: str, start: datetime) -> datetime:
    from datetime import timedelta
    hours = settings.sla_hours_by_priority.get(priority, settings.sla_hours_medium)
    return start + timedelta(hours=hours)


async def create_ticket(ticket: TicketCreate, session_id: str = None,
                        user_id: str = None, embedding: list = None) -> TicketInDB:
    import json as _json
    ticket_id = f"TKT-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.utcnow()
    sla = _sla_deadline_for(ticket.priority.value, now)
    async with get_session() as db:
        orm = TicketORM(
            id=ticket_id,
            title=ticket.title,
            description=ticket.description,
            priority=ticket.priority.value,
            department=ticket.department,
            source=ticket.source,
            session_id=session_id,
            user_id=user_id,
            status="open",
            created_at=now,
            sla_deadline=sla,
            embedding=_json.dumps(embedding) if embedding else None,
        )
        db.add(orm)
        db.add(AuditLogORM(actor=user_id or session_id or "system", action="ticket_created",
                           ticket_id=ticket_id, detail=f"priority={ticket.priority.value}"))
        await db.commit()
    return TicketInDB(
        ticket_id=ticket_id,
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        department=ticket.department,
        source=ticket.source,
        session_id=session_id,
        user_id=user_id,
        status="open",
        created_at=now,
        sla_deadline=sla,
    )


async def get_ticket(ticket_id: str) -> Optional[TicketInDB]:
    async with get_session() as db:
        result = await db.execute(select(TicketORM).where(TicketORM.id == ticket_id))
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        return _ticket_to_model(orm)


def _ticket_to_model(r) -> TicketInDB:
    return TicketInDB(
        ticket_id=r.id, title=r.title, description=r.description,
        priority=r.priority or "medium", status=r.status,
        department=r.department, source=r.source or "chat",
        session_id=r.session_id, user_id=r.user_id, created_at=r.created_at,
        category=r.category, resolution_type=r.resolution_type,
        model_used=r.model_used, confidence=r.confidence,
        sla_deadline=r.sla_deadline, resolved_at=r.resolved_at,
    )


async def update_ticket_status(ticket_id: str, status: str, resolved: bool = False) -> bool:
    """Update a ticket's status (e.g. reopen → 'escalated'). Returns True if found."""
    async with get_session() as db:
        result = await db.execute(select(TicketORM).where(TicketORM.id == ticket_id))
        orm = result.scalar_one_or_none()
        if not orm:
            return False
        orm.status = status
        if resolved:
            orm.resolved_at = datetime.utcnow()
        db.add(AuditLogORM(actor="system", action="ticket_status",
                           ticket_id=ticket_id, detail=status))
        await db.commit()
        return True


async def escalate_overdue_tickets() -> list:
    """
    Mark still-active tickets (open / in_review) whose SLA deadline has passed as
    'escalated'. Returns the list of escalated ticket ids. Resolved/already-escalated
    tickets are untouched. Called periodically by the SLA watchdog.
    """
    now = datetime.utcnow()
    escalated = []
    async with get_session() as db:
        result = await db.execute(
            select(TicketORM).where(
                TicketORM.status.in_(["open", "in_review"]),
                TicketORM.sla_deadline.isnot(None),
                TicketORM.sla_deadline < now,
            )
        )
        rows = result.scalars().all()
        for t in rows:
            t.status = "escalated"
            db.add(AuditLogORM(actor="sla_watchdog", action="sla_escalation",
                               ticket_id=t.id, detail="SLA deadline breached"))
            escalated.append(t.id)
        if rows:
            await db.commit()
    return escalated


async def list_tickets(status=None, category=None, session_id=None, user_id=None,
                       category_in=None, limit=50, offset=0):
    async with get_session() as db:
        q = select(TicketORM)
        if status:
            q = q.where(TicketORM.status == status)
        if category:
            q = q.where(TicketORM.category == category)
        if category_in:
            q = q.where(TicketORM.category.in_(category_in))
        if session_id:
            q = q.where(TicketORM.session_id == session_id)
        if user_id:
            q = q.where(TicketORM.user_id == user_id)
        q = q.order_by(TicketORM.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return [_ticket_to_model(r) for r in result.scalars().all()]


async def get_analytics(days: int = 14, categories_filter=None) -> dict:
    """Richer dashboard analytics: trends, priority mix, SLA compliance, feedback.
    Pass `categories_filter` to scope to a department's categories."""
    from datetime import timedelta
    cf = list(categories_filter) if categories_filter else None
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    pri = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    created_by_day, resolved_by_day = {}, {}
    sla_met = sla_late = 0

    async with get_session() as db:
        rq = select(TicketORM.created_at, TicketORM.resolved_at,
                    TicketORM.priority, TicketORM.sla_deadline)
        if cf:
            rq = rq.where(TicketORM.category.in_(cf))
        rows = (await db.execute(rq)).all()
        uq = select(func.count()).select_from(FeedbackORM).where(FeedbackORM.notes.like("helpful=True%"))
        dq = select(func.count()).select_from(FeedbackORM).where(FeedbackORM.notes.like("helpful=False%"))
        if cf:
            uq = uq.where(FeedbackORM.predicted_category.in_(cf))
            dq = dq.where(FeedbackORM.predicted_category.in_(cf))
        up = (await db.execute(uq)).scalar() or 0
        down = (await db.execute(dq)).scalar() or 0

    for created, resolved, priority, sla in rows:
        if priority in pri:
            pri[priority] += 1
        if created and created >= since:
            k = created.date().isoformat()
            created_by_day[k] = created_by_day.get(k, 0) + 1
        if resolved and resolved >= since:
            k = resolved.date().isoformat()
            resolved_by_day[k] = resolved_by_day.get(k, 0) + 1
        if resolved and sla:
            if resolved <= sla:
                sla_met += 1
            else:
                sla_late += 1

    trend = []
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).date().isoformat()
        trend.append({"date": d, "created": created_by_day.get(d, 0),
                      "resolved": resolved_by_day.get(d, 0)})

    compliance = round(100 * sla_met / (sla_met + sla_late), 1) if (sla_met + sla_late) else None
    return {
        "trend": trend,
        "priority": pri,
        "sla": {"met": sla_met, "late": sla_late, "compliance_pct": compliance},
        "feedback": {"up": up, "down": down},
    }


async def find_similar_tickets(embedding: list, exclude_id: str = None,
                               threshold: float = 0.75, limit: int = 5,
                               days: int = 14) -> list:
    """Cosine-similarity search over recent tickets' stored embeddings."""
    import json as _json
    import numpy as np
    from datetime import timedelta
    if not embedding:
        return []
    since = datetime.utcnow() - timedelta(days=days)
    async with get_session() as db:
        q = (select(TicketORM)
             .where(TicketORM.embedding.isnot(None), TicketORM.created_at >= since)
             .order_by(TicketORM.created_at.desc()).limit(500))
        rows = (await db.execute(q)).scalars().all()
    qv = np.array(embedding, dtype=float)
    qn = np.linalg.norm(qv) + 1e-9
    out = []
    for t in rows:
        if exclude_id and t.id == exclude_id:
            continue
        try:
            ev = np.array(_json.loads(t.embedding), dtype=float)
        except Exception:
            continue
        if ev.shape != qv.shape:
            continue
        sim = float(qv.dot(ev) / (qn * (np.linalg.norm(ev) + 1e-9)))
        if sim >= threshold:
            out.append({"ticket_id": t.id, "title": t.title, "status": t.status,
                        "category": t.category, "similarity": round(sim, 3),
                        "created_at": t.created_at.isoformat() if t.created_at else None})
    out.sort(key=lambda x: -x["similarity"])
    return out[:limit]


# ── Users ──────────────────────────────────────────────────────────────────────

async def create_user(username: str, password_hash: str, role: str = "client") -> dict:
    async with get_session() as db:
        existing = await db.execute(select(UserORM).where(UserORM.username == username))
        if existing.scalar_one_or_none() is not None:
            return None  # username taken
        u = UserORM(username=username, password_hash=password_hash, role=role)
        db.add(u)
        await db.commit()
        return {"id": u.id, "username": u.username, "role": u.role}


async def get_user_by_username(username: str):
    async with get_session() as db:
        result = await db.execute(select(UserORM).where(UserORM.username == username))
        u = result.scalar_one_or_none()
        if not u:
            return None
        return {"id": u.id, "username": u.username, "role": u.role,
                "department": u.department, "password_hash": u.password_hash}


async def list_teams_with_counts() -> list:
    """All departments with ticket counts — powers the admin Teams → Tickets view."""
    from core.teams import DEPARTMENTS, DEPARTMENT_NAMES
    active = ["open", "in_review", "escalated"]
    async with get_session() as db:
        out = []
        for code, cats in DEPARTMENTS.items():
            total = await db.scalar(
                select(func.count(TicketORM.id)).where(TicketORM.category.in_(cats)))
            open_ct = await db.scalar(
                select(func.count(TicketORM.id)).where(
                    TicketORM.category.in_(cats), TicketORM.status.in_(active)))
            out.append({"department": code, "name": DEPARTMENT_NAMES.get(code, code),
                        "categories": cats,
                        "ticket_count": total or 0, "open_count": open_ct or 0})
        return out


async def list_users_with_counts() -> list:
    """All users with their ticket counts — powers the admin Users → Tickets view."""
    async with get_session() as db:
        users = (await db.execute(select(UserORM).order_by(UserORM.created_at))).scalars().all()
        out = []
        for u in users:
            total = await db.scalar(
                select(func.count(TicketORM.id)).where(TicketORM.user_id == u.id))
            open_ct = await db.scalar(
                select(func.count(TicketORM.id)).where(
                    TicketORM.user_id == u.id,
                    TicketORM.status.in_(["open", "in_review", "escalated"])))
            out.append({"id": u.id, "username": u.username, "role": u.role,
                        "ticket_count": total or 0, "open_count": open_ct or 0})
        return out


async def save_decision(ticket_id, classification, routing, action, resolution_detail=None):
    async with get_session() as db:
        d = DecisionORM(
            ticket_id=ticket_id,
            category=classification.category,
            routing=routing,
            confidence=classification.confidence,
            action=action,
            resolution_detail=resolution_detail,
        )
        db.add(d)
        # Update ticket + drive the status lifecycle from the routing decision.
        result = await db.execute(select(TicketORM).where(TicketORM.id == ticket_id))
        t = result.scalar_one_or_none()
        if t:
            t.category = classification.category
            t.resolution_type = routing
            t.confidence = classification.confidence
            t.model_used = classification.model_used
            status_map = {"autonomous": "resolved", "hitl": "in_review", "human": "escalated"}
            t.status = status_map.get(routing, "in_review")
            if t.status == "resolved":
                t.resolved_at = datetime.utcnow()
        db.add(AuditLogORM(actor="decision_engine", action="decision", ticket_id=ticket_id,
                           detail=f"routing={routing} category={classification.category} "
                                  f"conf={classification.confidence:.2f}"))
        await db.commit()


async def push_to_review_queue(ticket, classification, priority="normal"):
    queue_id = str(uuid.uuid4())
    async with get_session() as db:
        q = ReviewQueueORM(
            id=queue_id,
            ticket_id=ticket.ticket_id,
            ticket_data=ticket.model_dump(mode="json"),
            ai_prediction=classification.model_dump(mode="json"),
            priority=priority,
        )
        db.add(q)
        await db.commit()
    return queue_id


def _queue_to_model(r) -> ReviewQueue:
    td = dict(r.ticket_data or {})
    return ReviewQueue(
        queue_id=r.id, ticket_id=r.ticket_id,
        ticket=TicketInDB(**td),
        ai_prediction=ClassificationResult(**r.ai_prediction),
        created_at=r.created_at, status=r.status,
        priority=r.priority or "normal",
        sla_deadline=td.get("sla_deadline"),
    )


async def get_review_queue(status="pending", category=None, priority=None, limit=50,
                           categories=None):
    cats = set(categories) if categories else None
    async with get_session() as db:
        result = await db.execute(
            select(ReviewQueueORM)
            .where(ReviewQueueORM.status == status)
            .order_by(ReviewQueueORM.created_at.asc())
            .limit(500)
        )
        rows = result.scalars().all()
        out = []
        for r in rows:
            item = _queue_to_model(r)
            # Department scoping: only this department's categories.
            if cats is not None and item.ai_prediction.category not in cats:
                continue
            # Filters apply to the ticket's real category/priority.
            if category and item.ai_prediction.category != category:
                continue
            if priority and item.ticket.priority != priority:
                continue
            out.append(item)
        # Sort by priority (critical → high → medium → low), then oldest first.
        rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        out.sort(key=lambda i: (rank.get(i.ticket.priority, 2), i.created_at or datetime.min))
        return out[:limit]


async def get_review_item(queue_id):
    async with get_session() as db:
        result = await db.execute(
            select(ReviewQueueORM).where(ReviewQueueORM.id == queue_id)
        )
        r = result.scalar_one_or_none()
        if not r:
            return None
        return _queue_to_model(r)


async def submit_review_decision(decision: ReviewDecision, item: ReviewQueue):
    async with get_session() as db:
        result = await db.execute(
            select(ReviewQueueORM).where(ReviewQueueORM.id == decision.queue_id)
        )
        r = result.scalar_one_or_none()
        if r:
            r.status = "approved" if decision.approved else "overridden"
            r.resolved_at = datetime.utcnow()
        # Agent has handled the ticket → mark it resolved.
        tres = await db.execute(select(TicketORM).where(TicketORM.id == item.ticket_id))
        t = tres.scalar_one_or_none()
        if t:
            if decision.override_category:
                t.category = decision.override_category
            if decision.override_resolution:
                t.resolution_type = decision.override_resolution.value
            t.status = "resolved"
            t.resolved_at = datetime.utcnow()
        db.add(AuditLogORM(
            actor=decision.agent_id or "agent", action="review_decision",
            ticket_id=item.ticket_id,
            detail=("approved" if decision.approved else "overridden")
                   + f" -> {decision.override_category or item.ai_prediction.category}"
                   + (f" | notes: {decision.notes}" if decision.notes else ""),
        ))
        await db.commit()


async def save_feedback_log(feedback: FeedbackLog):
    async with get_session() as db:
        f = FeedbackORM(
            ticket_id=feedback.ticket_id,
            predicted_category=feedback.predicted_category,
            predicted_resolution=feedback.predicted_resolution,
            predicted_confidence=feedback.predicted_confidence,
            final_category=feedback.final_category,
            final_resolution=feedback.final_resolution,
            was_corrected=feedback.was_corrected,
            agent_id=feedback.agent_id,
            notes=feedback.notes,
        )
        db.add(f)
        await db.commit()


# ── Audit log & model metrics ────────────────────────────────────────────────

async def list_audit(limit=100, ticket_id=None):
    async with get_session() as db:
        q = select(AuditLogORM)
        if ticket_id:
            q = q.where(AuditLogORM.ticket_id == ticket_id)
        q = q.order_by(AuditLogORM.created_at.desc()).limit(limit)
        rows = (await db.execute(q)).scalars().all()
        return [
            {"actor": r.actor, "action": r.action, "ticket_id": r.ticket_id,
             "detail": r.detail, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]


async def record_model_metric(f1, accuracy, total_samples):
    correction_rate = (await get_hitl_stats()).get("correction_rate", 0)
    async with get_session() as db:
        db.add(ModelMetricORM(f1=f1, accuracy=accuracy,
                              correction_rate=correction_rate, total_samples=total_samples))
        await db.commit()


async def get_model_perf():
    async with get_session() as db:
        rows = (await db.execute(
            select(ModelMetricORM).order_by(ModelMetricORM.run_date.asc())
        )).scalars().all()
        history = [
            {"date": r.run_date.strftime("%Y-%m-%d %H:%M") if r.run_date else "",
             "f1": r.f1, "accuracy": r.accuracy,
             "correction_rate": r.correction_rate, "total_samples": r.total_samples}
            for r in rows
        ]
        return {"has_data": len(history) > 0, "history": history}


async def get_feedback_count():
    async with get_session() as db:
        result = await db.execute(select(func.count()).select_from(FeedbackORM))
        return result.scalar()


async def get_session_history(session_id):
    async with get_session() as db:
        result = await db.execute(
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(ChatMessageORM.created_at.asc())
            .limit(20)
        )
        from models.schemas import ChatMessage, MessageRole
        return [
            ChatMessage(role=MessageRole(r.role), content=r.content)
            for r in result.scalars().all()
        ]


async def save_message(session_id, role, content):
    async with get_session() as db:
        m = ChatMessageORM(session_id=session_id, role=role, content=content)
        db.add(m)
        await db.commit()


async def get_hitl_stats(categories=None):
    """HITL stats; pass `categories` to scope to a department."""
    cf = set(categories) if categories else None
    async with get_session() as db:
        # Pending count — review_queue stores category in JSON, so filter in Python.
        pend_rows = (await db.execute(
            select(ReviewQueueORM).where(ReviewQueueORM.status == "pending"))).scalars().all()
        if cf is not None:
            pending = sum(1 for r in pend_rows
                          if (r.ai_prediction or {}).get("category") in cf)
        else:
            pending = len(pend_rows)
        total = (await db.execute(select(func.count()).select_from(ReviewQueueORM))).scalar()

        corr_q = select(func.count()).select_from(FeedbackORM).where(FeedbackORM.was_corrected == True)
        fb_q = select(func.count()).select_from(FeedbackORM)
        if cf is not None:
            corr_q = corr_q.where(FeedbackORM.predicted_category.in_(list(cf)))
            fb_q = fb_q.where(FeedbackORM.predicted_category.in_(list(cf)))
        corrections = (await db.execute(corr_q)).scalar()
        total_fb = (await db.execute(fb_q)).scalar()

        sla_q = (select(func.count()).select_from(TicketORM)
                 .where(TicketORM.status != "resolved")
                 .where(TicketORM.sla_deadline.isnot(None))
                 .where(TicketORM.sla_deadline < datetime.utcnow()))
        if cf is not None:
            sla_q = sla_q.where(TicketORM.category.in_(list(cf)))
        sla_breached = (await db.execute(sla_q)).scalar()
        return {
            "total_queued": total,
            "pending": pending,
            "total_feedback": total_fb,
            "correction_rate": round(corrections / total_fb, 3) if total_fb else 0,
            "sla_breached": sla_breached or 0,
        }


async def get_routing_stats(categories_filter=None):
    """Routing/category stats. Pass `categories_filter` to scope to a department."""
    cf = list(categories_filter) if categories_filter else None
    async with get_session() as db:
        rq = select(DecisionORM.routing, func.count()).group_by(DecisionORM.routing)
        if cf:
            rq = rq.where(DecisionORM.category.in_(cf))
        result = await db.execute(rq)
        routing = {r: c for r, c in result.all()}

        cq = (select(DecisionORM.category, func.count()).group_by(DecisionORM.category)
              .order_by(func.count().desc()).limit(10))
        if cf:
            cq = cq.where(DecisionORM.category.in_(cf))
        cat_result = await db.execute(cq)
        categories = [{"category": c, "count": n} for c, n in cat_result.all()]

        tq = select(func.count()).select_from(TicketORM)
        if cf:
            tq = tq.where(TicketORM.category.in_(cf))
        total = (await db.execute(tq)).scalar()

        # Average resolution time (hours) over resolved tickets.
        rr = select(TicketORM.created_at, TicketORM.resolved_at).where(TicketORM.resolved_at.isnot(None))
        if cf:
            rr = rr.where(TicketORM.category.in_(cf))
        res_rows = (await db.execute(rr)).all()
        avg_resolution_hours = None
        if res_rows:
            secs = [(rv - cv).total_seconds() for cv, rv in res_rows if cv and rv]
            if secs:
                avg_resolution_hours = round(sum(secs) / len(secs) / 3600, 2)

        return {
            "total_tickets": total,
            "routing": routing,
            "top_categories": categories,
            "avg_resolution_hours": avg_resolution_hours,
        }
