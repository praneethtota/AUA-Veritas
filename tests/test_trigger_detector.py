"""Tests for TriggerDetector — Layer 1 and Layer 2 detection."""
import pytest
from core.trigger_detector import TriggerDetector, is_correction_signal


@pytest.fixture
def detector():
    return TriggerDetector()


# ── Layer 1: clear corrections ────────────────────────────────────────────────

def test_explicit_negation(detector):
    assert detector.detect("No, that's wrong — use Postgres.") is True

def test_incorrect_keyword(detector):
    assert detector.detect("That's incorrect. Use snake_case.") is True

def test_going_forward(detector):
    assert detector.detect("Going forward always add type hints.") is True

def test_from_now_on(detector):
    assert detector.detect("From now on, use async patterns.") is True

def test_never_keyword(detector):
    assert detector.detect("Never use SQLite in production.") is True

def test_always_keyword(detector):
    assert detector.detect("Always inject the correction store first.") is True

def test_dont_keyword(detector):
    assert detector.detect("Don't use the primary model for review.") is True

def test_actually_correction(detector):
    assert detector.detect("Actually, it should be a POST endpoint.") is True

def test_remember_instruction(detector):
    assert detector.detect("Remember, we use Postgres not SQLite.") is True

def test_we_decided(detector):
    assert detector.detect("We decided to use Electron for the desktop app.") is True

def test_wrong_keyword(detector):
    assert detector.detect("Wrong — use snake_case not camelCase.") is True

def test_i_prefer(detector):
    assert detector.detect("I prefer concise explanations throughout.") is True

# ── Layer 1: clear non-corrections ───────────────────────────────────────────

def test_transient_rewrite(detector):
    assert detector.detect("Can you rewrite this paragraph?") is False

def test_question_what(detector):
    assert detector.detect("What is the complexity of heapsort?") is False

def test_question_how(detector):
    assert detector.detect("How does the VCG mechanism work?") is False

def test_positive_thanks(detector):
    assert detector.detect("Thanks, that looks good.") is False

def test_positive_ok(detector):
    assert detector.detect("OK.") is False

def test_positive_perfect(detector):
    assert detector.detect("Perfect, let's continue.") is False

def test_code_request(detector):
    assert detector.detect("Write a function that implements binary search.") is False

def test_generate_request(detector):
    assert detector.detect("Generate a SQLite schema for the corrections table.") is False

# ── Layer 2: semantic corrections (no keyword) ────────────────────────────────

def test_semantic_not_merging(detector):
    assert detector.detect("We are not merging these two concepts. They are separate.") is True

def test_semantic_different_things(detector):
    assert detector.detect("These are two different things — do not conflate them.") is True

def test_semantic_independent(detector):
    assert detector.detect("The AUA Framework and AUA-Veritas are completely independent.") is True

def test_semantic_distinct_components(detector):
    assert detector.detect("The router and the arbiter are distinct components.") is True

# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_string(detector):
    assert detector.detect("") is False

def test_whitespace_only(detector):
    assert detector.detect("   ") is False

def test_detect_with_score_correction(detector):
    is_corr, score = detector.detect_with_score("No, that's wrong.")
    assert is_corr is True
    assert score >= 0.5

def test_detect_with_score_non_correction(detector):
    is_corr, score = detector.detect_with_score("What is merge sort?")
    assert is_corr is False
    assert score < 0.5

# ── Module-level convenience function ────────────────────────────────────────

def test_module_level_function():
    assert is_correction_signal("Going forward use async patterns.") is True
    assert is_correction_signal("Can you explain how this works?") is False
