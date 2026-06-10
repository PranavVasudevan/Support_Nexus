"""
Session state store.

Two interchangeable backends, chosen automatically:

  • Redis      — when REDIS_URL is set (docker-compose / multi-replica). Safe
                 across horizontally-scaled backend replicas, no sticky sessions.
  • In-memory  — when REDIS_URL is blank (no-Docker local mode). A simple
                 in-process dict with TTL expiry. Perfect for single-process
                 local runs; do NOT use with --scale > 1.

The public API (get/set/delete_session_state) is identical for both, so the
rest of the app never needs to know which one is active.
"""
import json
import time
from typing import Optional, Dict, Tuple

from loguru import logger

from core.config import settings

_redis = None                                   # redis.asyncio.Redis | None
_mem: Dict[str, Tuple[float, str]] = {}         # session_id → (expires_at, json)

_DEFAULT = {"gathering": False, "extracted": {}, "missing": []}


async def init_redis():
    """Connect to Redis if configured; otherwise use the in-memory store."""
    global _redis
    if not settings.use_redis:
        _redis = None
        logger.info("Session store: in-memory (no REDIS_URL configured)")
        return
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        await _redis.ping()
        logger.info(f"Session store: Redis ({settings.redis_url})")
    except Exception as e:
        _redis = None
        logger.warning(f"Redis unavailable ({e}); falling back to in-memory session store")


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()


def _key(session_id: str) -> str:
    return f"session:{session_id}"


def _mem_get(session_id: str) -> Optional[str]:
    entry = _mem.get(session_id)
    if not entry:
        return None
    expires_at, raw = entry
    if expires_at < time.time():
        _mem.pop(session_id, None)
        return None
    return raw


async def get_session_state(session_id: str) -> dict:
    """Return session gathering state dict, or default empty state."""
    if _redis:
        raw = await _redis.get(_key(session_id))
    else:
        raw = _mem_get(session_id)
    if raw:
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return dict(_DEFAULT)
    return dict(_DEFAULT)


async def set_session_state(session_id: str, state: dict):
    """Persist session state with TTL."""
    raw = json.dumps(state)
    if _redis:
        await _redis.setex(_key(session_id), settings.session_ttl_seconds, raw)
    else:
        _mem[session_id] = (time.time() + settings.session_ttl_seconds, raw)


async def delete_session_state(session_id: str):
    if _redis:
        await _redis.delete(_key(session_id))
    else:
        _mem.pop(session_id, None)
