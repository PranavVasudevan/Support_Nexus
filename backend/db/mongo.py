"""
Optional MongoDB layer for chat-event / classification logs.

Mongo is entirely optional. When MONGO_URL is blank (no-Docker local mode) or
the server can't be reached, every log call becomes a silent no-op — the app
keeps working without it. Imports are lazy so `motor` need not be installed
for local runs.
"""
from datetime import datetime
from loguru import logger
from core.config import settings

client = None
db = None


async def init_mongo():
    global client, db
    if not settings.use_mongo:
        logger.info("MongoDB disabled (no MONGO_URL configured) — event logging is a no-op")
        return
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(settings.mongo_url, serverSelectionTimeoutMS=2000)
        db = client.ticket_logs
        logger.info("MongoDB initialized")
    except Exception as e:
        client = None
        db = None
        logger.warning(f"MongoDB unavailable ({e}) — event logging disabled")


async def log_chat_event(session_id: str, event_type: str, data: dict):
    if db is None:
        return
    try:
        await db.chat_events.insert_one({
            "session_id": session_id,
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow(),
        })
    except Exception as e:
        logger.warning(f"MongoDB log failed: {e}")


async def log_classification(ticket_id: str, classification: dict):
    if db is None:
        return
    try:
        await db.classifications.insert_one({
            "ticket_id": ticket_id,
            "classification": classification,
            "timestamp": datetime.utcnow(),
        })
    except Exception as e:
        logger.warning(f"MongoDB classification log failed: {e}")
