"""
Local LLM client — Ollama (replaces the old Gemini Flash integration).

Runs fully offline against a local Ollama server (default
http://localhost:11434), so there is no API key, no rate limit, and no cloud
dependency.

  Install:  https://ollama.com/download
  Pull:     ollama pull qwen2.5:7b

Exposes a single async helper, `ollama_generate`, shared by both the intent
detector and the classifier. It raises on any error (server down, timeout,
non-200) so callers can fall back to their rule-based / keyword paths exactly
the way they did when Gemini was rate-limited.
"""
import httpx

from core.config import settings

# Local inference is much slower than a hosted API (and the first call also has
# to load the model into memory), so use a generous timeout.
_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))


async def ollama_generate(
    prompt: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 400,
    json_mode: bool = False,
) -> str:
    """Call the local Ollama /api/generate endpoint and return the raw text.

    Args:
        prompt:       the full prompt to send.
        temperature:  sampling temperature (0.0 = deterministic).
        max_tokens:   cap on generated tokens (Ollama's ``num_predict``).
        json_mode:    when True, ask Ollama to constrain output to valid JSON
                      (``format: json``) — far more reliable than prompt-only
                      JSON requests. Use for classification / intent calls.

    Returns:
        The model's response text (stripped).

    Raises:
        httpx.HTTPError on connection failure / timeout / non-200 status.
    """
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if json_mode:
        payload["format"] = "json"

    resp = await _client.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json=payload,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


async def aclose() -> None:
    """Close the shared HTTP client (called on app shutdown)."""
    await _client.aclose()
