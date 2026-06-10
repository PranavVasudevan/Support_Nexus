"""
Intent Detection Service
═════════════════════════
Classifies every incoming chat message into one of THREE intents:

  • greeting → small talk / greeting / thanks / bye  → reply conversationally
  • vague    → a bare topic or keyword ("VPN", "laptop", "payment") with no actual
               problem described → ask the user to explain the issue
  • ticket   → a real, described problem → extract fields, then (in the chat flow)
               gather more detail and classify

A fast rule-based pre-filter handles the obvious cases instantly; anything
ambiguous is sent to the local LLM (Ollama). If the LLM is unavailable the
rule-based path still produces a sensible result, so the app degrades
gracefully offline.
"""
import re
import json
from typing import List, Tuple

from loguru import logger

from models.schemas import IntentResult, IntentType, ChatMessage
from core.config import settings
from core.llm import ollama_generate


# ── Keyword vocabularies ─────────────────────────────────────────────────────

# Bare IT topics. On their own (with no problem described) these are "vague" and
# we should ask the user to explain what's actually wrong.
TOPIC_KEYWORDS = [
    "vpn", "laptop", "computer", "pc", "desktop", "printer", "scanner",
    "email", "outlook", "mail", "password", "network", "wifi", "wi-fi",
    "internet", "software", "hardware", "monitor", "keyboard", "mouse",
    "phone", "mobile", "payroll", "salary", "payslip", "bank", "payment",
    "billing", "invoice", "vpn", "server", "database", "access", "login",
    "account", "storage", "drive", "onedrive", "sharepoint", "teams", "zoom",
    "application", "app", "system", "device", "screen", "headset", "camera",
]

# Strong signals that the message describes an ACTUAL problem (→ ticket).
STRONG_PROBLEM_KEYWORDS = [
    "not working", "doesn't work", "won't", "wont", "broken", "error", "errors",
    "can't", "cannot", "unable", "failed", "failing", "crash", "crashing", "bug",
    "stuck", "locked out", "locked", "denied", "outage", "down", "freeze", "frozen",
    "disconnect", "slow", "sluggish", "lagging", "timeout", "times out",
    "blue screen", "won't turn on", "no internet", "overheat", "not able",
    "keeps", "issue with", "problem with", "trouble", "help me", "stopped",
    "compromis", "fraud", "stolen", "hacked", "breach", "phishing", "malware",
    "virus", "deleted", "recover", "reset", "expired", "blocked", "missing",
]

# Greetings / gratitude / closings → small talk.
SMALLTALK_PHRASES = [
    "hi", "hello", "hey", "howdy", "yo", "sup",
    "good morning", "good afternoon", "good evening",
    "how are you", "what's up", "whats up", "how's it going",
    "thank", "thanks", "thx", "ty", "appreciate", "cheers", "that helped",
    "helped a lot", "you helped", "that worked", "it worked", "perfect", "great",
    "awesome", "amazing", "nice", "cool", "good bot", "well done", "good job",
    "bye", "goodbye", "see you", "see ya", "cya", "take care", "later",
    "ok", "okay", "sure", "got it", "understood", "alright", "sounds good",
    "no problem", "np", "nevermind", "nvm", "forget it", "all good",
    "who are you", "what can you do", "what do you do",
]


def _has_strong_problem(msg_lower: str) -> bool:
    return any(kw in msg_lower for kw in STRONG_PROBLEM_KEYWORDS)


def _is_smalltalk(message: str) -> bool:
    """Short greetings / thanks / closings with no real problem signal."""
    msg = message.lower().strip().rstrip("!.?")
    words = msg.split()
    if _has_strong_problem(msg):
        return False
    if len(words) > 6:
        return False
    return any(msg == p or msg.startswith(p + " ") or p == msg for p in SMALLTALK_PHRASES) \
        or any(p in msg for p in SMALLTALK_PHRASES if len(p) > 3)


def _found_topic(msg_lower: str) -> str:
    """Return the first IT topic keyword found in the message, else ''."""
    # word-boundary match so "app" doesn't match "happen"
    for kw in TOPIC_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", msg_lower):
            return kw
    return ""


def _is_vague(message: str) -> bool:
    """
    True when the message is just a topic/keyword (or a couple of words) with no
    actual problem described — e.g. "VPN", "my laptop", "payment". These should
    prompt the user to explain the issue rather than become a ticket.
    """
    msg = message.lower().strip().rstrip("!.?")
    words = msg.split()
    if _has_strong_problem(msg):
        return False                      # there's a real problem → not vague
    if len(words) > 5:
        return False                      # long enough to carry a description
    return bool(_found_topic(msg))        # short + mentions a topic → vague


# ── Conversational reply helpers (used when the LLM is offline) ───────────────

def _greeting_reply(message: str) -> str:
    m = message.lower().strip()
    if any(w in m for w in ["thank", "thanks", "appreciate", "cheers", "ty", "thx", "helped", "worked"]):
        return "Glad I could help! Let me know if anything else comes up."
    if any(w in m for w in ["bye", "goodbye", "see you", "take care", "later", "cya"]):
        return "Take care! I'm here whenever you need IT support."
    if any(w in m for w in ["how are you", "what's up", "whats up", "how's it going"]):
        return "Running smoothly and ready to help! What IT issue can I assist you with today?"
    if any(w in m for w in ["what can you do", "what do you do", "who are you", "can you help"]):
        return ("I'm your IT support assistant. I can help with VPN, passwords, email, "
                "printers, hardware, software installs, network and access issues — "
                "just describe the problem you're facing.")
    return "Hey there! I'm your IT support assistant. What tech issue can I help you with today?"


def _vague_reply(topic: str) -> str:
    nice = topic.upper() if topic.lower() == "vpn" else topic
    return (
        f"I can help with **{nice}**-related issues. Could you explain what's actually "
        f"happening? For example: what you were trying to do, any error message you see, "
        f"and when it started."
    )


def _rule_extract_priority(message: str) -> str:
    low = message.lower()
    CRITICAL = ["compromis", "breach", "hacked", "ransomware", "data breach", "outage",
                "production down", "system down", "server down", "stolen", "fraud",
                "urgent", "asap", "emergency", "critical", "immediately", "right now",
                "everyone", "all users", "company-wide", "security incident", "phishing"]
    HIGH = ["high priority", "important", "blocking", "blocked", "deadline",
            "time-sensitive", "as soon as possible", "major", "multiple users",
            "can't access", "cannot access", "locked out", "not working"]
    LOW = ["low priority", "no rush", "whenever", "not urgent", "minor",
           "when you get a chance", "at your convenience", "no hurry", "small issue"]
    if any(w in low for w in CRITICAL):
        return "critical"
    if any(w in low for w in HIGH):
        return "high"
    if any(w in low for w in LOW):
        return "low"
    return "medium"


def _title_from(message: str) -> str:
    words = message.strip().split()
    title = " ".join(words[:8])
    if len(words) > 8:
        title += "…"
    return title or "Support request"


# Generic clarifying questions per topic — used when the LLM is offline.
_GENERIC_QUESTIONS = {
    "vpn": ["Which VPN client are you using (e.g. Cisco AnyConnect, GlobalProtect)?",
            "What exact error or behaviour do you see when connecting?",
            "Did it work before, and what changed (password, network, update)?"],
    "password": ["Which account or system are you locked out of?",
                 "What happens when you try to sign in (error message)?",
                 "Have you tried the self-service reset already?"],
    "printer": ["Which printer (name/location) is affected?",
                "What error shows, and is it for one document or all?",
                "Are other people able to print to it?"],
    "email": ["Which mail app are you using (Outlook desktop, webmail, phone)?",
              "What's happening — not sending, not receiving, or an error?",
              "When did it start, and does it affect all mail or some?"],
    "payment": ["What exactly is wrong with the payment (charged twice, failed, wrong amount)?",
                "Which transaction/invoice and what amount?",
                "When did it happen?"],
}
_DEFAULT_QUESTIONS = [
    "What exactly is happening (the symptom)?",
    "Is there an error message — what does it say?",
    "When did it start, and what have you already tried?",
]


def _generic_questions(topic: str) -> list:
    return _GENERIC_QUESTIONS.get(topic, _DEFAULT_QUESTIONS)


# Appended to every user-facing LLM prompt so replies match the user's language.
_LANG_RULE = ("Write your entire response in the SAME LANGUAGE the user is writing in "
              "(detect it from their message). Keep any JSON keys in English.")

# Phrases that signal a previous solution didn't work → reopen / escalate.
# Stored apostrophe-free; the message is normalized the same way before matching
# so "doesn't", "doesnt" and "doesn’t" all match.
_DISSATISFACTION = [
    "didnt work", "did not work", "doesnt work", "does not work", "not working",
    "still not", "still broken", "still happening", "still the same", "still doesnt",
    "still does not", "still not working", "still an issue", "same problem",
    "same issue", "not fixed", "didnt help", "did not help", "doesnt help",
    "not helping", "no luck", "no change", "not resolved", "isnt resolved",
    "not solved", "tried that", "tried all that", "tried those", "already tried",
    "that didnt", "still cant", "still cannot", "didnt fix", "doesnt fix",
    "didnt solve", "stopped working again",
]


def _is_dissatisfaction(message: str) -> bool:
    # Normalize away apostrophes (straight + curly) so "doesnt"/"doesn't" both hit.
    m = message.lower().replace("'", "").replace("’", "")
    return any(p in m for p in _DISSATISFACTION)


# Clearly NON-IT signals — a keyword backstop for the out-of-domain guard, in case
# the LLM mislabels an HR/facilities request as an IT issue. Word-boundary regex
# so "desk" doesn't match "desktop", etc.
_HR_KW = [r"\bteammate\b", "team mate", "coworker", "co-worker", r"\bcolleague",
          "harass", r"\bbully", "bullying", "discriminat", "misconduct",
          "unprofessional", "grievance", "hostile work", "my coworker"]
_FACILITIES_KW = [r"air[- ]?condition\w*", r"\ba/c\b", r"\bac unit\b", "heating",
                  "too hot", "too cold", "room temperature", r"\bdesk\b", r"\bchair\b",
                  r"\bseat\b", r"\bseating\b", "seat reassignment", "lighting",
                  "light bulb", "washroom", "restroom", r"\btoilet\b", "parking",
                  "elevator", "water cooler", r"\bpantry\b", "cafeteria", "furniture",
                  r"\bbuilding\b"]


def _nonit_hint(text: str):
    """Return 'HR' / 'Facilities' if obvious non-IT keywords are present, else None."""
    t = text.lower()
    if any(re.search(p, t) for p in _HR_KW):
        return "HR"
    if any(re.search(p, t) for p in _FACILITIES_KW):
        return "Facilities"
    return None


# Physical-damage / "can't be fixed with software steps" signals → needs a human
# (repair or replacement), so the issue must NOT be auto-resolved with instructions.
_NEEDS_HUMAN_PLAIN = [
    "cracked", "shattered", "smashed", "dropped it", "dropped my", "physically damaged",
    "physical damage", "wont turn on", "wont power on", "not turning on", "not powering on",
    "wont switch on", "water damage", "liquid damage", "spilled", "broken screen",
    "screen is cracked", "screen cracked", "screen is broken", "wont charge", "not charging",
    "overheating", "burning smell", "swollen battery", "wont boot", "no display",
    "black screen", "needs replacement", "needs a replacement", "hardware failure",
]

# Signals that many people / the business are affected (keeps real outages high-priority).
_MULTI_USER = [
    "everyone", "all users", "whole team", "entire team", "multiple", "nobody can",
    "no one can", "production", "entire office", "company-wide", "several people",
    "all of us", "the team", "customers cannot", "customers can't",
]


def _needs_human_hint(text: str) -> bool:
    """Physical damage / dead device → needs a person, not auto software steps."""
    t = text.lower().replace("'", "").replace("’", "")
    if re.search(r"\bdead\b", t):
        return True
    return any(p in t for p in _NEEDS_HUMAN_PLAIN)


def _is_multi_user(text: str) -> bool:
    t = text.lower().replace("'", "").replace("’", "")
    return any(p.replace("'", "") in t for p in _MULTI_USER)


class IntentDetector:
    def __init__(self):
        pass

    # ── Rule-based pre-filter ────────────────────────────────────────────────
    def _rule_based_check(self, message: str) -> str:
        """Return 'greeting', 'vague', 'ticket', or 'ambiguous'."""
        if _is_smalltalk(message):
            return "greeting"
        if _has_strong_problem(message.lower()):
            return "ticket"
        if _is_vague(message):
            return "vague"
        # Longer messages that clearly describe something → ticket
        if len(message.split()) >= 12:
            return "ticket"
        return "ambiguous"

    # ── Main entry point ─────────────────────────────────────────────────────
    async def detect(self, message: str, history: List[ChatMessage]) -> IntentResult:
        rule = self._rule_based_check(message)
        logger.info(f"Intent rule pre-filter: {rule}")

        # Confident rule-based verdicts skip the LLM for speed.
        if rule == "greeting":
            reply = await self._compose_reply("greeting", message, history)
            return IntentResult(is_ticket=False, intent=IntentType.greeting,
                                confidence=0.97, reply=reply)
        if rule == "vague":
            topic = _found_topic(message.lower())
            # Template reply (no extra LLM call); the clarifying questions come
            # from analyze_problem() in the chat flow.
            return IntentResult(is_ticket=False, intent=IntentType.vague,
                                confidence=0.9, reply=_vague_reply(topic),
                                extracted={"title": _title_from(message), "topic": topic})

        # 'ticket' or 'ambiguous' → let the LLM decide + extract (if available).
        if settings.ollama_enabled:
            try:
                return await self._llm_detect(message, history)
            except Exception as e:
                logger.warning(f"Local LLM intent unavailable ({e}) — using rule-based fallback")

        return self._rule_intent(message, rule)

    # ── Rule-based fallback intent (LLM offline) ─────────────────────────────
    def _rule_intent(self, message: str, rule: str) -> IntentResult:
        if rule == "ambiguous":
            # Treat a short, non-problem, non-topic message as a vague request.
            topic = _found_topic(message.lower())
            return IntentResult(
                is_ticket=False, intent=IntentType.vague, confidence=0.55,
                reply=_vague_reply(topic) if topic else
                ("Could you describe the IT issue you're facing — what's happening, any "
                 "error message, and when it started?"),
                extracted={"title": _title_from(message)},
            )
        # ticket
        return IntentResult(
            is_ticket=True, intent=IntentType.ticket, confidence=0.7,
            needs_detail=len(message.split()) < 12,
            extracted={"title": _title_from(message),
                       "priority": _rule_extract_priority(message)},
        )

    # ── LLM-backed reply composer (greeting / vague) ─────────────────────────
    async def _compose_reply(self, kind: str, message: str,
                             history: List[ChatMessage], topic: str = "") -> str:
        fallback = _greeting_reply(message) if kind == "greeting" else _vague_reply(topic)
        if not settings.ollama_enabled:
            return fallback
        history_text = "\n".join(f"{m.role}: {m.content}" for m in history[-4:])
        if kind == "greeting":
            prompt = (
                "You are a friendly IT support assistant chatbot. The user sent a "
                "greeting or small-talk message (not a support request). Reply in ONE "
                "short, warm sentence and invite them to describe any IT issue.\n"
                f"{_LANG_RULE}\n\n"
                f"Recent history:\n{history_text}\n\nUser: {message}\n\nReply:"
            )
        else:
            prompt = (
                "You are an IT support assistant. The user mentioned a topic but did not "
                f"describe an actual problem (topic: '{topic or 'IT'}'). Ask them, in ONE "
                "or two short sentences, to explain the issue — what's happening, any error "
                "message, and when it started. Be specific to the topic.\n\n"
                f"User: {message}\n\nReply:"
            )
        try:
            text = await ollama_generate(prompt, temperature=0.3, max_tokens=120)
            return text.strip() or fallback
        except Exception as e:
            logger.warning(f"LLM reply compose failed ({e}); using fallback")
            return fallback

    # ── LLM intent classification + field extraction ─────────────────────────
    async def _llm_detect(self, message: str, history: List[ChatMessage]) -> IntentResult:
        history_text = "\n".join(f"{m.role}: {m.content}" for m in history[-6:])
        prompt = f"""You are the intake brain of an IT support assistant.
Classify the user's latest message into EXACTLY ONE intent:

- "greeting": small talk, greeting, thanks, or goodbye. Not a request for help.
- "vague": mentions an IT topic/keyword (e.g. VPN, laptop, payment, email) but does
   NOT describe an actual problem. Too little to act on.
- "ticket": describes a real IT problem or request (even briefly).

If intent is "greeting" or "vague", write a short, friendly "reply" for the user
(for "vague", ask them to explain the issue: what's happening, any error, when it started).
If intent is "ticket", set "reply" to null and extract a short title + priority, and set
"needs_detail" to true if the description is too thin to resolve confidently.

Respond ONLY with valid JSON, no markdown:
{{
  "intent": "greeting" | "vague" | "ticket",
  "reply": "<string for greeting/vague, else null>",
  "title": "<short title if ticket, else null>",
  "priority": "low" | "medium" | "high" | "critical" | null,
  "needs_detail": true | false
}}

Conversation history:
{history_text}

Latest message: {message}

JSON:"""
        raw = await ollama_generate(prompt, temperature=0.1, max_tokens=300, json_mode=True)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(raw)

        intent_str = str(data.get("intent", "ticket")).lower()
        if intent_str not in ("greeting", "vague", "ticket"):
            intent_str = "ticket"
        intent = IntentType(intent_str)

        if intent in (IntentType.greeting, IntentType.vague):
            reply = data.get("reply") or (
                _greeting_reply(message) if intent == IntentType.greeting
                else _vague_reply(_found_topic(message.lower()))
            )
            return IntentResult(
                is_ticket=False, intent=intent, confidence=0.9, reply=reply,
                extracted={"title": data.get("title") or _title_from(message)},
            )

        # ticket
        priority = data.get("priority")
        if priority not in ("low", "medium", "high", "critical"):
            priority = _rule_extract_priority(message)
        return IntentResult(
            is_ticket=True, intent=IntentType.ticket, confidence=0.85,
            needs_detail=bool(data.get("needs_detail", True)),
            extracted={"title": data.get("title") or _title_from(message),
                       "priority": priority},
        )

    # ── First-turn intake questions (always asked) ───────────────────────────
    async def intake_questions(self, context: str, message: str) -> dict:
        """
        Produce tailored clarifying questions for the FIRST intake turn — always
        returns questions so every ticket gets a "describe your issue" box, even
        when the first message already looks detailed.

        Returns: {"questions": [str], "title": str, "priority": str}
        """
        topic = _found_topic(f"{context} {message}".lower())
        fallback = {
            "questions": _generic_questions(topic),
            "title": _title_from(context or message),
            "priority": _rule_extract_priority(message),
            "frustrated": False,
            "language": "English",
        }
        if not settings.ollama_enabled:
            return fallback
        prompt = f"""You are an IT support agent intaking a new issue. Based on the user's
message, ask 3 to 4 SPECIFIC questions that will help you fully understand and resolve
THIS issue. Tailor them to the problem — never generic. If the user already stated
something, ask to confirm details or fill gaps (affected device/app/account, exact
error, when it started, what they've tried, how many people affected).
Also detect if the user sounds frustrated, angry, or stressed.
{_LANG_RULE}

User's message: {message}
Topic: {topic or "general IT"}

Respond ONLY with valid JSON, no markdown:
{{
  "questions": ["...", "...", "..."],
  "title": "<short ticket title>",
  "priority": "low" | "medium" | "high" | "critical",
  "frustrated": true | false,
  "language": "<the language the user is writing in, e.g. English, Spanish, Hindi>"
}}

JSON:"""
        try:
            raw = await ollama_generate(prompt, temperature=0.3, max_tokens=350, json_mode=True)
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = json.loads(raw)
            questions = [str(q).strip() for q in (data.get("questions") or []) if str(q).strip()]
            if not questions:
                questions = _generic_questions(topic)
            priority = data.get("priority")
            if priority not in ("low", "medium", "high", "critical"):
                priority = _rule_extract_priority(message)
            title = (data.get("title") or _title_from(context or message)).strip()
            return {"questions": questions[:4], "title": title, "priority": priority,
                    "frustrated": bool(data.get("frustrated", False)),
                    "language": (data.get("language") or "English").strip()}
        except Exception as e:
            logger.warning(f"intake_questions LLM failed ({e}); using generic questions")
            return fallback

    # ── Problem analysis (clarify loop + priority) ───────────────────────────
    async def analyze_problem(self, context: str, collected: str) -> dict:
        """
        Decide whether we understand the user's problem well enough to act.

        Returns a dict:
          {
            "understood": bool,       # enough detail to classify + resolve?
            "questions": [str],       # tailored follow-ups when not understood
            "priority": str,          # low | medium | high | critical
            "title": str,             # concise ticket title
          }
        Falls back to rule-based analysis when the LLM is unavailable.
        """
        full = f"{context}\n{collected}".strip()
        if not settings.ollama_enabled:
            return self._rule_analyze(context, collected)
        prompt = f"""You are an IT support intake specialist. Decide if you understand the
issue well enough to attempt a solution. You can proceed once you know the SYMPTOM
(what's going wrong) and the AFFECTED THING (app/device/account/service). Lean towards
proceeding — only ask for more if the problem is genuinely unclear or could be several
very different issues. A clear one-line description of a problem is usually enough.

Topic / first message: {context or "(none)"}
Everything the user has told you so far:
{collected or "(nothing yet)"}

If it is genuinely NOT enough, write 2-4 SPECIFIC clarifying questions tailored to THIS
problem (never generic). If it IS enough, set "understood" true and return an empty
questions list.
Estimate the priority from IMPACT and URGENCY only:
  critical = security breach / outage / many users affected / production down
  high     = blocks THIS user's ability to work, time-sensitive, locked out
  medium   = a normal single-user issue, including a broken or damaged PERSONAL
             device (phone/laptop) that needs repair but isn't stopping their work
  low      = minor / cosmetic / no rush
Rules: how long a problem has merely PERSISTED does NOT raise priority. Do NOT
rate something high just because words like "broken", "dead" or "won't turn on"
appear — a single damaged personal device is usually MEDIUM. Only use high/critical
when work is actually blocked or many people are affected.

Also set "needs_human": true if resolving this realistically needs a PERSON —
physical repair, hardware replacement, or on-site help (e.g. a cracked/dropped
device, one that won't power on, water damage, dead hardware). In those cases the
user cannot fix it by following software steps.

Also decide whether this is genuinely an IT / technical support issue. If it is
NOT — an HR / people matter (behaviour, conduct, complaints), a facilities /
workplace request (seat/desk/office), or anything not IT — set "it_issue" false
and "category_hint" to "HR", "Facilities", or "Other".
Also detect if the user sounds frustrated, angry, or stressed.
{_LANG_RULE}

Respond ONLY with valid JSON, no markdown:
{{
  "understood": true | false,
  "questions": ["...", "..."],
  "priority": "low" | "medium" | "high" | "critical",
  "title": "<short ticket title>",
  "frustrated": true | false,
  "needs_human": true | false,
  "it_issue": true | false,
  "category_hint": "HR" | "Facilities" | "Other" | null,
  "language": "<the language the user is writing in, e.g. English, Spanish, Hindi>"
}}

JSON:"""
        try:
            raw = await ollama_generate(prompt, temperature=0.1, max_tokens=400, json_mode=True)
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = json.loads(raw)
            understood = bool(data.get("understood", False))
            questions = [str(q).strip() for q in (data.get("questions") or []) if str(q).strip()]
            priority = data.get("priority")
            if priority not in ("low", "medium", "high", "critical"):
                priority = _rule_extract_priority(full)
            title = (data.get("title") or _title_from(context or collected)).strip()
            # Pragmatic override: don't over-question. If the user has clearly
            # described a problem with reasonable detail, proceed even if the
            # model wanted more.
            if not understood and _has_strong_problem(full.lower()) \
                    and len(collected.split()) >= 12:
                understood, questions = True, []
            # Safety: if not understood but the model gave no questions, fall back.
            if not understood and not questions:
                questions = _generic_questions(_found_topic(full.lower()))
            hint = data.get("category_hint")
            if hint not in ("HR", "Facilities", "Other"):
                hint = None
            it_issue = bool(data.get("it_issue", True))
            # Keyword backstop: obvious HR/facilities terms override an LLM that
            # mislabelled the request as an IT issue.
            kw = _nonit_hint(full)
            if kw:
                it_issue, hint = False, kw
            # Physical-damage backstop: a dead/broken device needs a human.
            needs_human = bool(data.get("needs_human", False)) or _needs_human_hint(full)
            # A physically damaged DEVICE is still an IT/asset issue (Hardware /
            # Mobile Device), not "Other" — keep it in IT so it's categorised right
            # (it'll be routed to a human via needs_human, not auto-resolved).
            if needs_human and kw is None:
                it_issue = True
            return {"understood": understood, "questions": questions[:4],
                    "priority": priority, "title": title,
                    "frustrated": bool(data.get("frustrated", False)),
                    "needs_human": needs_human,
                    "multi_user": _is_multi_user(full),
                    "it_issue": it_issue,
                    "category_hint": hint,
                    "language": (data.get("language") or "English").strip()}
        except Exception as e:
            logger.warning(f"analyze_problem LLM failed ({e}); using rule-based analysis")
            return self._rule_analyze(context, collected)

    def _rule_analyze(self, context: str, collected: str) -> dict:
        full = f"{context} {collected}".strip()
        has_problem = _has_strong_problem(full.lower())
        enough_words = len(collected.split()) >= 10
        understood = has_problem and enough_words
        return {
            "understood": understood,
            "questions": [] if understood else _generic_questions(_found_topic(full.lower())),
            "priority": _rule_extract_priority(full),
            "title": _title_from(context or collected),
            "frustrated": False,
            "needs_human": _needs_human_hint(full),
            "multi_user": _is_multi_user(full),
            "it_issue": _nonit_hint(full) is None,   # keyword backstop offline too
            "category_hint": _nonit_hint(full),
            "language": "English",
        }

    async def close(self):
        # The shared Ollama HTTP client is closed once in main.py's shutdown.
        return
