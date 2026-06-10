"""
Autonomous Resolver
═══════════════════
When the Decision Engine routes a ticket to the *autonomous* path, this service
actually "solves" it: it runs a category-specific workflow, records every step
it executed, and returns a structured AutonomousResolution that is shown to the
user and stored for audit.

Each workflow here SIMULATES the integration calls a real IT automation platform
would make (Okta / Active Directory, Intune / Jamf, Microsoft 365, ServiceNow,
print servers, monitoring agents, …). The integration points are marked with
`# → REAL:` comments so you can drop in live API calls without changing the
shape of the result. The step list, summary, ETA and follow-up are real output
that the chat UI renders so the user can see exactly *how* their issue was
resolved automatically.
"""
import json
import uuid
from typing import Callable, Dict, List, Optional

from loguru import logger

from models.schemas import TicketInDB, AutonomousResolution, ResolutionStep
from core.config import settings
from core.llm import ollama_generate

# Short reference-id prefixes per category (used in AUTO-<prefix>-XXXXXX ids).
_REF_PREFIX = {
    "Password_Reset": "PWR", "Email": "EML", "Printer": "PRN",
    "Cloud_Storage": "STG", "VPN": "VPN", "Software_Install": "SW",
    "Mobile_Device": "MDM", "Performance": "PERF",
}


def _ref(prefix: str) -> str:
    """Generate a human-friendly automation run / work-order id."""
    return f"AUTO-{prefix}-{uuid.uuid4().hex[:6].upper()}"


def _steps(items: List[tuple]) -> List[ResolutionStep]:
    """items: list of (action, detail) — status defaults to done."""
    return [
        ResolutionStep(step=i + 1, action=a, status="done", detail=d)
        for i, (a, d) in enumerate(items)
    ]


class AutonomousResolver:
    """Maps an autonomous category to a workflow that returns AutonomousResolution."""

    def _handlers(self) -> Dict[str, Callable[[TicketInDB], AutonomousResolution]]:
        return {
            "Password_Reset":   self._reset_password,
            "Email":            self._provision_email_resource,
            "Printer":          self._restart_print_spooler,
            "Cloud_Storage":    self._provision_storage,
            "VPN":              self._reset_vpn_config,
            "Software_Install": self._trigger_software_deploy,
            "Mobile_Device":    self._send_mdm_command,
            "Performance":      self._trigger_performance_scan,
        }

    async def resolve(self, ticket: TicketInDB, category: str,
                      language: str = "English") -> AutonomousResolution:
        # 1) Preferred path: let the local LLM generate a solution tailored to
        #    THIS ticket's description (specific, not canned).
        if settings.ollama_enabled:
            try:
                resolution = await self._llm_solution(ticket, category, language)
                if resolution is not None:
                    logger.info(
                        f"[AUTO] {ticket.ticket_id} resolved via LLM solution "
                        f"({resolution.reference_id})"
                    )
                    return resolution
            except Exception as e:
                logger.warning(
                    f"[AUTO] LLM solution failed for {ticket.ticket_id} ({e}); "
                    "using the built-in workflow"
                )

        # 2) Fallback: the deterministic per-category workflow.
        handler = self._handlers().get(category, self._default_resolve)
        try:
            resolution = handler(ticket)
            logger.info(
                f"[AUTO] {ticket.ticket_id} resolved via {category} workflow "
                f"({resolution.reference_id})"
            )
            return resolution
        except Exception as e:
            logger.error(f"[AUTO] resolution failed for {ticket.ticket_id}: {e}")
            return AutonomousResolution(
                automated=False,
                category=category,
                status="failed",
                summary="Automated resolution could not complete — escalating to an agent.",
                reference_id=_ref("ERR"),
                steps=[ResolutionStep(step=1, action="Run automated workflow",
                                      status="failed", detail=str(e))],
                follow_up="An agent has been notified and will pick this up shortly.",
            )

    # ── LLM-generated solution ────────────────────────────────────────────────
    async def _llm_solution(
        self, ticket: TicketInDB, category: str, language: str = "English"
    ) -> Optional[AutonomousResolution]:
        """Ask the local LLM for a concrete, step-by-step fix for this ticket."""
        prompt = f"""You are a senior IT support engineer. A support ticket has been
routed for automatic resolution. Produce a clear, specific, step-by-step solution the
end user can follow to fix THIS exact issue. Tailor it to the described problem — no
generic filler.

Category: {category.replace('_', ' ')}
Title: {ticket.title}
Description: {ticket.description}

Give 4 to 6 concrete steps. Each step has a short "action" (an imperative instruction)
and a one-sentence "detail" explaining it. Then a one-line "summary" of the fix and a
"follow_up" telling the user what to do if it still isn't resolved.
IMPORTANT: Write ALL text values (summary, every action, every detail, follow_up) in
{language}. Keep the JSON keys themselves in English.

Respond ONLY with valid JSON, no markdown:
{{
  "summary": "<one sentence>",
  "steps": [
    {{"action": "<imperative step>", "detail": "<one sentence>"}}
  ],
  "follow_up": "<what to do if this doesn't work>"
}}

JSON:"""
        raw = await ollama_generate(prompt, temperature=0.2, max_tokens=600, json_mode=True)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(raw)

        raw_steps = data.get("steps") or []
        steps: List[ResolutionStep] = []
        for i, s in enumerate(raw_steps[:6]):
            if isinstance(s, dict):
                action = str(s.get("action") or s.get("step") or "").strip()
                detail = s.get("detail")
            else:
                action, detail = str(s).strip(), None
            if action:
                steps.append(ResolutionStep(step=len(steps) + 1, action=action,
                                            status="done",
                                            detail=str(detail).strip() if detail else None))
        if not steps:
            return None  # nothing usable → fall back to the canned workflow

        summary = str(data.get("summary") or "Here are the steps to resolve your issue.").strip()
        follow_up = data.get("follow_up")
        prefix = _REF_PREFIX.get(category, (category[:3] or "GEN").upper())
        return AutonomousResolution(
            automated=True,
            category=category,
            status="resolved",
            summary=summary,
            steps=steps,
            reference_id=_ref(prefix),
            system="AI Assistant",
            follow_up=str(follow_up).strip() if follow_up else
            "If this doesn't resolve it, reply here and we'll escalate to a specialist.",
        )

    # ── Workflows ────────────────────────────────────────────────────────────

    def _reset_password(self, ticket: TicketInDB) -> AutonomousResolution:
        # → REAL: Okta /api/v1/users/{id}/lifecycle/reset_password, or AD reset.
        return AutonomousResolution(
            automated=True,
            category="Password_Reset",
            reference_id=_ref("PWR"),
            system="Okta / Active Directory",
            summary="Your password reset link has been sent to your registered email.",
            steps=_steps([
                ("Verified your identity", "Matched session + registered email on file"),
                ("Revoked active sessions", "Signed out stale sessions to keep the account secure"),
                ("Generated one-time reset link", "Secure link valid for 30 minutes"),
                ("Emailed the reset link", "Sent to your corporate mailbox"),
                ("Logged action to audit trail", "Recorded for compliance"),
            ]),
            follow_up="Open the email and set a new password within 30 minutes. "
                      "If it doesn't arrive in 5 minutes, check spam or reply here.",
        )

    def _reset_vpn_config(self, ticket: TicketInDB) -> AutonomousResolution:
        # → REAL: VPN controller API (Cisco AnyConnect / GlobalProtect) reissue.
        return AutonomousResolution(
            automated=True,
            category="VPN",
            reference_id=_ref("VPN"),
            system="VPN Controller",
            summary="Your VPN profile has been reset and fresh credentials issued.",
            steps=_steps([
                ("Cleared stale VPN session", "Removed the locked/half-open tunnel server-side"),
                ("Rotated VPN certificate", "Issued a new client certificate"),
                ("Rebuilt your VPN profile", "Regenerated the connection profile"),
                ("Emailed the new profile + setup steps", "Sent to your corporate mailbox"),
            ]),
            follow_up="Re-import the emailed VPN profile and reconnect. "
                      "Reply here if it still drops after reconnecting.",
        )

    def _provision_email_resource(self, ticket: TicketInDB) -> AutonomousResolution:
        # → REAL: Microsoft 365 Graph API mailbox repair / quota.
        return AutonomousResolution(
            automated=True,
            category="Email",
            reference_id=_ref("EML"),
            system="Microsoft 365 / Exchange",
            summary="Your mailbox has been repaired and re-synced.",
            steps=_steps([
                ("Checked mailbox health", "Detected a stuck sync state"),
                ("Cleared the sync lock", "Reset the server-side sync token"),
                ("Extended mailbox quota", "Raised quota headroom to prevent re-blocking"),
                ("Triggered a fresh sync", "Re-synchronised mail, calendar and contacts"),
            ]),
            follow_up="Restart Outlook (or refresh webmail). Mail should sync within a few minutes.",
        )

    def _restart_print_spooler(self, ticket: TicketInDB) -> AutonomousResolution:
        # → REAL: remote exec on the print server (WMI / SSH / RMM agent).
        return AutonomousResolution(
            automated=True,
            category="Printer",
            reference_id=_ref("PRN"),
            system="Print Server",
            summary="The print queue was cleared and the spooler restarted.",
            steps=_steps([
                ("Located your print server", "Matched the printer to its host"),
                ("Cancelled stuck jobs", "Cleared the jammed queue"),
                ("Restarted the Print Spooler service", "Service is running again"),
                ("Sent a test page", "Confirmed the printer responds"),
            ]),
            follow_up="Try printing again. If it still fails, reply and we'll dispatch a technician.",
        )

    def _provision_storage(self, ticket: TicketInDB) -> AutonomousResolution:
        # → REAL: OneDrive/SharePoint admin API or Google Drive API.
        return AutonomousResolution(
            automated=True,
            category="Cloud_Storage",
            reference_id=_ref("STG"),
            system="OneDrive / SharePoint",
            summary="Your cloud storage quota has been increased and access restored.",
            steps=_steps([
                ("Checked storage usage", "Account was at/over quota"),
                ("Increased your quota", "Added headroom to your allocation"),
                ("Cleared the access lock", "Re-enabled uploads and sync"),
                ("Re-validated sharing permissions", "Confirmed your access to shared libraries"),
            ]),
            follow_up="Re-open the file or resync the folder. Access should work immediately.",
        )

    def _trigger_software_deploy(self, ticket: TicketInDB) -> AutonomousResolution:
        # → REAL: Intune / SCCM / Jamf deployment job.
        return AutonomousResolution(
            automated=True,
            category="Software_Install",
            status="in_progress",
            reference_id=_ref("SW"),
            system="Intune / SCCM",
            summary="A software installation job has been queued to your device.",
            steps=_steps([
                ("Identified your device", "Matched the asset to your account"),
                ("Validated licensing", "Confirmed an available license seat"),
                ("Queued the install job", "Deployment pushed via device management"),
                ("Scheduled auto-verification", "Will confirm the install on completion"),
            ]),
            eta="10–15 minutes",
            follow_up="Keep your device on and connected. You'll get a confirmation when the "
                      "install finishes. Reply if it isn't done within 30 minutes.",
        )

    def _send_mdm_command(self, ticket: TicketInDB) -> AutonomousResolution:
        # → REAL: Intune / Jamf device action (sync, reset, re-enroll).
        return AutonomousResolution(
            automated=True,
            category="Mobile_Device",
            status="in_progress",
            reference_id=_ref("MDM"),
            system="Mobile Device Management",
            summary="A device management command has been sent to your mobile device.",
            steps=_steps([
                ("Located your enrolled device", "Matched the device in MDM"),
                ("Refreshed device policies", "Re-pushed configuration profiles"),
                ("Issued a sync command", "Forced a check-in to apply changes"),
            ]),
            eta="A few minutes",
            follow_up="Unlock your device and keep it on Wi-Fi so it can check in. "
                      "Reply if the issue persists after it syncs.",
        )

    def _trigger_performance_scan(self, ticket: TicketInDB) -> AutonomousResolution:
        # → REAL: monitoring/RMM agent diagnostic + remediation.
        return AutonomousResolution(
            automated=True,
            category="Performance",
            status="in_progress",
            reference_id=_ref("PERF"),
            system="Monitoring Agent",
            summary="A performance diagnostic and cleanup has been started on your device.",
            steps=_steps([
                ("Started a diagnostic scan", "Collecting CPU / memory / disk telemetry"),
                ("Cleared temp & cache files", "Freed disk space and reset caches"),
                ("Flagged heavy background processes", "Identified resource-hungry tasks"),
            ]),
            eta="~10 minutes",
            follow_up="A diagnostic report will be attached to this ticket. A restart often "
                      "resolves the remainder — reply if it's still slow afterwards.",
        )

    def _default_resolve(self, ticket: TicketInDB) -> AutonomousResolution:
        return AutonomousResolution(
            automated=True,
            category="General",
            summary="An automated resolution workflow was triggered and is being monitored.",
            reference_id=_ref("GEN"),
            steps=_steps([
                ("Triggered the standard remediation workflow", "Generic auto-resolve path"),
                ("Enabled completion monitoring", "Will verify the outcome automatically"),
            ]),
            follow_up="Reply here if the issue isn't resolved shortly.",
        )
