"""
One-off migration: copy all data from the old SQLite DB into PostgreSQL.

Handles the user-ID remap: the 5 department + admin/client users were re-seeded
in Postgres with NEW ids, so SQLite tickets that reference the old ids are
rewritten to the matching Postgres user (matched by username). Self-registered
users (pranav, suman, saji, …) are copied across with their original ids.
Existing rows (by primary key) are skipped, so it's safe to re-run.
"""
import asyncio
import os
import sys

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from db.postgres import (
    Base, TicketORM, UserORM, ReviewQueueORM, FeedbackORM,
    ModelMetricORM, AuditLogORM, ChatMessageORM, DecisionORM,
)

SQLITE_URL = "sqlite+aiosqlite:///C:/Users/sanjisuman/Desktop/TICKET_UPS/data/app.db"
PG_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/tickets_db"


def row_to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


async def copy_generic(ss, ds, ORM, transform=None):
    """Copy all rows of a table, skipping primary keys that already exist."""
    pk = list(ORM.__table__.primary_key.columns)[0].name
    rows = (await ss.execute(select(ORM))).scalars().all()
    existing = set((await ds.execute(select(getattr(ORM, pk)))).scalars().all())
    n = 0
    for r in rows:
        d = row_to_dict(r)
        if transform:
            d = transform(d)
            if d is None:
                continue
        if d[pk] in existing:
            continue
        ds.add(ORM(**d))
        n += 1
    await ds.commit()
    return n, len(rows)


async def main():
    src = create_async_engine(SQLITE_URL)
    dst = create_async_engine(PG_URL)
    async with dst.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Src = sessionmaker(src, class_=AsyncSession, expire_on_commit=False)
    Dst = sessionmaker(dst, class_=AsyncSession, expire_on_commit=False)

    async with Src() as ss, Dst() as ds:
        # 1) Users → build sqlite_id -> pg_id map (by username).
        umap = {}
        for u in (await ss.execute(select(UserORM))).scalars().all():
            existing = (await ds.execute(
                select(UserORM).where(UserORM.username == u.username))).scalar_one_or_none()
            if existing:
                umap[u.id] = existing.id
            else:
                ds.add(UserORM(id=u.id, username=u.username, password_hash=u.password_hash,
                               role=u.role, department=getattr(u, "department", None),
                               created_at=u.created_at))
                umap[u.id] = u.id
        await ds.commit()
        pg_user_ids = set((await ds.execute(select(UserORM.id))).scalars().all())
        print(f"users: mapped {len(umap)} (now {len(pg_user_ids)} in Postgres)")

        # 2) Tickets → rewrite user_id via the map.
        def fix_ticket(d):
            uid = umap.get(d.get("user_id"), d.get("user_id"))
            d["user_id"] = uid if uid in pg_user_ids else None
            return d
        n, total = await copy_generic(ss, ds, TicketORM, transform=fix_ticket)
        print(f"tickets: copied {n}/{total}")

        # 3) The rest reference ticket_id (string) — copy as-is, skip existing.
        for ORM, label in [(DecisionORM, "decisions"), (FeedbackORM, "feedback_logs"),
                           (ReviewQueueORM, "review_queue"), (ModelMetricORM, "model_metrics"),
                           (AuditLogORM, "audit_log"), (ChatMessageORM, "chat_messages")]:
            try:
                n, total = await copy_generic(ss, ds, ORM)
                print(f"{label}: copied {n}/{total}")
            except Exception as e:
                print(f"{label}: SKIPPED ({e})")

    await src.dispose()
    await dst.dispose()
    print("Migration complete.")


asyncio.run(main())
