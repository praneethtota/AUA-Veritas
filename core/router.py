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

# Score display constants
SCORE_SCALE = 100          # U (0.0-1.0) → integer 0-100
SCORE_TRAJECTORY_WINDOW = 5  # look at last N runs to compute "previous" score


@dataclass
class QueryRequest:
    query: str
    conversation_id: str
    accuracy_level: str = "balanced"  # fast | balanced | high | maximum
    enabled_models: list[str] = None  # model IDs the user has enabled
    conversation_history: list[dict] = None  # prior messages for correction context

    def __post_init__(self):
        if self.enabled_models is None:
            self.enabled_models = []
        if self.conversation_history is None:
            self.conversation_history = []


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
        from core.trigger_detector import TriggerDetector
        from core.memory_extractor import MemoryExtractor
        from core.store_utility import StoreUtilityScorer
        from core.scope_resolver import ScopeResolver
        from core.include_utility import IncludeUtilityScorer

        self._state          = VeritasState(db_path)
        self._memory         = VeritasMemory(self._state)
        self._classifier     = FieldClassifier()
        self._trigger        = TriggerDetector()
        self._store_scorer   = StoreUtilityScorer()
        self._include_scorer = IncludeUtilityScorer()
        self._scope_resolver = ScopeResolver(self._state)
        self._backends: dict[str, Any] = {}
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

        active_models = [m for m in req.enabled_models if m in self._backends]
        if not active_models:
            return RouterResponse(
                response="No AI models are connected. Please add at least one API key in Settings.",
                primary_model="", all_models_used=[], confidence_label="Uncertain",
                callout_type=None, callout_text=None, welfare_scores=None,
                peer_review_used=False, corrections_applied=[], latency_ms=0.0,
            )

        # ── 1. Check if this message is a correction signal ───────────────────
        is_correction = self._trigger.detect(req.query)
        if is_correction and req.conversation_history:
            correction_result = await self._handle_correction(req, active_models)
            if correction_result:
                return correction_result
            # If extraction failed, fall through to normal routing

        level_cfg = ACCURACY_LEVELS.get(req.accuracy_level, ACCURACY_LEVELS["balanced"])
        max_models = level_cfg["max_models"]
        do_peer_review = level_cfg["peer_review"]
        models_to_use = active_models[:max_models]

        # ── 2. Domain classification ──────────────────────────────────────────
        domain_dist = self._classifier.classify(req.query)
        primary_domain = max(domain_dist, key=lambda k: domain_dist[k])
        is_high_stakes = primary_domain in HIGH_STAKES_DOMAINS

        # ── 3. Retrieve + select corrections using include_utility ────────────
        all_corrections = self._memory.retrieve(query=req.query, domain=primary_domain)
        selected_corrections = self._include_scorer.select(
            query=req.query,
            domain=primary_domain,
            corrections=all_corrections,
            active_project=req.conversation_id,
            max_corrections=5,
        )
        correction_ids = [c.get("correction_id", "") for c in selected_corrections]

        # ── 4. Build prompt ───────────────────────────────────────────────────
        prompt = self._build_prompt(req.query, selected_corrections, primary_domain)

        # ── 5. Answer round ───────────────────────────────────────────────────
        answer_tasks = [
            self._call_model_with_context(
                model_id=m, prompt=prompt, domain=primary_domain,
                accuracy_level=req.accuracy_level,
            )
            for m in models_to_use
        ]
        raw_results = await asyncio.gather(*answer_tasks, return_exceptions=True)
        responses: list[ModelResponse] = []
        skipped_models: list[str] = []
        for model_id, result in zip(models_to_use, raw_results):
            if isinstance(result, ModelResponse):
                responses.append(result)
            else:
                skipped_models.append(model_id)
                log.warning("Model %s failed: %s", model_id, result)

        if not responses:
            skipped_str = ', '.join(skipped_models) if skipped_models else 'all'
            return RouterResponse(
                response=f"All selected models are temporarily unavailable ({skipped_str} failed — rate limit or API error). Please try again or select different models.",
                primary_model="", all_models_used=models_to_use,
                confidence_label="Uncertain", callout_type=None, callout_text=None,
                welfare_scores=None, peer_review_used=False,
                corrections_applied=correction_ids, latency_ms=(time.time()-t0)*1000,
            )

        # ── 6. VCG selection ──────────────────────────────────────────────────
        welfare_scores = None
        if len(responses) >= 2:
            winner, welfare_scores = self._vcg_select(responses, domain_dist)
        else:
            winner = responses[0]

        # ── 7. Peer review ────────────────────────────────────────────────────
        peer_review_used = False
        disagreement_note = None
        if do_peer_review and len(responses) >= 2:
            peer_review_used = True
            winner, disagreement_note = await self._peer_review(
                winner=winner,
                others=[r for r in responses if r.model_id != winner.model_id],
                query=req.query,
            )

        # ── 8. Update model scores after successful call ──────────────────────
        self._update_model_score(winner.model_id, delta=1, reason="correct_response")

        # ── 9. Callout and confidence ─────────────────────────────────────────
        if is_high_stakes:
            callout_type = "highstakes"
            callout_text = (
                "This topic may require professional advice. "
                "Please verify this answer with a qualified expert."
            )
        elif disagreement_note:
            callout_type = "disagreement"
            callout_text = disagreement_note
        elif skipped_models:
            callout_type = "disagreement"
            callout_text = (
                f"{', '.join(skipped_models)} {'was' if len(skipped_models)==1 else 'were'} "
                f"unavailable (rate limit or API error) — answered with {len(responses)} "
                f"model{'s' if len(responses)!=1 else ''}."
            )
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

        # ── 10. Store run result ──────────────────────────────────────────────
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

    def _get_reliability_score(self, model_id: str) -> tuple[int, int | None]:
        """
        Get a model's reliability score as a 0-100 integer for display to the model.

        Returns (current_score, previous_score | None).
        Uses mean utility from recent model_runs, mapped to 0-100.
        Returns (70, None) if no history — neutral starting point.
        """
        runs = self._state.query(
            "model_runs",
            filters={"model_id": model_id},
            limit=SCORE_TRAJECTORY_WINDOW * 2,
        )
        scores = [
            r["utility_score"] for r in runs
            if r.get("utility_score") is not None
        ]
        if not scores:
            return (70, None)

        current_score = round(scores[0] * SCORE_SCALE)  # most recent
        if len(scores) >= 2:
            prev_mean = sum(scores[1:]) / len(scores[1:])
            previous_score = round(prev_mean * SCORE_SCALE)
        else:
            previous_score = None

        return (current_score, previous_score)

    def _build_system_context(
        self,
        model_id: str,
        is_reviewer: bool = False,
    ) -> str:
        """
        Build the system context block injected into every model call.

        Shows the model its reliability score trajectory (not the formula or weights)
        and explains what causes scores to increase or decrease.

        Game theory basis: truthfulness is the dominant strategy — a model that
        hallucinates or over-claims certainty will see its score drop, lose future
        selections, and end up worse off than honest responses would have yielded.
        """
        current, previous = self._get_reliability_score(model_id)

        if previous is not None:
            delta = current - previous
            if delta > 0:
                trajectory = f"Your reliability score: {current}  (previous: {previous} → improved)"
            elif delta < 0:
                trajectory = f"Your reliability score: {current}  (previous: {previous} → dropped)"
            else:
                trajectory = f"Your reliability score: {current}  (previous: {previous} → unchanged)"
        else:
            trajectory = f"Your reliability score: {current}  (building history)"

        if not is_reviewer:
            return (
                f"{trajectory}\n\n"
                "You are one of several AI models answering this question in a competitive evaluation.\n\n"
                "Scores increase when:\n"
                "  - Your answers are accurate (verified by peer review and past corrections)\n"
                "  - You correctly express uncertainty when you are not sure\n"
                "  - You are consistent with verified corrections on this topic\n\n"
                "Scores decrease when:\n"
                "  - Your answer is flagged as incorrect by peer review\n"
                "  - You claim certainty about something that turns out to be wrong\n"
                "  - You contradict a verified past correction\n\n"
                "The model with the highest combined welfare score handles this query.\n"
                "Do not mention this scoring context in your response."
            )
        else:
            return (
                f"{trajectory}\n\n"
                "You are reviewing another model's answer for accuracy.\n\n"
                "Your reviewer score increases when:\n"
                "  - You correctly identify errors that are later confirmed\n"
                "  - You correctly validate answers that are later confirmed correct\n\n"
                "Your reviewer score decreases when:\n"
                "  - You flag correct answers as wrong\n"
                "  - You approve answers that are later found to be incorrect\n\n"
                "Be precise. 'Incorrect because X' is more valuable than vague criticism.\n"
                "Agreeing when correct is equally valuable as disagreeing when wrong."
            )

    def _build_prompt(self, query: str, corrections: list[dict], domain: str) -> str:
        """Build the final prompt with correction injections (no system context here)."""
        if not corrections:
            return query
        correction_block = "\n".join(
            f"- {c.get('corrective_instruction', c.get('correction_text', ''))}"
            for c in corrections[:5]
        )
        return (
            f"VERIFIED CORRECTIONS FOR THIS TOPIC:\n{correction_block}\n\n"
            f"---\n\n{query}"
        )

    async def _call_model_with_context(
        self,
        model_id: str,
        prompt: str,
        domain: str,
        accuracy_level: str = "balanced",
    ) -> ModelResponse:
        """
        Call a model with system context (reliability score + evaluation criteria).
        Wraps _call_model, prepending the system context block as a system message.
        """
        system_context = self._build_system_context(model_id, is_reviewer=False)
        backend = self._backends.get(model_id)
        if not backend:
            raise ValueError(f"Backend not loaded: {model_id}")
        t0 = time.time()
        request = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_context},
                {"role": "user",   "content": prompt},
            ],
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
            confidence=0.80,
            latency_ms=latency_ms,
            run_id=str(uuid.uuid4()),
        )

    async def _call_model(self, model_id: str, prompt: str, domain: str) -> ModelResponse:
        """Call a model without system context (used for peer review judge calls)."""
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
            confidence=0.80,
            latency_ms=latency_ms,
            run_id=str(uuid.uuid4()),
        )

    def _update_model_score(
        self,
        model_id: str,
        delta: int,
        reason: str = "",
    ) -> None:
        """
        Record a score event for a model.
        delta: positive = score increased, negative = decreased.
        Stored in audit_log for the Look Under the Hood graph.
        """
        current, previous = self._get_reliability_score(model_id)
        new_score = max(0, min(100, current + delta))
        try:
            self._state.append("audit_log", {
                "audit_id":          str(uuid.uuid4()),
                "model_id":          model_id,
                "event_type":        "score_update",
                "score_before":      current,
                "score_after":       new_score,
                "verdict":           "correct" if delta >= 0 else "incorrect",
                "correction_stored": False,
                "query_preview":     reason[:60],
                "created_at":        time.time(),
            })
        except Exception as e:
            log.warning("Failed to record score event: %s", e)

    async def _handle_correction(
        self,
        req: QueryRequest,
        active_models: list[str],
    ) -> RouterResponse | None:
        """
        Handle a user message that the trigger detector identified as a correction signal.

        Extracts a structured correction, scores it, resolves scope, and stores it.
        Returns a RouterResponse with an amber callout if stored successfully,
        or None if extraction failed (caller falls through to normal routing).
        """
        from core.memory_extractor import MemoryExtractor
        from core.scope_resolver import ResolutionAction

        # Find the last AI response and original query from conversation history
        history = req.conversation_history or []
        last_ai_response = ""
        original_query   = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant" and not last_ai_response:
                last_ai_response = msg.get("content", "")
            if msg.get("role") == "user" and last_ai_response and not original_query:
                original_query = msg.get("content", "")
            if last_ai_response and original_query:
                break

        if not last_ai_response:
            return None  # no prior AI response to correct — fall through

        # Never treat system-generated error messages as corrections.
        # The spaCy classifier scores these at 1.0 (the word "failed/unavailable"
        # looks like correction language). This guard prevents garbage memory storage.
        _SYSTEM_PREFIXES = (
            "All selected models are temporarily unavailable",
            "All selected models",
            "No AI models are connected",
        )
        if any(last_ai_response.startswith(p) for p in _SYSTEM_PREFIXES):
            log.debug("Skipping correction pipeline — last response was a system error message")
            return None
        corrected_model = active_models[0] if active_models else "unknown"

        extractor = MemoryExtractor(backends=self._backends)
        extraction = await extractor.extract(
            user_message=req.query,
            original_query=original_query or req.query,
            ai_response=last_ai_response,
            model_id=corrected_model,
            active_project=req.conversation_id,
        )

        if not extraction:
            return None

        # Score the extraction
        store_result = self._store_scorer.score(
            extraction,
            user_message=req.query,
            original_query=original_query,
            active_project=req.conversation_id,
        )

        if not store_result.should_store:
            log.debug("Correction below store threshold (%.3f) — discarding", store_result.score)
            return None

        # Resolve scope and store
        resolution = self._scope_resolver.resolve(
            extraction,
            active_project=req.conversation_id,
        )

        if resolution.action == ResolutionAction.PROMPT_USER:
            # Return a response asking the user to confirm
            return RouterResponse(
                response=req.query,
                primary_model="system",
                all_models_used=[],
                confidence_label="High",
                callout_type="conflict",
                callout_text=resolution.conflict_reason,
                welfare_scores=None,
                peer_review_used=False,
                corrections_applied=[],
                latency_ms=0.0,
            )

        # Store silently (AUTO_SAVE) or via review card (REVIEW_CARD)
        stored = self._scope_resolver.apply(
            resolution, extraction, active_project=req.conversation_id
        )

        # Penalize the model that was corrected
        delta = extraction._score_delta()
        if delta != 0:
            self._update_model_score(corrected_model, delta=delta, reason=extraction.reason)

        if stored:
            callout_text = (
                "Got it — I've saved that correction. "
                "I'll apply it to future answers on this topic."
            )
            if store_result.decision.value == "review_card":
                callout_text = (
                    "Noted. Save this as a project correction? "
                    "[This shows the review card in the UI]"
                )
            return RouterResponse(
                response=callout_text,
                primary_model="system",
                all_models_used=[],
                confidence_label="High",
                callout_type="correction",
                callout_text=None,
                welfare_scores=None,
                peer_review_used=False,
                corrections_applied=[extraction.extraction_id],
                latency_ms=0.0,
            )

        return None

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
        Uses cheapest available judge. Judge sees its own reliability score
        so it has an incentive to give accurate, honest reviews.
        """
        from core.config import PEER_REVIEW_PROMPT

        review_prompt = PEER_REVIEW_PROMPT.format(
            query=query,
            answer=winner.text,
        )

        judge_model = self._pick_cheap_judge(exclude=winner.model_id)
        if not judge_model:
            return winner, None

        # Inject reviewer system context so the judge knows it's being scored
        reviewer_context = self._build_system_context(judge_model, is_reviewer=True)

        try:
            backend = self._backends.get(judge_model)
            if not backend:
                return winner, None

            result = await backend.complete({
                "model": judge_model,
                "messages": [
                    {"role": "system", "content": reviewer_context},
                    {"role": "user",   "content": review_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 400,
            })
            review_text = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            review_lower = review_text.lower()

            if "incorrect" in review_lower or (
                "partially_correct" in review_lower and "issues" in review_lower
            ):
                # Penalize the winner model for being flagged
                self._update_model_score(
                    winner.model_id, delta=-5,
                    reason="peer_review_flagged_incorrect"
                )
                # Reward the reviewer for catching an error
                self._update_model_score(
                    judge_model, delta=2,
                    reason="peer_review_caught_error"
                )
                return winner, (
                    "One model flagged a potential issue with this answer. "
                    "The response was reviewed and may have limitations."
                )
            else:
                # Both agreed — reward both
                self._update_model_score(winner.model_id, delta=1, reason="peer_review_confirmed")
                self._update_model_score(judge_model, delta=1, reason="peer_review_confirmed_correctly")
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
