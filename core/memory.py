"""
core/memory.py — AUA-Veritas correction memory.
Adapted from aua/assertions_store.py — per-user scoped from day 1.
COPIED AND MODIFIED — see docs/COPY-LOG.md
"""
from __future__ import annotations

import logging
import time
import uuid

log = logging.getLogger(__name__)

DECAY_YEARS = {"A": None, "B": 10, "C": 3, "D": 0.5}


class VeritasMemory:
    """Per-user correction memory store."""

    def __init__(self, state) -> None:
        self._state = state

    def retrieve(
        self, query: str, domain: str, user_id: str = "local", limit: int = 5
    ) -> list[dict]:
        """
        Retrieve relevant corrections for a query.

        Scoring: keyword overlap (primary) + domain match bonus (secondary).
        Domain is NOT used as a hard filter — corrections stored under a slightly
        different domain still get surfaced if the keywords match.
        """
        # Fetch all active corrections for this user (no domain filter)
        all_corrections = self._state.query(
            "corrections",
            filters={"user_id": user_id},
            limit=500,
        )
        # Exclude superseded corrections
        active = [c for c in all_corrections if c.get("scope") != "superseded"]

        # Score by keyword overlap + domain bonus
        query_words = set(query.lower().split())
        # Also tokenize the query into substrings for partial matching
        query_tokens = set()
        for w in query_words:
            query_tokens.add(w)
            if len(w) > 4:  # add stems for longer words
                query_tokens.add(w[:5])

        scored = []
        for c in active:
            canon = c.get("canonical_query", "")
            canon_words = set(canon.lower().split("_"))

            # Primary: direct keyword overlap
            overlap = len(query_tokens & canon_words)

            # Also check corrective_instruction for keyword overlap
            instruction_words = set(c.get("corrective_instruction", "").lower().split())
            instr_overlap = len(query_words & instruction_words)

            # Domain bonus (0.5 weight — not a hard filter)
            domain_bonus = 0.5 if c.get("domain") == domain else 0.0

            total_score = overlap + (instr_overlap * 0.3) + domain_bonus

            if total_score > 0:
                scored.append((total_score, c))

        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:limit]]

    def store(
        self,
        canonical_query: str,
        domain: str,
        correction_text: str,
        error_type: str = "general",
        confidence: float = 0.9,
        rejected_run_id: str | None = None,
        chosen_text: str | None = None,
        user_id: str = "local",
    ) -> str:
        """Store a new correction. Returns correction_id."""
        correction_id = str(uuid.uuid4())
        self._state.append("corrections", {
            "correction_id": correction_id,
            "user_id": user_id,
            "canonical_query": canonical_query,
            "domain": domain,
            "error_type": error_type,
            "correction_text": correction_text,
            "rejected_run_id": rejected_run_id,
            "chosen_text": chosen_text,
            "confidence": confidence,
            "decay_class": "A",
            "source": "system",
            "created_at": time.time(),
        })
        log.info("Correction stored: %s / %s", domain, canonical_query[:60])
        return correction_id

    def prior_mean_u(self, model_id: str, user_id: str = "local") -> float | None:
        """Get running mean utility score for a model (for VCG welfare)."""
        runs = self._state.query(
            "model_runs",
            filters={"model_id": model_id},
            limit=100,
        )
        scores = [r["utility_score"] for r in runs if r.get("utility_score") is not None]
        return round(sum(scores) / len(scores), 4) if scores else None
