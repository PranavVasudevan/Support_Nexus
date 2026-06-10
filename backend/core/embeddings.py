"""
Text embeddings via Ollama — powers duplicate / similar-ticket detection.
Uses a small dedicated embedding model (nomic-embed-text) since chat models
(qwen2.5) don't expose an embedding endpoint.
"""
from typing import Optional, List

import httpx
from loguru import logger

from core.config import settings

_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))


async def embed(text: str) -> Optional[List[float]]:
    """Return the embedding vector for `text`, or None on failure."""
    if not settings.ollama_enabled or not text or not text.strip():
        return None
    try:
        resp = await _client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/embed",
            json={"model": settings.embed_model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        vecs = data.get("embeddings")
        if vecs and isinstance(vecs, list):
            return vecs[0]
        # legacy shape
        if data.get("embedding"):
            return data["embedding"]
        return None
    except Exception as e:
        logger.warning(f"embed() failed ({e})")
        return None


async def aclose() -> None:
    await _client.aclose()
