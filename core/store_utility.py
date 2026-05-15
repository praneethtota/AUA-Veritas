"""
core/store_utility.py — Store utility scorer.

Scores whether a candidate memory (ExtractionResult) is worth saving.
Called after memory_extractor produces a result and before scope_resolver
decides what to do with it.

Formula (from roadmap §"Store utility scoring"):
  store_utility = 0.30 × correction_strength
                + 0.25 × future_reuse_probability
                + 0.20 × project_relevance
                + 0.15 × user_explicitness
                + 0.10 × severity
                − 0.20 × ambiguity
                − 0.20 × sensitivity_risk

Thresholds:
  ≥ 0.85  → auto-save (fires background hook, shows undo toast)
  0.60–0.85 → passive review card (user sees it, can approve/edit/ignore)
  < 0.60  → discard silently

All sub-scores are 0.0–1.0. The final score is clamped to [0.0, 1.0].
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory_extractor import ExtractionResult

log = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

THRESHOLD_AUTO_SAVE    = 0.85   # store silently, show undo toast
THRESHOLD_REVIEW_CARD  = 0.60   # show passive review card
# below 0.60 → discard silently


class StoreDecision(str, Enum):
    AUTO_SAVE   = "auto_save"    # ≥ 0.85: store, show undo toast
    REVIEW_CARD = "review_card"  # 0.60–0.85: show passive review card
    DISCARD     = "discard"      # < 0.60: ignore silently


@dataclass
class StoreUtilityResult:
    score:       float
    decision:    StoreDecision
    breakdown:   dict[str, float]   # individual sub-scores for debugging

    @property
    def should_store(self) -> bool:
        return self.decision in (StoreDecision.AUTO_SAVE, StoreDecision.REVIEW_CARD)

    @property
    def is_auto(self) -> bool:
        return self.decision == StoreDecision.AUTO_SAVE


# ── Keyword sets for sub-score estimation ─────────────────────────────────────

_STRONG_CORRECTION_PHRASES = re.compile(
    r"\b(wrong|incorrect|error|mistake|not right|backwards|confused|"
    r"misunderstood|keep (getting|doing|saying)|every time|again)\b",
    re.IGNORECASE,
)

_PERSISTENT_PHRASES = re.compile(
    r"\b(always|never|going forward|from now on|every|all|permanently|"
    r"rule|standard|prefer|convention)\b",
    re.IGNORECASE,
)

_EXPLICIT_PHRASES = re.compile(
    r"\b(specifically|explicitly|must|should|required|important|critical|"
    r"please remember|don.t forget|make sure|ensure)\b",
    re.IGNORECASE,
)

_AMBIGUOUS_PHRASES = re.compile(
    r"\b(maybe|perhaps|might|could|sometimes|it depends|not sure|"
    r"i think|possibly|probably|kind of|sort of)\b",
    re.IGNORECASE,
)

_SENSITIVE_PHRASES = re.compile(
    r"\b(password|secret|token|key|credential|private|personal|ssn|"
    r"social security|credit card|bank|salary|medical|health|diagnosis)\b",
    re.IGNORECASE,
)

_HIGH_STAKES_DOMAINS = frozenset({"legal", "medical", "finance"})


# ── Scorer ────────────────────────────────────────────────────────────────────

class StoreUtilityScorer:
    """
    Scores whether an ExtractionResult is worth storing in the corrections table.

    All sub-scores are heuristic estimates based on the correction content and
    extraction metadata. The formula approximates what Gemini Flash-Lite would
    judge if we called it on every candidate — without the extra API call.
    """

    def score(
        self,
        extraction: "ExtractionResult",
        user_message: str = "",
        original_query: str = "",
        active_project: str | None = None,
    ) -> StoreUtilityResult:
        """
        Score a candidate memory.

        Args:
            extraction:      The ExtractionResult to evaluate.
            user_message:    Raw user correction message (for signal detection).
            original_query:  Original query that produced the wrong answer.
            active_project:  Active project name (increases project_relevance).

        Returns:
            StoreUtilityResult with score, decision, and sub-score breakdown.
        """
        text = f"{user_message} {extraction.corrective_instruction} {original_query}"

        breakdown = {
            "correction_strength":    self._correction_strength(extraction, user_message),
            "future_reuse":           self._future_reuse(extraction, user_message),
            "project_relevance":      self._project_relevance(extraction, active_project),
            "user_explicitness":      self._user_explicitness(user_message),
            "severity":               self._severity(extraction),
            "ambiguity":              self._ambiguity(text),
            "sensitivity_risk":       self._sensitivity_risk(text),
        }

        raw = (
              0.30 * breakdown["correction_strength"]
            + 0.25 * breakdown["future_reuse"]
            + 0.20 * breakdown["project_relevance"]
            + 0.15 * breakdown["user_explicitness"]
            + 0.10 * breakdown["severity"]
            - 0.20 * breakdown["ambiguity"]
            - 0.20 * breakdown["sensitivity_risk"]
        )
        score = round(max(0.0, min(1.0, raw)), 4)

        if score >= THRESHOLD_AUTO_SAVE:
            decision = StoreDecision.AUTO_SAVE
        elif score >= THRESHOLD_REVIEW_CARD:
            decision = StoreDecision.REVIEW_CARD
        else:
            decision = StoreDecision.DISCARD

        log.debug(
            "store_utility=%.3f (%s) for %s/%s",
            score, decision.value,
            extraction.domain, extraction.canonical_query[:40],
        )

        return StoreUtilityResult(
            score=score,
            decision=decision,
            breakdown=breakdown,
        )

    # ── Sub-scores ────────────────────────────────────────────────────────────

    def _correction_strength(self, extraction: "ExtractionResult", text: str) -> float:
        """How strong/clear is the correction signal? 0.0–1.0"""
        base = extraction.confidence  # already 0.0–1.0

        # Boost for explicit error language
        if _STRONG_CORRECTION_PHRASES.search(text):
            base = min(1.0, base + 0.15)

        # Type-based adjustment
        type_boosts = {
            "factual_correction":     0.0,
            "failure_pattern":        0.10,   # repeated → stronger signal
            "project_decision":       0.05,
            "persistent_instruction": 0.05,
            "preference":            -0.10,   # preferences are weaker signals
        }
        base = min(1.0, max(0.0, base + type_boosts.get(extraction.type, 0.0)))
        return round(base, 4)

    def _future_reuse(self, extraction: "ExtractionResult", text: str) -> float:
        """How likely is this correction to be relevant in future queries? 0.0–1.0"""
        score = 0.5  # neutral baseline

        # Persistent language → high reuse
        if _PERSISTENT_PHRASES.search(text):
            score = min(1.0, score + 0.35)

        # Decay class affects expected reuse
        decay_scores = {"A": 0.20, "B": 0.10, "C": 0.0, "D": -0.15}
        score += decay_scores.get(extraction.decay_class, 0.0)

        # Scope
        if extraction.scope == "global":
            score = min(1.0, score + 0.15)
        elif extraction.scope == "conversation":
            score = max(0.0, score - 0.30)

        return round(max(0.0, min(1.0, score)), 4)

    def _project_relevance(
        self, extraction: "ExtractionResult", active_project: str | None
    ) -> float:
        """How relevant is this to the active project context? 0.0–1.0"""
        if extraction.scope == "project" and active_project:
            return 0.90
        if extraction.scope == "global":
            return 0.70
        if extraction.scope == "conversation":
            return 0.30
        return 0.50

    def _user_explicitness(self, text: str) -> float:
        """How explicitly did the user state the correction? 0.0–1.0"""
        base = 0.50
        if _EXPLICIT_PHRASES.search(text):
            base = min(1.0, base + 0.35)
        # Short, direct corrections score higher (no hedging)
        word_count = len(text.split())
        if word_count <= 15:
            base = min(1.0, base + 0.10)
        elif word_count > 60:
            base = max(0.0, base - 0.10)
        return round(base, 4)

    def _severity(self, extraction: "ExtractionResult") -> float:
        """How severe is the error being corrected? 0.0–1.0"""
        type_severity = {
            "factual_correction":     0.80,
            "failure_pattern":        0.90,   # repeated errors are severe
            "project_decision":       0.85,
            "persistent_instruction": 0.70,
            "preference":             0.40,
        }
        base = type_severity.get(extraction.type, 0.60)

        # High-stakes domains are more severe
        if extraction.domain in _HIGH_STAKES_DOMAINS:
            base = min(1.0, base + 0.10)

        return round(base, 4)

    def _ambiguity(self, text: str) -> float:
        """How ambiguous or hedged is the correction? 0.0–1.0 (higher = more ambiguous)"""
        if not _AMBIGUOUS_PHRASES.search(text):
            return 0.0
        # Count hedge words — more hedges = more ambiguous
        matches = _AMBIGUOUS_PHRASES.findall(text)
        return round(min(1.0, len(matches) * 0.25), 4)

    def _sensitivity_risk(self, text: str) -> float:
        """Does the text contain sensitive data that shouldn't be stored? 0.0–1.0"""
        if _SENSITIVE_PHRASES.search(text):
            return 0.80
        return 0.0
