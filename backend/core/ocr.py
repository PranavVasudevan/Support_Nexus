"""
Screenshot OCR — extract error text from an uploaded image with Tesseract.
The extracted text is then fed through the normal chat/classification flow
(same qwen2.5 model), so no vision model is required.
"""
import io
import os

from loguru import logger

from core.config import settings

_READY = False


def _ensure_tesseract():
    global _READY
    if _READY:
        return True
    import pytesseract
    candidates = [
        settings.tesseract_cmd,
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
        "/usr/bin/tesseract", "/usr/local/bin/tesseract",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            pytesseract.pytesseract.tesseract_cmd = c
            _READY = True
            return True
    # Fall back to PATH (raises later if not found).
    _READY = True
    return True


def extract_text(image_bytes: bytes) -> str:
    """OCR an image (PNG/JPG/…) into plain text. Raises on unreadable input."""
    _ensure_tesseract()
    import pytesseract
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    # Light normalization helps Tesseract on UI screenshots.
    if img.mode != "RGB":
        img = img.convert("RGB")
    text = pytesseract.image_to_string(img)
    cleaned = "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())
    logger.info(f"OCR extracted {len(cleaned)} chars from image")
    return cleaned.strip()
