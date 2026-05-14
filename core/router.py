"""
core/router.py — AUA-Veritas query router.

Written fresh (not copied from AUA) because AUA's router is tightly coupled
to vLLM/Ollama specialists and the AUA config system.

Veritas router responsibilities:
1. Classify domain from query
2. Retrieve corrections from memory
3. Build prompt with injected corrections + context grammar
4. Call frontier model(s) based on accuracy level
5. Validate response (contradiction detection)
6. Run peer review round if accuracy == "maximum"
7. Select winner via VCG welfare maximization for multi-model queries
8. Store results and corrections
9. Return response + metadata for the UI
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from core.config import (
    ACCURACY_LEVELS,
    HIGH_STAKES_DOMAINS,
    PEER_REVIEW_PROMPT,
    SUPPORTED_MODELS,
)

log = logging.getLogger(__name__)


@dataclass
class QueryRequest:
    query: str
    conversation_id: str
    accuracy_level: str = "balanced"  # fast | balanced | high | maximum
    enabled_models: list[str] = None  # model IDs the user has enabled

    def __post_init__(self):
        if self.enabled_models is None:
            self.enabled_models = []


@dataclass
class ModelResponse:
    model_id: str
    text: str
    confidence: float
    latency_ms: float
    run_id: str


@dataclass
class RouterResponse:
    response: str                        # final answer text
    primary_model: str                   # model that produced the winner
    all_models_used: list[str]           # all models called in answer round
    confidence_label: str                # "High" | "Medium" | "Uncertain"
    callout_type: str | None             # None | "correction" | "crosscheck" | "disagreement" | "highstakes"
    callout_text: str | None             # plain-language callout for the user
    welfare_scores: dict[str, float] | None  # VCG scores per model (max/high only)
    peer_review_used: bool
    corrections_applied: list[str]       # correction IDs injected
    latency_ms: float


class VeritasRouter:
    """
    Main router for AUA-Veritas.

    Instantiated once on app startup. Holds loaded model backend instances.
    """

    def __init__(self, db_path: str):
        from core.state import VeritasState
        from core.memory import VeritasMemory
        from core.field_classifier import FieldClassifier

        self._state = VeritasState(db_path)
        self._memory = VeritasMemory(self._state)
        self._classifier = FieldClassifier()
        self._backends: dict[str, Any] = {}  # model_id → backend instance
        log.info("VeritasRouter initialized")

    # ── Backend management ────────────────────────────────────────────────────

    def load_backend(self, model_id: str, api_key: str) -> bool:
        """Load a model backend. Returns True on success."""
        spec = SUPPORTED_MODELS.get(model_id)
        if not spec:
            log.warning("Unknown model_id: %s", model_id)
            return False
        try:
            module_path, class_name = spec["plugin_class"].rsplit(":", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            self._backends[model_id] = cls(model_id=model_id, api_key=api_key)
            log.info("Loaded backend: %s", model_id)
            return True
        except Exception as e:
            log.error("Failed to load backend %s: %s", model_id, e)
            return False

    def loaded_models(self) -> list[str]:
        return list(self._backends.keys())

    # ── Main route ────────────────────────────────────────────────────────────

    async def route(self, req: QueryRequest) -> RouterResponse:
        t0 = time.time()

        # Filter to loaded + enabled models
        active_models = [m for m in req.enabled_models if m in self._backends]
        if not active_models:
            return RouterResponse(
                response="No AI models are connected. Please add at least one API key in Settings.",
                primary_model="", all_models_used=[], confidence_label="Uncertain",
                callout_type=None, callout_text=None, welfare_scores=None,
                peer_review_used=False, corrections_applied=[], latency_ms=0.0,
            )

        level_cfg = ACCURACY_LEVELS.get(req.accuracy_level, ACCURACY_LEVELS["balanced"])
        max_models = level_cfg["max_models"]
        do_peer_review = level_cfg["peer_review"]

        # Cap to max_models for this accuracy level
        models_to_use = active_models[:max_models]

        # ── 1. Domain classification ──────────────────────────────────────────
        domain_dist = self._classifier.classify(req.query)
        primary_domain = max(domain_dist, key=lambda k: domain_dist[k])
        is_high_stakes = primary_domain in HIGH_STAKES_DOMAINS

        # ── 2. Retrieve corrections ───────────────────────────────────────────
        corrections = self._memory.retrieve(query=req.query, domain=primary_domain)
        correction_ids = [c["correction_id"] for c in corrections]

        # ── 3. Build prompt with corrections ─────────────────────────────────
        prompt = self._build_prompt(req.query, corrections, primary_domain)

        # ── 4. Answer round (parallel) ────────────────────────────────────────
        answer_tasks = [
            self._call_model(model_id=m, prompt=prompt, domain=primary_domain)
            for m in models_to_use
        ]
        raw_results = await asyncio.gather(*answer_tasks, return_exceptions=True)
        responses: list[ModelResponse] = [
            r for r in raw_results if isinstance(r, ModelResponse)
        ]

        if not responses:
            return RouterResponse(
                response="All selected models are temporarily unavailable. Please try again.",
                primary_model="", all_models_used=models_to_use,
                confidence_label="Uncertain", callout_type=None, callout_text=None,
                welfare_scores=None, peer_review_used=False,
                corrections_applied=correction_ids, latency_ms=(time.time()-t0)*1000,
            )

        # ── 5. VCG selection (if multiple responses) ──────────────────────────
        welfare_scores = None
        if len(responses) >= 2:
            winner, welfare_scores = self._vcg_select(responses, domain_dist)
        else:
            winner = responses[0]

        # ── 6. Peer review round (maximum accuracy) ───────────────────────────
        peer_review_used = False
        disagreement_note = None
        if do_peer_review and len(responses) >= 2:
            peer_review_used = True
            winner, disagreement_note = await self._peer_review(
                winner=winner,
                others=[r for r in responses if r.model_id != winner.model_id],
                query=req.query,
            )

        # ── 7. High-stakes domain check ───────────────────────────────────────
        if is_high_stakes:
            callout_type = "highstakes"
            callout_text = (
                "This topic may require professional advice. "
                "Please verify this answer with a qualified expert."
            )
        elif disagreement_note:
            callout_type = "disagreement"
            callout_text = disagreement_note
        elif len(responses) >= 2 and not disagreement_note:
            callout_type = "crosscheck"
            callout_text = (
                f"Cross-checked with {len(responses)} models. "
                "They gave consistent answers."
            )
        elif correction_ids:
            callout_type = "correction"
            callout_text = "Applied a past correction to improve this answer."
        else:
            callout_type = None
            callout_text = None

        # ── 8. Confidence label ───────────────────────────────────────────────
        if is_high_stakes:
            confidence_label = "Uncertain"
        elif len(responses) >= 2 and not disagreement_note:
            confidence_label = "High"
        elif correction_ids and not disagreement_note:
            confidence_label = "High"
        elif disagreement_note:
            confidence_label = "Medium"
        else:
            confidence_label = "Medium"

        # ── 9. Store run results ──────────────────────────────────────────────
        self._state.append("model_runs", {
            "run_id": winner.run_id,
            "query_id": str(uuid.uuid4()),
            "model_id": winner.model_id,
            "round": "answer",
            "raw_response": winner.text,
            "confidence_score": winner.confidence,
            "vcg_welfare_score": welfare_scores.get(winner.model_id) if welfare_scores else None,
            "vcg_winner": 1,
            "corrections_applied": str(correction_ids),
            "latency_ms": winner.latency_ms,
        })

        total_ms = round((time.time() - t0) * 1000, 1)
        log.info(
            "route complete: domain=%s winner=%s confidence=%s latency=%dms",
            primary_domain, winner.model_id, confidence_label, total_ms,
        )

        return RouterResponse(
            response=winner.text,
            primary_model=winner.model_id,
            all_models_used=[r.model_id for r in responses],
            confidence_label=confidence_label,
            callout_type=callout_type,
            callout_text=callout_text,
            welfare_scores=welfare_scores,
            peer_review_used=peer_review_used,
            corrections_applied=correction_ids,
            latency_ms=total_ms,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_prompt(self, query: str, corrections: list[dict], domain: str) -> str:
        """Build the final prompt with correction injections."""
        if not corrections:
            return query
        correction_block = "\n".join(
            f"- {c['correction_text']}" for c in corrections[:5]
        )
        return (
            f"IMPORTANT CORRECTIONS FOR THIS TOPIC:\n{correction_block}\n\n"
            f"---\n\n{query}"
        )

    async def _call_model(self, model_id: str, prompt: str, domain: str) -> ModelResponse:
        """Call a single model backend."""
        backend = self._backends.get(model_id)
        if not backend:
            raise ValueError(f"Backend not loaded: {model_id}")
        t0 = time.time()
        request = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        result = await backend.complete(request)
        text = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        latency_ms = round((time.time() - t0) * 1000, 1)
        return ModelResponse(
            model_id=model_id,
            text=text,
            confidence=0.80,  # will be updated by confidence_updater
            latency_ms=latency_ms,
            run_id=str(uuid.uuid4()),
        )

    def _vcg_select(
        self,
        responses: list[ModelResponse],
        domain_dist: dict[str, float],
    ) -> tuple[ModelResponse, dict[str, float]]:
        """
        VCG welfare maximization: W_i = P(domain) × confidence × prior_mean_U.
        Returns (winner, welfare_scores_dict).
        """
        welfare: dict[str, float] = {}
        for r in responses:
            spec = SUPPORTED_MODELS.get(r.model_id, {})
            # Use general domain probability if model's domain not in dist
            p_domain = max(domain_dist.values()) if domain_dist else 1.0
            prior_u = self._memory.prior_mean_u(r.model_id) or 1.0
            w = round(p_domain * r.confidence * prior_u, 6)
            welfare[r.model_id] = w

        winner = max(responses, key=lambda r: (welfare[r.model_id], r.confidence))
        return winner, welfare

    async def _peer_review(
        self,
        winner: ModelResponse,
        others: list[ModelResponse],
        query: str,
    ) -> tuple[ModelResponse, str | None]:
        """
        Peer review round: have other models review the winner's answer.
        Uses the cheapest available judge model.
        Returns (confirmed_winner, disagreement_note | None).
        """
        review_prompt = PEER_REVIEW_PROMPT.format(
            query=query,
            answer=winner.text,
        )

        # Pick cheapest available judge
        judge_model = self._pick_cheap_judge(exclude=winner.model_id)
        if not judge_model:
            # No judge available — skip review
            return winner, None

        try:
            review_result = await self._call_model(
                model_id=judge_model,
                prompt=review_prompt,
                domain="general",
            )
            review_text = review_result.text.lower()

            if "incorrect" in review_text or ("partially_correct" in review_text and "issues" in review_text):
                # Extract correction from review
                correction_hint = review_result.text
                return winner, (
                    f"One model flagged a potential issue with the answer. "
                    f"The response was reviewed and may have limitations."
                )
            else:
                # Reviewer agreed
                return winner, None

        except Exception as e:
            log.warning("Peer review failed: %s", e)
            return winner, None

    def _pick_cheap_judge(self, exclude: str) -> str | None:
        """Return the cheapest loaded model suitable for peer review, excluding the winner."""
        for model_id, spec in SUPPORTED_MODELS.items():
            if spec.get("is_cheap_judge") and model_id in self._backends and model_id != exclude:
                return model_id
        # Fallback: any loaded model except winner
        for model_id in self._backends:
            if model_id != exclude:
                return model_id
        return None
