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
        """Retrieve relevant corrections for a query."""
        # Simple keyword match on canonical_query for MVP
        # Upgrade path: embedding similarity in Phase 5
        all_corrections = self._state.query(
            "corrections",
            filters={"user_id": user_id, "domain": domain},
            limit=200,
        )
        # Score by keyword overlap
        query_words = set(query.lower().split())
        scored = []
        for c in all_corrections:
            canon_words = set(c.get("canonical_query", "").lower().split("_"))
            overlap = len(query_words & canon_words)
            if overlap > 0:
                scored.append((overlap, c))
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
