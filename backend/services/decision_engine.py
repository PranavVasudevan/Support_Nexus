"""
Decision Engine
Receives (ticket, classification) → routes to autonomous / HITL / human
Completely model-agnostic: only cares about category + confidence tuple.
"""
import uuid
from loguru import logger

from models.schemas import (
    ClassificationResult,
    DecisionResult,
    ResolutionType,
    TicketInDB,
)
from core.config import settings
from db.postgres import save_decision, push_to_review_queue
from services.autonomous_resolver import AutonomousResolver


class DecisionEngine:
    def __init__(self):
        self.resolver = AutonomousResolver()

    async def process(
        self,
        ticket: TicketInDB,
        classification: ClassificationResult,
        language: str = "English",
    ) -> DecisionResult:
        """Route a classified ticket to the correct resolution path."""
        confidence = classification.confidence
        resolution = classification.resolution_type

        logger.info(
            f"[{ticket.ticket_id}] category={classification.category} "
            f"confidence={confidence:.3f} resolution={resolution}"
        )

        # Sensitive / human-only categories always go to a human, regardless of
        # how confident the model is.
        if resolution == ResolutionType.human:
            result = await self._human_path(ticket, classification)
        elif (
            resolution == ResolutionType.autonomous
            and confidence >= settings.confidence_autonomous
        ):
            result = await self._autonomous_path(ticket, classification, language)
        elif confidence >= settings.confidence_hitl:
            result = await self._hitl_path(ticket, classification)
        else:
            result = await self._human_path(ticket, classification)

        # Prometheus instrumentation (never allowed to break the request path).
        try:
            from api.routes.metrics import record_decision
            record_decision(result.routing.value, classification.category, confidence)
        except Exception:
            pass

        return result

    async def _autonomous_path(
        self, ticket: TicketInDB, classification: ClassificationResult,
        language: str = "English",
    ) -> DecisionResult:
        """Auto-resolve: run the category workflow, record every step, close."""
        logger.info(f"[{ticket.ticket_id}] → AUTONOMOUS path")

        resolution = await self.resolver.resolve(ticket, classification.category, language)

        await save_decision(
            ticket_id=ticket.ticket_id,
            classification=classification,
            routing="autonomous",
            action=f"{resolution.reference_id}: {resolution.summary}",
            resolution_detail=resolution.model_dump(mode="json"),
        )

        # If the workflow itself failed, fall back to a human queue.
        if not resolution.automated or resolution.status == "failed":
            queue_id = await push_to_review_queue(ticket, classification, priority="high")
            return DecisionResult(
                ticket_id=ticket.ticket_id,
                classification=classification,
                routing=ResolutionType.human,
                action_taken=f"Auto-resolution failed — escalated to agent ({queue_id})",
                requires_review=True,
                resolution=resolution,
            )

        return DecisionResult(
            ticket_id=ticket.ticket_id,
            classification=classification,
            routing=ResolutionType.autonomous,
            action_taken=resolution.summary,
            requires_review=False,
            resolution=resolution,
        )

    async def _hitl_path(
        self, ticket: TicketInDB, classification: ClassificationResult
    ) -> DecisionResult:
        """Queue for human review with AI suggestion attached."""
        logger.info(f"[{ticket.ticket_id}] → HITL path")

        queue_id = await push_to_review_queue(ticket, classification)

        await save_decision(
            ticket_id=ticket.ticket_id,
            classification=classification,
            routing="hitl",
            action=f"queued:{queue_id}",
        )

        return DecisionResult(
            ticket_id=ticket.ticket_id,
            classification=classification,
            routing=ResolutionType.hitl,
            action_taken=f"Added to review queue: {queue_id}",
            requires_review=True,
        )

    async def _human_path(
        self, ticket: TicketInDB, classification: ClassificationResult
    ) -> DecisionResult:
        """Low confidence or sensitive — full human handling."""
        logger.info(f"[{ticket.ticket_id}] → HUMAN path")

        queue_id = await push_to_review_queue(
            ticket, classification, priority="high"
        )

        await save_decision(
            ticket_id=ticket.ticket_id,
            classification=classification,
            routing="human",
            action=f"escalated:{queue_id}",
        )

        return DecisionResult(
            ticket_id=ticket.ticket_id,
            classification=classification,
            routing=ResolutionType.human,
            action_taken="Escalated to human agent",
            requires_review=True,
        )
