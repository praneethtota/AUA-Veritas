"""
Tests for model incentive transparency and memory pipeline wiring.

Covers:
  - _get_reliability_score() — U score → 0-100 integer
  - _build_system_context() — answer round and reviewer context blocks
  - _build_prompt() — correction injection with include_utility
  - _update_model_score() — audit_log writes
  - Trigger detection in route() — correction signals handled before routing
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.router import VeritasRouter, QueryRequest


# ── Minimal router fixture ────────────────────────────────────────────────────

def make_router() -> VeritasRouter:
    """Build a VeritasRouter with all dependencies mocked, bypassing __init__."""
    router = object.__new__(VeritasRouter)  # skip __init__

    mock_state = MagicMock()
    mock_state.query.return_value = []
    mock_state.append.return_value = "test-id"
    mock_state._conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_state._conn.return_value.__exit__ = MagicMock(return_value=False)

    router._state          = mock_state
    router._memory         = MagicMock()
    router._memory.retrieve.return_value = []
    router._memory.prior_mean_u.return_value = None
    router._classifier     = MagicMock()
    router._classifier.classify.return_value = {"software_engineering": 0.9}
    router._trigger        = MagicMock()
    router._trigger.detect.return_value = False
    router._store_scorer   = MagicMock()
    router._include_scorer = MagicMock()
    router._include_scorer.select.return_value = []
    router._scope_resolver = MagicMock()
    router._backends       = {}
    return router


# ═══════════════════════════════════════════════════════════════════════════════
# _get_reliability_score
# ═══════════════════════════════════════════════════════════════════════════════

def test_get_reliability_score_no_history():
    router = make_router()
    router._state.query.return_value = []
    current, previous = router._get_reliability_score("gpt-4o")
    assert current == 70           # neutral starting score
    assert previous is None


def test_get_reliability_score_single_run():
    router = make_router()
    router._state.query.return_value = [{"utility_score": 0.75, "model_id": "gpt-4o"}]
    current, previous = router._get_reliability_score("gpt-4o")
    assert current == 75
    assert previous is None        # only one run — no trajectory


def test_get_reliability_score_with_trajectory():
    router = make_router()
    # Most recent first — scores were 0.60 before, now 0.80
    router._state.query.return_value = [
        {"utility_score": 0.80, "model_id": "gpt-4o"},   # current
        {"utility_score": 0.60, "model_id": "gpt-4o"},   # previous
    ]
    current, previous = router._get_reliability_score("gpt-4o")
    assert current == 80
    assert previous == 60


def test_get_reliability_score_clamped():
    router = make_router()
    router._state.query.return_value = [{"utility_score": 1.0}]
    current, _ = router._get_reliability_score("gpt-4o")
    assert current == 100

    router._state.query.return_value = [{"utility_score": 0.0}]
    current, _ = router._get_reliability_score("gpt-4o")
    assert current == 0


# ═══════════════════════════════════════════════════════════════════════════════
# _build_system_context
# ═══════════════════════════════════════════════════════════════════════════════

def test_build_system_context_answer_round():
    router = make_router()
    router._state.query.return_value = []   # no history → score 70
    ctx = router._build_system_context("gpt-4o", is_reviewer=False)

    assert "70" in ctx                              # current score shown
    assert "competitive evaluation" in ctx          # explains the context
    assert "Scores increase" in ctx
    assert "Scores decrease" in ctx
    assert "Do not mention" in ctx                  # instruction to hide context
    assert "reviewer" not in ctx.lower()            # not reviewer language


def test_build_system_context_reviewer_round():
    router = make_router()
    router._state.query.return_value = []
    ctx = router._build_system_context("gpt-4o-mini", is_reviewer=True)

    assert "reviewer" in ctx.lower()               # reviewer-specific language
    assert "reviewing" in ctx.lower()
    assert "reviewer score" in ctx.lower()
    assert "Do not mention" not in ctx              # no need to hide in review


def test_build_system_context_shows_trajectory_improved():
    router = make_router()
    router._state.query.return_value = [
        {"utility_score": 0.80},   # current (80)
        {"utility_score": 0.65},   # previous (65)
    ]
    ctx = router._build_system_context("gpt-4o")
    assert "80" in ctx
    assert "65" in ctx
    assert "improved" in ctx


def test_build_system_context_shows_trajectory_dropped():
    router = make_router()
    router._state.query.return_value = [
        {"utility_score": 0.60},   # current (60) — dropped from 75
        {"utility_score": 0.75},   # previous (75)
    ]
    ctx = router._build_system_context("gpt-4o")
    assert "dropped" in ctx


def test_build_system_context_no_formula_exposed():
    """The welfare formula must NOT appear in the system context."""
    router = make_router()
    router._state.query.return_value = []
    ctx = router._build_system_context("gpt-4o")

    assert "P(domain)" not in ctx
    assert "prior_mean_u" not in ctx
    assert "w_e" not in ctx
    assert "formula" not in ctx.lower()


def test_build_system_context_no_competitor_named():
    """The competing model must NOT be named in the system context."""
    router = make_router()
    router._state.query.return_value = []
    ctx = router._build_system_context("gpt-4o")

    # Should not mention specific competitors
    assert "claude" not in ctx.lower()
    assert "gemini" not in ctx.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# _build_prompt
# ═══════════════════════════════════════════════════════════════════════════════

def test_build_prompt_no_corrections():
    router = make_router()
    result = router._build_prompt("What is merge sort?", [], "software_engineering")
    assert result == "What is merge sort?"


def test_build_prompt_with_corrections():
    router = make_router()
    corrections = [
        {"corrective_instruction": "Use Postgres not SQLite."},
        {"corrective_instruction": "Always add type hints."},
    ]
    result = router._build_prompt("What database should I use?", corrections, "software_engineering")
    assert "Use Postgres not SQLite." in result
    assert "Always add type hints." in result
    assert "VERIFIED CORRECTIONS" in result
    assert "What database should I use?" in result


def test_build_prompt_corrections_before_query():
    router = make_router()
    corrections = [{"corrective_instruction": "Use Postgres."}]
    result = router._build_prompt("What database?", corrections, "software_engineering")
    corrections_pos = result.find("VERIFIED")
    query_pos = result.find("What database?")
    assert corrections_pos < query_pos


def test_build_prompt_caps_at_5_corrections():
    router = make_router()
    corrections = [{"corrective_instruction": f"Correction {i}"} for i in range(10)]
    result = router._build_prompt("query", corrections, "general")
    # Only first 5 should appear
    assert "Correction 0" in result
    assert "Correction 4" in result
    assert "Correction 5" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# _update_model_score
# ═══════════════════════════════════════════════════════════════════════════════

def test_update_model_score_writes_audit_log():
    router = make_router()
    router._state.query.return_value = [{"utility_score": 0.72}]   # current=72
    router._update_model_score("gpt-4o", delta=-10, reason="test penalty")

    call_args = router._state.append.call_args_list[-1]
    table = call_args[0][0]
    record = call_args[0][1]

    assert table == "audit_log"
    assert record["model_id"] == "gpt-4o"
    assert record["score_before"] == 72
    assert record["score_after"] == 62
    assert record["verdict"] == "incorrect"
    assert record["event_type"] == "score_update"


def test_update_model_score_clamped_at_0():
    router = make_router()
    router._state.query.return_value = [{"utility_score": 0.05}]  # current=5
    router._update_model_score("gpt-4o", delta=-20)

    record = router._state.append.call_args_list[-1][0][1]
    assert record["score_after"] == 0   # clamped, not -15


def test_update_model_score_clamped_at_100():
    router = make_router()
    router._state.query.return_value = [{"utility_score": 0.98}]  # current=98
    router._update_model_score("gpt-4o", delta=+10)

    record = router._state.append.call_args_list[-1][0][1]
    assert record["score_after"] == 100   # clamped, not 108


def test_update_model_score_positive_delta_verdict():
    router = make_router()
    router._state.query.return_value = [{"utility_score": 0.70}]
    router._update_model_score("gpt-4o", delta=+2)

    record = router._state.append.call_args_list[-1][0][1]
    assert record["verdict"] == "correct"


# ═══════════════════════════════════════════════════════════════════════════════
# Trigger detection in route()
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_route_correction_signal_triggers_memory_pipeline():
    """When trigger detector fires, _handle_correction is called."""
    router = make_router()
    router._trigger.detect.return_value = True   # it IS a correction
    router._backends = {"gpt-4o": AsyncMock()}

    # Patch _handle_correction to confirm it was called
    router._handle_correction = AsyncMock(return_value=None)

    req = QueryRequest(
        query="No, use Postgres not SQLite.",
        conversation_id="conv-1",
        accuracy_level="balanced",
        enabled_models=["gpt-4o"],
    )
    req.conversation_history = [
        {"role": "user", "content": "What database?"},
        {"role": "assistant", "content": "Use SQLite."},
    ]

    # _handle_correction returns None → falls through to normal routing
    # Mock normal routing path
    router._call_model_with_context = AsyncMock(return_value=MagicMock(
        model_id="gpt-4o", text="Postgres answer", confidence=0.8,
        latency_ms=100.0, run_id="r1",
    ))

    with patch.object(router, "_vcg_select", return_value=(MagicMock(
        model_id="gpt-4o", text="Postgres answer", confidence=0.8,
        latency_ms=100.0, run_id="r1",
    ), None)):
        try:
            await router.route(req)
        except Exception:
            pass  # routing may fail in mock context, we just need the call check

    router._handle_correction.assert_called_once()


@pytest.mark.asyncio
async def test_route_non_correction_skips_memory_pipeline():
    """When trigger detector returns False, _handle_correction is NOT called."""
    router = make_router()
    router._trigger.detect.return_value = False   # NOT a correction
    router._handle_correction = AsyncMock()

    req = QueryRequest(
        query="What is merge sort?",
        conversation_id="conv-1",
        accuracy_level="fast",
        enabled_models=[],  # no models → early return
    )

    await router.route(req)

    router._handle_correction.assert_not_called()
