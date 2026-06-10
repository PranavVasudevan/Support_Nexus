"""
Classifier Service
Primary:  fine-tuned DistilBERT (fast, on-prem, zero API cost)
Fallback: local LLM via Ollama (qwen2.5:7b by default — fully offline)

Zero-cost strategy:
  - DistilBERT handles ~95-99% of traffic once trained
  - The local LLM fallback fires when the model is absent OR DistilBERT
    confidence is below settings.distilbert_fallback_threshold (default 0.70)
  - Both paths run entirely on-prem — no API keys, no rate limits, no cloud

`torch` / `transformers` are imported lazily so the API can run in an
LLM-only local mode without the heavy ML stack installed.
"""
import json
import httpx
from pathlib import Path
from typing import Optional
from loguru import logger

from core.config import settings
from core.llm import ollama_generate
from models.schemas import ClassificationResult, ResolutionType


RESOLUTION_RULES = {
    # Auto-resolvable — handled end-to-end by the AutonomousResolver
    "Password_Reset":    "autonomous",
    "Email":             "autonomous",
    "Printer":           "autonomous",
    "Cloud_Storage":     "autonomous",
    "VPN":               "autonomous",
    "Software_Install":  "autonomous",
    "Mobile_Device":     "autonomous",
    "Performance":       "autonomous",
    # HITL-assisted
    "Data_Recovery":     "hitl",
    "Database":          "hitl",
    "Hardware":          "hitl",
    "Network":           "hitl",
    "Access_Request":    "hitl",
    "Onboarding":        "hitl",
    "Application_Error": "hitl",
    # Always human — sensitive (never auto-resolved regardless of confidence)
    "Payroll":           "human",
    "Security":          "human",
    "Compliance":        "human",
    "Offboarding":       "human",
    "Billing":           "human",
    # Non-IT buckets assigned by the out-of-domain guard → always human.
    "HR":                "human",
    "Facilities":        "human",
    "Other":             "human",
}

# Categories that must NEVER be auto-resolved, even at 100% confidence.
SENSITIVE_CATEGORIES = {"Payroll", "Security", "Compliance", "Offboarding", "Billing",
                        "HR", "Facilities", "Other"}


class ClassifierService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.model_path = settings.model_path
        self.device = "cpu"          # resolved at load() once torch is imported
        self._model_loaded = False

    async def load(self):
        """Load DistilBERT if a fine-tuned model exists, else rely on the LLM."""
        model_path = Path(settings.model_path)
        has_weights = (
            model_path.exists()
            and (model_path / "config.json").exists()
            and (
                (model_path / "pytorch_model.bin").exists()
                or (model_path / "model.safetensors").exists()
            )
        )
        if not has_weights:
            self._model_loaded = False
            logger.info(
                f"No fine-tuned model at {model_path} — using the local LLM for all "
                "classification. Train one with scripts/initial_train.py for the "
                "faster on-prem path."
            )
            return

        try:
            import torch
            from transformers import (
                DistilBertTokenizerFast,
                DistilBertForSequenceClassification,
            )
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading DistilBERT from {model_path} (device={self.device})...")
            self.tokenizer = DistilBertTokenizerFast.from_pretrained(str(model_path))
            self.model = DistilBertForSequenceClassification.from_pretrained(
                str(model_path)
            ).to(self.device)
            self.model.eval()
            self._model_loaded = True
            logger.info(f"DistilBERT loaded on {self.device}")
        except Exception as e:
            self._model_loaded = False
            logger.warning(f"Could not load DistilBERT: {e}. Local LLM fallback active.")

    async def classify(self, title: str, description: str) -> ClassificationResult:
        """
        Routing:
          1. If a model is loaded, run DistilBERT.
          2. If its confidence ≥ fallback_threshold → trust it.
          3. Otherwise (low confidence) → ask the local LLM for a second opinion.
          4. If no model is loaded at all → the local LLM handles it directly.
        """
        text = f"{title} [SEP] {description}"

        if self._model_loaded:
            result = await self._classify_distilbert(text)
            if result is not None:
                if result.confidence >= settings.distilbert_fallback_threshold:
                    return result
                # Low confidence → prefer the LLM if enabled, else keyword rescue.
                if settings.ollama_enabled:
                    logger.info(
                        f"DistilBERT confidence {result.confidence:.2f} < "
                        f"{settings.distilbert_fallback_threshold} → local LLM fallback"
                    )
                    llm = await self._classify_ollama(title, description)
                    if llm is not None:
                        return llm
                # Final safety net: keyword override on the DistilBERT result.
                override = self._keyword_override(text)
                if override:
                    result.category = override
                    result.resolution_type = self._resolution_enum(override, result.confidence)
                return result

        return await self._classify_ollama(title, description)

    async def _classify_distilbert(self, text: str) -> Optional[ClassificationResult]:
        try:
            import torch
            import numpy as np

            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=256,
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1)[0].cpu().numpy()

            pred_idx = int(np.argmax(probs))
            confidence = float(probs[pred_idx])
            category = settings.id2label[pred_idx]

            all_scores = {
                settings.id2label[i]: float(probs[i]) for i in range(len(probs))
            }

            return ClassificationResult(
                category=category,
                resolution_type=self._resolution_enum(category, confidence),
                confidence=confidence,
                all_scores=all_scores,
                model_used="distilbert",
            )
        except Exception as e:
            logger.error(f"DistilBERT inference error: {e}")
            return None

    async def _classify_ollama(self, title: str, description: str) -> ClassificationResult:
        """Use the local LLM (Ollama) as the zero-cost fallback / primary classifier."""
        categories_str = ", ".join(settings.categories)
        prompt = f"""You are a precise IT support ticket classifier.

Classify this ticket into EXACTLY ONE category from the list and rate your confidence.

Categories: {categories_str}

Ticket title: {title}
Ticket description: {description}

Respond ONLY with valid JSON, no markdown:
{{
  "category": "<exact category name from list>",
  "confidence": 0.0-1.0,
  "reasoning": "<one short sentence>"
}}

JSON:"""

        if not settings.ollama_enabled:
            logger.error("Ollama disabled and no DistilBERT model — cannot classify.")
            return ClassificationResult(
                category="Application_Error",
                resolution_type=ResolutionType.human,
                confidence=0.0,
                model_used="none",
            )

        try:
            raw = await ollama_generate(
                prompt,
                temperature=0.0,
                max_tokens=200,
                json_mode=True,
            )
            # json_mode constrains output to valid JSON, but strip any stray
            # markdown fences just in case.
            raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
            data = json.loads(raw)

            category = data.get("category", "Application_Error")
            if category not in settings.categories:
                category = "Application_Error"
            confidence = float(data.get("confidence", 0.75))

            return ClassificationResult(
                category=category,
                resolution_type=self._resolution_enum(category, confidence),
                confidence=confidence,
                all_scores={category: confidence},
                model_used="ollama_fallback",
            )
        except Exception as e:
            logger.error(f"Ollama classifier error: {e}")
            # Keyword rescue before giving up — keeps the system usable offline.
            override = self._keyword_override(f"{title} {description}")
            cat = override or "Application_Error"
            return ClassificationResult(
                category=cat,
                resolution_type=self._resolution_enum(cat, 0.5),
                confidence=0.50,
                all_scores={cat: 0.5},
                model_used="keyword_fallback" if override else "ollama_fallback",
            )

    def _keyword_override(self, text: str) -> Optional[str]:
        """Override low-confidence predictions using keyword matching.

        Security and billing are checked first so a compromised-card / fraud
        message is correctly treated as a security incident rather than a
        generic application error.
        """
        t = text.lower()
        if any(w in t for w in [
            "security", "breach", "hack", "hacked", "virus", "malware", "phishing",
            "compromis", "fraud", "stolen", "unauthorized", "unauthorised",
            "data breach", "leaked", "identity theft", "scam", "suspicious login",
        ]):
            return "Security"
        if any(w in t for w in [
            "billing", "invoice", "overcharged", "charged twice", "double charged",
            "credit card", "payment", "refund", "subscription charge", "wrong amount billed",
        ]):
            return "Billing"
        if any(w in t for w in ["vpn", "virtual private network"]):
            return "VPN"
        if any(w in t for w in ["password", "pwd", "passphrase", "reset password", "locked out"]):
            return "Password_Reset"
        if any(w in t for w in ["network", "internet", "wifi", "wi-fi", "ethernet"]):
            return "Network"
        if any(w in t for w in ["printer", "print", "scanner", "spooler"]):
            return "Printer"
        if any(w in t for w in ["email", "outlook", "gmail", "mailbox", "smtp"]):
            return "Email"
        if any(w in t for w in ["laptop", "hardware", "keyboard", "monitor", "screen", "mouse"]):
            return "Hardware"
        if any(w in t for w in ["payroll", "salary", "pay slip", "wages", "paycheck"]):
            return "Payroll"
        if any(w in t for w in ["software", "install", "application", "app "]):
            return "Software_Install"
        if any(w in t for w in ["access", "permission", "login", "sign in"]):
            return "Access_Request"
        if any(w in t for w in ["security", "breach", "hack", "virus", "malware", "phishing"]):
            return "Security"
        return None

    def _resolution_enum(self, category: str, confidence: float) -> ResolutionType:
        """Combine per-category rules with confidence thresholds."""
        return ResolutionType(self._get_resolution(category, confidence))

    def _get_resolution(self, category: str, confidence: float) -> str:
        base = RESOLUTION_RULES.get(category, "hitl")
        # Sensitive categories are pinned to human, always.
        if category in SENSITIVE_CATEGORIES:
            return "human"
        if base == "autonomous" and confidence >= settings.confidence_autonomous:
            return "autonomous"
        if confidence >= settings.confidence_hitl:
            return base if base != "autonomous" else "hitl"
        return "human"

    async def close(self):
        # The shared Ollama HTTP client is closed once in main.py's shutdown.
        return
