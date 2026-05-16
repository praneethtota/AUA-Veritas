"""
core/trigger_detector.py — Layer 1 + Layer 2 trigger detection.

Answers one binary question per user message:
  "Is this a correction/instruction signal?"

Two-layer local architecture — no cloud API call on every message:

  Layer 1: Regex keyword match    (<1ms, zero cost, zero bundle size)
    Catches explicit correction phrases.
    Ambiguous results → Layer 2.

  Layer 2: spaCy text classifier  (<10ms, ~15MB, zero cost, offline)
    Catches semantic corrections with no trigger keywords.
    Model trained on 270 labelled examples (core/trigger_model/).

Cloud API (Gemini Flash-Lite) is only called in the MEMORY EXTRACTOR,
after the trigger is confirmed — not here.
"""
from __future__ import annotations

import logging
import re
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)

# ── Layer 1 — keyword patterns ────────────────────────────────────────────────

_CORRECTION_PATTERNS = re.compile(
    r"\b("
    r"no[,\s]|wrong|incorrect|that'?s not right|that is not right"
    r"|not what i (asked|said|meant)"
    r"|going forward|from now on|henceforth"
    r"|always |never |don'?t |avoid |stop "
    r"|actually[,\s]|in fact[,\s]"
    r"|remember[,\s]|we decided|we are not|we're not"
    r"|i prefer|i always want|i want .{0,30} to always"
    r"|use .{0,30} not |instead of |rather than "
    r"|that'?s (the )?(wrong|incorrect|opposite|backwards)"
    r"|you keep|you misunderstood|let me correct"
    r"|correction:|the correct (answer|approach|way)"
    r"|specifically said|told you"
    r")\b",
    re.IGNORECASE,
)

_NON_CORRECTION_PATTERNS = re.compile(
    r"^("
    r"(can you |could you |please )?(rewrite|summarize|translate|format|convert|refactor|rename|add|remove|sort|clean)"
    r"|what[\s']"          # what is / what's / what are
    r"|which\b"            # which database / which is / which would
    r"|how (do|does|would|can|should)"
    r"|why (is|are|does|do)"
    r"|when (is|are|does|do)"
    r"|where (is|are|does|do)"
    r"|is (it|there|this|that|postgres|sqlite|rust|python|react|redis)\b"
    r"|should (i|we|you)\b"
    r"|thanks?[,.]?$|thank you"
    r"|ok[,.]?$|okay[,.]?$|got it|sounds good|makes sense|understood|noted"
    r"|perfect[,.]?|great[,.]?|excellent[,.]?"
    r"|write (a|an|the)|create (a|an|the)|generate (a|an|the)|implement|build"
    r")",
    re.IGNORECASE,
)


class TriggerResult(Enum):
    CORRECTION     = "correction"
    NOT_CORRECTION = "not_correction"
    UNCERTAIN      = "uncertain"      # Layer 1 ambiguous → sends to Layer 2


class TriggerDetector:
    """
    Two-layer trigger detector. Fully local — no cloud API calls.

    Usage:
        detector = TriggerDetector()
        result = detector.detect("No, that's wrong — use Postgres.")
        # → True (is a correction signal)

        result = detector.detect("Can you rewrite this function?")
        # → False (not a correction signal)
    """

    def __init__(self, model_path: str | Path | None = None):
        self._nlp = None
        self._model_path = model_path or (
            Path(__file__).parent / "trigger_model" / "model-best"
        )
        self._load_layer2()

    def _load_layer2(self) -> None:
        """Load the spaCy text classifier (Layer 2). Fails gracefully."""
        try:
            import spacy
            if Path(self._model_path).exists():
                self._nlp = spacy.load(self._model_path)
                log.info("Trigger detector Layer 2 loaded from %s", self._model_path)
            else:
                log.warning(
                    "Trigger model not found at %s — Layer 2 disabled, "
                    "using Layer 1 only.", self._model_path
                )
        except ImportError:
            log.warning("spaCy not installed — Layer 2 disabled, using Layer 1 only.")

    def detect(self, message: str) -> bool:
        """
        Detect whether a user message is a correction/instruction signal.

        Args:
            message: The raw user message text.

        Returns:
            True  — correction signal detected (send to memory extractor)
            False — not a correction signal (skip)
        """
        if not message or not message.strip():
            return False

        text = message.strip()

        # ── Layer 1: regex keyword match ──────────────────────────────────────
        if _NON_CORRECTION_PATTERNS.match(text):
            return False  # Clear non-correction

        if _CORRECTION_PATTERNS.search(text):
            return True   # Clear correction

        # ── Layer 2: spaCy classifier for semantic corrections ────────────────
        if self._nlp is not None:
            doc = self._nlp(text)
            score = doc.cats.get("CORRECTION", 0.0)
            log.debug("Layer 2 score for %r: %.3f", text[:60], score)
            return score >= 0.5

        # Fallback: no Layer 2 available — conservative (don't store)
        return False

    def detect_with_score(self, message: str) -> tuple[bool, float]:
        """
        Detect and return the raw confidence score for debugging.

        Returns:
            (is_correction, confidence_score)
            confidence_score is 1.0 for Layer 1 matches, 0.0 for clear misses,
            or the classifier probability for Layer 2 decisions.
        """
        if not message or not message.strip():
            return False, 0.0

        text = message.strip()

        if _NON_CORRECTION_PATTERNS.match(text):
            return False, 0.0

        if _CORRECTION_PATTERNS.search(text):
            return True, 1.0

        if self._nlp is not None:
            doc = self._nlp(text)
            score = doc.cats.get("CORRECTION", 0.0)
            return score >= 0.5, score

        return False, 0.0

    def reload_model(self) -> bool:
        """Hot-reload the spaCy model from disk (after retraining)."""
        self._load_layer2()
        return self._nlp is not None


# Module-level singleton — import and use directly
_detector: TriggerDetector | None = None


def get_detector() -> TriggerDetector:
    """Return the module-level singleton trigger detector."""
    global _detector
    if _detector is None:
        _detector = TriggerDetector()
    return _detector


def is_correction_signal(message: str) -> bool:
    """Convenience function — detect whether a message is a correction signal."""
    return get_detector().detect(message)
