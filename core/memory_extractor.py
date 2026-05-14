"""
core/memory_extractor.py — Structured memory extraction from correction signals.

Called AFTER the trigger detector confirms a correction signal (~5-10% of messages).
Produces a structured ExtractionResult that feeds into:
  → store_utility scorer  (should this be saved?)
  → scope_resolver        (global / project / conversation)
  → corrections table     (the verified fact for prompt injection)
  → audit_log table       (the scoring event for Look Under the Hood)

Two-tier extraction:
  Tier 1: Gemini Flash-Lite (or GPT-4o mini fallback) — structured JSON prompt.
           Best quality. Costs ~$0.0001 per correction extracted.
  Tier 2: Rule-based fallback — pattern matching, no API call.
           Used when no judge model is connected or Tier 1 fails.

Input:  user_message, original_query, ai_response, model_id, active_project
Output: ExtractionResult (typed dataclass)
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ── Correction types ──────────────────────────────────────────────────────────

CORRECTION_TYPES = {
    "factual_correction":      "The AI stated something factually wrong",
    "persistent_instruction":  "The user is setting a permanent rule or preference",
    "project_decision":        "A decision specific to this project",
    "preference":              "The user's style or format preference",
    "failure_pattern":         "The AI keeps making the same kind of mistake",
}

# ── Decay classes ─────────────────────────────────────────────────────────────

DECAY_CLASSES = {
    "A": "Permanent — mathematical facts, fundamental concepts, stable API contracts",
    "B": "10 years — framework versions, language features, architectural patterns",
    "C": "3 years  — library APIs, tooling, configuration formats",
    "D": "6 months — current events, pricing, model names, fast-moving domains",
}

# ── Domain labels matching the field classifier ───────────────────────────────

KNOWN_DOMAINS = frozenset({
    "software_engineering", "mathematics", "science", "legal",
    "medical", "finance", "general", "education",
})

# ── Prompt template ───────────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """You are extracting a structured memory from a user correction in an AI assistant app.

CONTEXT:
Original query: {original_query}
AI response (first 400 chars): {ai_response_preview}
User correction: {user_message}
Active project: {active_project}

The user has flagged the AI's response as wrong or has issued a persistent instruction.
Extract the structured correction. Respond ONLY with valid JSON — no markdown, no explanation.

{{
  "type": "factual_correction" | "persistent_instruction" | "project_decision" | "preference" | "failure_pattern",
  "scope": "global" | "project" | "conversation",
  "corrective_instruction": "The correct information or rule to inject into future prompts (1-2 sentences, direct)",
  "reason": "Brief reason the AI was wrong or the rule being set (1 sentence)",
  "canonical_query": "snake_case_topic_identifier_max_8_words",
  "domain": "software_engineering" | "mathematics" | "science" | "legal" | "medical" | "finance" | "general" | "education",
  "confidence": 0.0,
  "decay_class": "A" | "B" | "C" | "D"
}}

Rules:
  scope=global if the instruction applies everywhere (style preferences, always/never rules)
  scope=project if it's specific to the current project ("{active_project}")
  scope=conversation if it's only relevant now (transient clarification)
  decay_class=A for permanent facts and stable rules
  decay_class=B for things that change over years (framework versions)
  decay_class=C for things that change in 1-3 years (library APIs)
  decay_class=D for fast-moving info (pricing, model names, current events)
  confidence=0.95 for explicit "X is wrong, it should be Y" corrections
  confidence=0.80 for preference statements ("I prefer X")
  confidence=0.70 for ambiguous or implicit corrections"""

# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ExtractionResult:
    """Structured memory extracted from a user correction."""

    extraction_id:          str
    type:                   str    # factual_correction | persistent_instruction | project_decision | preference | failure_pattern
    scope:                  str    # global | project | conversation
    corrective_instruction: str    # injected into future prompts
    reason:                 str    # why the model score changes
    canonical_query:        str    # snake_case normalized topic key
    domain:                 str    # software_engineering | mathematics | etc.
    confidence:             float  # 0.0 – 1.0
    decay_class:            str    # A | B | C | D
    model_id:               str    # which model was wrong
    query_preview:          str    # first 60 chars of original query
    extracted_via:          str    # "llm" | "rules"
    created_at:             float  = field(default_factory=time.time)

    def to_correction_record(self, active_project: str | None = None) -> dict:
        """
        Convert to the canonical correction event record for the corrections table.
        See roadmap: Correction event record — canonical schema.
        """
        return {
            "correction_id":          self.extraction_id,
            "model_id":               self.model_id,
            "score_delta":            self._score_delta(),
            "reason":                 self.reason,
            "corrective_instruction": self.corrective_instruction,
            "scope":                  self.scope,
            "domain":                 self.domain,
            "canonical_query":        self.canonical_query,
            "query_preview":          self.query_preview,
            "confidence":             self.confidence,
            "decay_class":            self.decay_class,
            "extracted_via":          self.extracted_via,
            "active_project":         active_project,
            "created_at":             self.created_at,
        }

    def to_audit_event(self, score_before: int, score_after: int) -> dict:
        """Convert to audit_log entry for Look Under the Hood graph."""
        return {
            "audit_id":           str(uuid.uuid4()),
            "model_id":           self.model_id,
            "event_type":         "correction_stored",
            "score_before":       score_before,
            "score_after":        score_after,
            "verdict":            "incorrect" if self.type == "factual_correction" else "instruction",
            "correction_stored":  True,
            "query_preview":      self.query_preview,
            "correction_type":    self.type,
            "created_at":         self.created_at,
        }

    def _score_delta(self) -> int:
        """Calculate reliability score delta based on correction type and confidence."""
        if self.type == "factual_correction":
            # Factual errors get the biggest penalty
            return -round(self.confidence * 15)
        elif self.type == "failure_pattern":
            # Repeated pattern errors get moderate penalty
            return -round(self.confidence * 10)
        elif self.type in ("persistent_instruction", "project_decision"):
            # Instructions and decisions don't penalize (model wasn't wrong, just uninformed)
            return 0
        elif self.type == "preference":
            return 0
        return -round(self.confidence * 5)


# ── Extractor ─────────────────────────────────────────────────────────────────

class MemoryExtractor:
    """
    Extracts structured ExtractionResult from a correction signal context.

    Two-tier strategy:
      Tier 1: Cloud LLM (Gemini Flash-Lite preferred, GPT-4o mini fallback)
      Tier 2: Rule-based extraction (no API call, lower quality)
    """

    def __init__(self, backends: dict | None = None):
        """
        Args:
            backends: dict of model_id → backend instance (from VeritasRouter).
                      If None or empty, falls back to rule-based extraction only.
        """
        self._backends = backends or {}

    # ── Public interface ──────────────────────────────────────────────────────

    async def extract(
        self,
        user_message: str,
        original_query: str,
        ai_response: str,
        model_id: str,
        active_project: str | None = None,
    ) -> ExtractionResult | None:
        """
        Extract a structured memory from a correction signal.

        Args:
            user_message:    The user's correction message.
            original_query:  The original query that produced the wrong answer.
            ai_response:     The AI's response being corrected (may be truncated).
            model_id:        Which model gave the wrong answer.
            active_project:  Name of the active project (for scope resolution).

        Returns:
            ExtractionResult if extraction succeeded, None if the message
            turned out not to be a meaningful correction after all.
        """
        if not user_message or not user_message.strip():
            return None

        query_preview = (original_query[:60] + "…") if len(original_query) > 60 else original_query

        # Try Tier 1: LLM extraction
        judge_model = self._pick_judge(exclude=model_id)
        if judge_model:
            result = await self._extract_via_llm(
                user_message, original_query, ai_response,
                model_id, active_project, query_preview, judge_model,
            )
            if result:
                return result
            log.warning("LLM extraction failed — falling back to rule-based")

        # Tier 2: Rule-based extraction
        return self._extract_via_rules(
            user_message, original_query, model_id, active_project, query_preview
        )

    # ── Tier 1: LLM extraction ────────────────────────────────────────────────

    async def _extract_via_llm(
        self,
        user_message: str,
        original_query: str,
        ai_response: str,
        model_id: str,
        active_project: str | None,
        query_preview: str,
        judge_model: str,
    ) -> ExtractionResult | None:
        """Call a cheap judge model with a structured extraction prompt."""
        from core.config import SUPPORTED_MODELS

        prompt = _EXTRACTION_PROMPT.format(
            original_query=original_query[:300],
            ai_response_preview=ai_response[:400],
            user_message=user_message[:500],
            active_project=active_project or "not specified",
        )

        backend = self._backends.get(judge_model)
        if not backend:
            return None

        try:
            response = await backend.complete({
                "model": judge_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 400,
            })
            raw_text = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return self._parse_llm_response(
                raw_text, model_id, query_preview, extracted_via=f"llm:{judge_model}"
            )
        except Exception as e:
            log.warning("LLM extraction error (%s): %s", judge_model, e)
            return None

    def _parse_llm_response(
        self,
        raw_text: str,
        model_id: str,
        query_preview: str,
        extracted_via: str,
    ) -> ExtractionResult | None:
        """Parse the JSON response from the judge model."""
        # Strip markdown fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.warning("Could not parse LLM extraction JSON: %r", text[:200])
            return None

        # Validate required fields
        required = {"type", "scope", "corrective_instruction", "reason",
                    "canonical_query", "domain", "confidence", "decay_class"}
        if not required.issubset(data.keys()):
            missing = required - data.keys()
            log.warning("LLM extraction missing fields: %s", missing)
            return None

        # Sanitize and clamp values
        corr_type  = data["type"]     if data["type"]     in CORRECTION_TYPES else "factual_correction"
        scope      = data["scope"]    if data["scope"]     in {"global","project","conversation"} else "project"
        domain     = data["domain"]   if data["domain"]    in KNOWN_DOMAINS    else "general"
        decay      = data["decay_class"] if data["decay_class"] in "ABCD"      else "A"
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.8))))

        # Sanitize canonical_query: lowercase, underscores, max 60 chars
        canonical = re.sub(r"[^a-z0-9_]", "_", data["canonical_query"].lower())[:60].strip("_")

        if not data["corrective_instruction"] or not data["reason"]:
            return None

        return ExtractionResult(
            extraction_id=str(uuid.uuid4()),
            type=corr_type,
            scope=scope,
            corrective_instruction=data["corrective_instruction"][:500],
            reason=data["reason"][:200],
            canonical_query=canonical,
            domain=domain,
            confidence=confidence,
            decay_class=decay,
            model_id=model_id,
            query_preview=query_preview,
            extracted_via=extracted_via,
        )

    # ── Tier 2: Rule-based extraction ─────────────────────────────────────────

    def _extract_via_rules(
        self,
        user_message: str,
        original_query: str,
        model_id: str,
        active_project: str | None,
        query_preview: str,
    ) -> ExtractionResult | None:
        """
        Pattern-based extraction when no LLM is available.
        Lower quality but zero cost and zero latency.
        """
        msg = user_message.strip()
        msg_lower = msg.lower()

        # ── Determine type ────────────────────────────────────────────────────
        if re.search(r"\b(going forward|from now on|henceforth|always |never )\b", msg_lower):
            corr_type = "persistent_instruction"
        elif re.search(r"\b(we decided|we are using|we chose|we're going with)\b", msg_lower):
            corr_type = "project_decision"
        elif re.search(r"\b(i prefer|i want|i like|i always)\b", msg_lower):
            corr_type = "preference"
        elif re.search(r"\b(you keep|every time|again|third time|keep getting)\b", msg_lower):
            corr_type = "failure_pattern"
        else:
            corr_type = "factual_correction"

        # ── Determine scope ───────────────────────────────────────────────────
        if corr_type in ("project_decision",) or re.search(
            r"\b(this project|for this|in this (repo|codebase|app))\b", msg_lower
        ):
            scope = "project"
        elif corr_type in ("persistent_instruction", "preference"):
            scope = "global"
        else:
            scope = "project" if active_project else "global"

        # ── Build corrective instruction ──────────────────────────────────────
        # Use the user's message directly — it IS the correction
        corrective_instruction = msg[:500]

        # ── Build reason ──────────────────────────────────────────────────────
        reason = f"User corrected the response: {msg[:100]}"

        # ── Canonical query from original query ───────────────────────────────
        canonical = re.sub(r"[^a-z0-9 ]", "", original_query.lower())
        canonical = re.sub(r"\s+", "_", canonical.strip())[:60].strip("_")
        if not canonical:
            canonical = "general_correction"

        # ── Domain heuristic ──────────────────────────────────────────────────
        domain = self._guess_domain(original_query + " " + msg)

        # ── Confidence based on type ──────────────────────────────────────────
        confidence_map = {
            "factual_correction":     0.85,
            "failure_pattern":        0.80,
            "project_decision":       0.90,
            "persistent_instruction": 0.85,
            "preference":             0.75,
        }
        confidence = confidence_map.get(corr_type, 0.80)

        # ── Decay class heuristic ─────────────────────────────────────────────
        decay_map = {
            "factual_correction":     "A",
            "project_decision":       "A",
            "persistent_instruction": "A",
            "preference":             "A",
            "failure_pattern":        "B",
        }
        decay = decay_map.get(corr_type, "A")

        return ExtractionResult(
            extraction_id=str(uuid.uuid4()),
            type=corr_type,
            scope=scope,
            corrective_instruction=corrective_instruction,
            reason=reason,
            canonical_query=canonical,
            domain=domain,
            confidence=confidence,
            decay_class=decay,
            model_id=model_id,
            query_preview=query_preview,
            extracted_via="rules",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _pick_judge(self, exclude: str) -> str | None:
        """
        Pick the cheapest available judge model for extraction.
        Preference order: Gemini Flash-Lite, GPT-4o mini, Claude Haiku, any other.
        """
        preferred = [
            "gemini-2.0-flash",
            "gpt-4o-mini",
            "claude-haiku-4-5-20251001",
        ]
        for model_id in preferred:
            if model_id in self._backends and model_id != exclude:
                return model_id
        # Any loaded model except the one being penalized
        for model_id in self._backends:
            if model_id != exclude:
                return model_id
        return None

    def _guess_domain(self, text: str) -> str:
        """Simple keyword-based domain guessing for rule-based fallback."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["code", "function", "class", "api", "sql", "python", "async", "database", "postgres", "sqlite"]):
            return "software_engineering"
        if any(w in text_lower for w in ["integral", "derivative", "proof", "theorem", "equation", "algorithm", "complexity"]):
            return "mathematics"
        if any(w in text_lower for w in ["law", "legal", "contract", "court", "jurisdiction"]):
            return "legal"
        if any(w in text_lower for w in ["diagnosis", "symptom", "treatment", "medical", "drug", "dose"]):
            return "medical"
        if any(w in text_lower for w in ["stock", "investment", "tax", "finance", "revenue", "budget"]):
            return "finance"
        return "general"
