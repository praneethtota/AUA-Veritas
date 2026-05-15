"""
core/include_utility.py — Include utility scorer.

Scores which stored memories are most relevant to inject into the
current prompt. Called before every model call to select which
corrections from the store to include.

Formula (from roadmap §"Include utility scoring"):
  include_utility = 0.30 × relevance_to_current_task
                  + 0.25 × failure_prevention_value
                  + 0.20 × importance
                  + 0.10 × recency
                  + 0.10 × confidence
                  + 0.05 × pinned_boost
                  − 0.20 × staleness
                  − 0.15 × token_cost

This prevents the prompt from becoming a memory dump — only the most
relevant corrections are injected. The user never sees this scoring,
just better answers.

Returns corrections sorted by include_utility, top N selected.
"""
from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

# ── Default limits ────────────────────────────────────────────────────────────

DEFAULT_MAX_CORRECTIONS = 5      # max corrections to inject per prompt
DEFAULT_MIN_SCORE       = 0.30   # below this, never inject
MAX_INSTRUCTION_TOKENS  = 200    # approximate token cap per correction


@dataclass
class ScoredCorrection:
    correction:      dict
    include_score:   float
    breakdown:       dict[str, float]


# ── Scorer ────────────────────────────────────────────────────────────────────

class IncludeUtilityScorer:
    """
    Selects which stored corrections to inject into the next prompt.

    Usage:
        scorer = IncludeUtilityScorer()
        selected = scorer.select(
            query="What database should I use?",
            domain="software_engineering",
            corrections=all_corrections,
            active_project="My App",
            max_corrections=5,
        )
        # selected is a list of correction dicts, highest score first
    """

    def select(
        self,
        query: str,
        domain: str,
        corrections: list[dict],
        active_project: str | None = None,
        max_corrections: int = DEFAULT_MAX_CORRECTIONS,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> list[dict]:
        """
        Select and rank corrections for injection into the current prompt.

        Args:
            query:           The current user query.
            domain:          The classified domain of the current query.
            corrections:     All stored corrections for this user/project.
            active_project:  Name of the active project.
            max_corrections: Maximum number of corrections to return.
            min_score:       Minimum include_utility to be considered.

        Returns:
            List of correction dicts, sorted by include_utility desc, capped at max.
        """
        if not corrections:
            return []

        scored = []
        for correction in corrections:
            # Skip superseded corrections
            if correction.get("scope") == "superseded":
                continue

            result = self.score(
                correction=correction,
                query=query,
                domain=domain,
                active_project=active_project,
            )
            if result.include_score >= min_score:
                scored.append(result)

        # Sort by score descending, take top N
        scored.sort(key=lambda x: x.include_score, reverse=True)
        selected = scored[:max_corrections]

        log.debug(
            "include_utility: %d/%d corrections selected for injection (query: %s...)",
            len(selected), len(corrections), query[:40],
        )

        return [s.correction for s in selected]

    def score(
        self,
        correction: dict,
        query: str,
        domain: str,
        active_project: str | None = None,
    ) -> ScoredCorrection:
        """
        Score a single correction for inclusion in the current prompt.

        Args:
            correction:     Correction dict from the corrections table.
            query:          Current user query.
            domain:         Classified domain of current query.
            active_project: Active project name.

        Returns:
            ScoredCorrection with include_score and sub-score breakdown.
        """
        breakdown = {
            "relevance":        self._relevance(correction, query, domain),
            "failure_prevention": self._failure_prevention(correction),
            "importance":       self._importance(correction),
            "recency":          self._recency(correction),
            "confidence":       float(correction.get("confidence", 0.8)),
            "pinned":           self._pinned(correction),
            "staleness":        self._staleness(correction),
            "token_cost":       self._token_cost(correction),
        }

        raw = (
              0.30 * breakdown["relevance"]
            + 0.25 * breakdown["failure_prevention"]
            + 0.20 * breakdown["importance"]
            + 0.10 * breakdown["recency"]
            + 0.10 * breakdown["confidence"]
            + 0.05 * breakdown["pinned"]
            - 0.20 * breakdown["staleness"]
            - 0.15 * breakdown["token_cost"]
        )
        include_score = round(max(0.0, min(1.0, raw)), 4)

        return ScoredCorrection(
            correction=correction,
            include_score=include_score,
            breakdown=breakdown,
        )

    # ── Sub-scores ────────────────────────────────────────────────────────────

    def _relevance(self, correction: dict, query: str, domain: str) -> float:
        """
        How relevant is this correction to the current query/domain? 0.0–1.0

        Uses keyword overlap between the query and the correction's canonical_query
        and corrective_instruction.
        """
        score = 0.0

        # Domain match
        if correction.get("domain") == domain:
            score += 0.40
        elif correction.get("domain") == "general":
            score += 0.15

        # Scope bonus — global corrections relevant everywhere
        if correction.get("scope") == "global":
            score += 0.15

        # Keyword overlap between query and canonical_query
        query_words = set(query.lower().split())
        canonical_words = set(
            correction.get("canonical_query", "").replace("_", " ").lower().split()
        )
        instruction_words = set(
            correction.get("corrective_instruction", "").lower().split()
        )

        overlap_canonical    = len(query_words & canonical_words)
        overlap_instruction  = len(query_words & instruction_words)

        if overlap_canonical > 0:
            score += min(0.30, overlap_canonical * 0.10)
        if overlap_instruction > 0:
            score += min(0.15, overlap_instruction * 0.05)

        return round(min(1.0, score), 4)

    def _failure_prevention(self, correction: dict) -> float:
        """
        How much does injecting this prevent a known failure? 0.0–1.0

        Failure patterns and factual corrections from the same domain
        have the highest prevention value.
        """
        type_scores = {
            "failure_pattern":        1.0,   # model keeps repeating this mistake
            "factual_correction":     0.85,  # model was wrong; prevent recurrence
            "project_decision":       0.70,  # prevents contradiction of decisions
            "persistent_instruction": 0.65,
            "preference":             0.40,
        }
        return type_scores.get(correction.get("type", "factual_correction"), 0.50)

    def _importance(self, correction: dict) -> float:
        """
        Inherent importance of this correction type. 0.0–1.0
        Uses confidence as a proxy for verified importance.
        """
        confidence = float(correction.get("confidence", 0.80))
        decay_boost = {"A": 0.10, "B": 0.05, "C": 0.0, "D": -0.10}
        base = confidence + decay_boost.get(correction.get("decay_class", "A"), 0.0)
        return round(max(0.0, min(1.0, base)), 4)

    def _recency(self, correction: dict) -> float:
        """
        How recent is this correction? Recent = more relevant. 0.0–1.0

        Exponential decay over 90 days:
          score = exp(-days_old / 90)
          age = 0 days   → 1.00
          age = 30 days  → 0.72
          age = 90 days  → 0.37
          age = 180 days → 0.14
        """
        created_at = correction.get("created_at") or 0.0
        if not created_at:
            return 0.50  # unknown age — neutral

        decay_class = correction.get("decay_class", "A")
        if decay_class == "A":
            return 0.80  # permanent facts don't decay
        if decay_class == "D":
            # Fast-moving info decays quickly — 30-day half-life
            days_old = (time.time() - float(created_at)) / 86400
            return round(max(0.0, math.exp(-days_old / 30)), 4)

        days_old = (time.time() - float(created_at)) / 86400
        return round(max(0.0, math.exp(-days_old / 90)), 4)

    def _pinned(self, correction: dict) -> float:
        """Was this correction pinned by the user? 0.0 or 1.0"""
        return 1.0 if correction.get("pinned") else 0.0

    def _staleness(self, correction: dict) -> float:
        """
        Is this correction stale relative to its decay class? 0.0–1.0

        Staleness applies a penalty when the correction is significantly
        older than its expected lifetime.
        """
        decay_class = correction.get("decay_class", "A")
        if decay_class == "A":
            return 0.0  # permanent — never stale

        created_at = correction.get("created_at") or 0.0
        if not created_at:
            return 0.0

        days_old = (time.time() - float(created_at)) / 86400
        # Stale thresholds per decay class
        stale_days = {"B": 3650, "C": 1095, "D": 180}
        threshold = stale_days.get(decay_class, 365)

        if days_old > threshold:
            # Linearly increase staleness penalty after threshold
            excess_fraction = min(1.0, (days_old - threshold) / threshold)
            return round(excess_fraction, 4)
        return 0.0

    def _token_cost(self, correction: dict) -> float:
        """
        Approximate token cost of including this correction. 0.0–1.0

        Longer corrective instructions cost more tokens.
        Normalized against MAX_INSTRUCTION_TOKENS.
        """
        text = correction.get("corrective_instruction", "")
        word_count = len(text.split())
        # ~1.3 tokens per word (rough approximation)
        approx_tokens = word_count * 1.3
        return round(min(1.0, approx_tokens / MAX_INSTRUCTION_TOKENS), 4)
