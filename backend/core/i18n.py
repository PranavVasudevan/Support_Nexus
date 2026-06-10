"""
Lightweight localization for fixed UI/scaffolding strings.
══════════════════════════════════════════════════════════
The AI-generated content (questions, solution steps, greetings) is already
produced in the user's language by the model. This module localizes the small
set of FIXED template strings (intro lines, ticket header, routing messages)
so the entire reply is in the user's language.

Translations are done once per (language, text) via the local LLM and cached in
memory, so there's no repeated cost. English (or unknown) passes through
unchanged. Placeholder tokens like [[ID]] are preserved verbatim.
"""
from loguru import logger

from core.config import settings
from core.llm import ollama_generate

# (language_lower, text) -> translated text
_cache: dict = {}


def _is_english(language: str) -> bool:
    return not language or language.strip().lower() in ("english", "en", "en-us", "")


async def translate(text: str, language: str, tokens: tuple = ()) -> str:
    """
    Translate `text` into `language`, preserving any [[TOKEN]] placeholders.

    Returns the original text unchanged for English/unknown languages, empty
    input, or if the LLM is disabled/fails. If `tokens` are given and any are
    missing from the translation, the original is returned (so we never lose a
    placeholder like the ticket id).
    """
    if _is_english(language) or not text or not text.strip() or not settings.ollama_enabled:
        return text
    lang = language.strip()
    key = (lang.lower(), text)
    if key in _cache:
        return _cache[key]

    prompt = (
        f"Translate the following UI text into {lang}. Rules:\n"
        "- Keep any tokens in double square brackets like [[ID]] EXACTLY as they are.\n"
        "- Keep emojis and markdown (** **) as they are.\n"
        "- Return ONLY the translated text — no quotes, no notes, no original.\n\n"
        f"Text:\n{text}"
    )
    try:
        out = (await ollama_generate(prompt, temperature=0.0, max_tokens=400)).strip()
        out = out.strip().strip('"').strip()
        if not out:
            return text
        if tokens and not all(t in out for t in tokens):
            logger.warning(f"translate dropped a token for {lang!r}; using original")
            return text
        _cache[key] = out
        return out
    except Exception as e:
        logger.warning(f"translate failed ({e}); using original")
        return text
