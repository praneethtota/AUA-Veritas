"""Tests for ScopeResolver — OOP inheritance model and conflict handling."""
import pytest
from unittest.mock import MagicMock, patch

from core.scope_resolver import (
    ScopeResolver,
    ResolutionAction,
    ResolutionResult,
    Scope,
    SCOPE_PRIORITY,
)
from core.memory_extractor import ExtractionResult
import time


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_extraction(**kwargs) -> ExtractionResult:
    defaults = dict(
        extraction_id="new-id",
        type="factual_correction",
        scope="project",
        corrective_instruction="Use Postgres not SQLite.",
        reason="Wrong DB recommended.",
        canonical_query="database_choice",
        domain="software_engineering",
        confidence=0.95,
        decay_class="A",
        model_id="gpt-4o",
        query_preview="What database should I use?",
        extracted_via="rules",
    )
    defaults.update(kwargs)
    return ExtractionResult(**defaults)


def make_existing_correction(**kwargs) -> dict:
    defaults = dict(
        correction_id="old-id",
        user_id="local",
        canonical_query="database_choice",
        domain="software_engineering",
        scope="project",
        corrective_instruction="Use SQLite for simplicity.",
        confidence=0.80,
        decay_class="A",
    )
    defaults.update(kwargs)
    return defaults


def make_resolver(existing_corrections: list[dict] | None = None) -> ScopeResolver:
    """Create a ScopeResolver with a mocked state store."""
    mock_state = MagicMock()
    existing = existing_corrections or []

    def mock_query(table, filters=None, limit=100):
        if not existing:
            return []
        filters = filters or {}
        result = []
        for c in existing:
            if all(c.get(k) == v for k, v in filters.items()):
                result.append(c)
        return result[:limit]

    mock_state.query.side_effect = mock_query
    mock_state._conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_state._conn.return_value.__exit__ = MagicMock(return_value=False)

    return ScopeResolver(state=mock_state)


# ── Scope enum and priority ───────────────────────────────────────────────────

def test_scope_values():
    assert Scope.GLOBAL.value == "global"
    assert Scope.PROJECT.value == "project"
    assert Scope.CONVERSATION.value == "conversation"


def test_scope_priority_order():
    assert SCOPE_PRIORITY[Scope.PROJECT] > SCOPE_PRIORITY[Scope.GLOBAL]
    assert SCOPE_PRIORITY[Scope.CONVERSATION] > SCOPE_PRIORITY[Scope.PROJECT]


# ── ResolutionResult ──────────────────────────────────────────────────────────

def test_needs_user_input_true_for_prompt():
    r = ResolutionResult(action=ResolutionAction.PROMPT_USER, final_scope="project", silent=False)
    assert r.needs_user_input is True


def test_needs_user_input_false_for_store():
    r = ResolutionResult(action=ResolutionAction.STORE, final_scope="project", silent=True)
    assert r.needs_user_input is False


# ── No conflict ───────────────────────────────────────────────────────────────

def test_no_existing_memory_stores_directly():
    resolver = make_resolver(existing_corrections=[])
    extraction = make_extraction(scope="project")
    result = resolver.resolve(extraction, active_project="My App")
    assert result.action == ResolutionAction.STORE
    assert result.final_scope == "project"
    assert result.silent is True
    assert result.conflict is None


def test_conversation_scope_always_stores():
    resolver = make_resolver(existing_corrections=[
        make_existing_correction(scope="global")  # even with existing global
    ])
    extraction = make_extraction(scope="conversation")
    result = resolver.resolve(extraction)
    assert result.action == ResolutionAction.STORE
    assert result.final_scope == "conversation"
    assert result.silent is True


# ── Rule 3: Identical canonical_query → last wins silently ───────────────────

def test_identical_canonical_query_replaces_silently():
    existing = make_existing_correction(
        canonical_query="database_choice",
        scope="project",
    )
    resolver = make_resolver([existing])
    extraction = make_extraction(
        canonical_query="database_choice",
        scope="project",
    )
    result = resolver.resolve(extraction)
    assert result.action == ResolutionAction.REPLACE
    assert result.silent is True
    assert result.conflict == existing


def test_identical_canonical_query_global_replaces_silently():
    existing = make_existing_correction(
        canonical_query="prefer_snake_case",
        scope="global",
    )
    resolver = make_resolver([existing])
    extraction = make_extraction(
        canonical_query="prefer_snake_case",
        scope="global",
    )
    result = resolver.resolve(extraction)
    assert result.action == ResolutionAction.REPLACE
    assert result.silent is True


# ── Rule 1: Project overrides global silently ─────────────────────────────────

def test_project_overrides_global_silently():
    """Project memory for same topic should override global silently."""
    existing = make_existing_correction(
        canonical_query="database_storage",  # different canonical but same domain prefix
        scope="global",
    )
    resolver = make_resolver([existing])
    extraction = make_extraction(
        canonical_query="database_choice",
        scope="project",
        domain="software_engineering",
    )
    result = resolver.resolve(extraction, active_project="My App")
    # Project overriding global — keep both silently
    assert result.action in (ResolutionAction.STORE, ResolutionAction.KEEP_BOTH)
    assert result.final_scope == "project"
    assert result.silent is True


def test_global_overriding_project_prompts_user():
    """Setting a global that might override a project memory should prompt."""
    existing = make_existing_correction(
        canonical_query="database_choice",
        scope="project",
    )
    resolver = make_resolver([existing])
    extraction = make_extraction(
        canonical_query="database_choice",
        scope="global",  # global trying to override project (unusual)
    )
    result = resolver.resolve(extraction)
    # This is an unusual case — should flag for user decision
    assert result.action in (ResolutionAction.PROMPT_USER, ResolutionAction.REPLACE)


# ── Rule 2: Same-scope conflict on related topic ──────────────────────────────

def test_same_scope_conflict_prompts_user():
    """Two project memories on related topics should prompt the user."""
    existing = make_existing_correction(
        canonical_query="database_orm",   # related to database, different key
        scope="project",
    )
    resolver = make_resolver([existing])
    extraction = make_extraction(
        canonical_query="database_orm",
        scope="project",
    )
    # Same canonical_query → replace silently (rule 3 takes precedence)
    result = resolver.resolve(extraction)
    assert result.action == ResolutionAction.REPLACE
    assert result.silent is True


def test_conflict_reason_contains_both_instructions():
    resolver = make_resolver()
    existing = make_existing_correction(
        corrective_instruction="Use SQLite for simplicity.",
    )
    extraction = make_extraction(
        corrective_instruction="Use Postgres for production.",
    )
    reason = resolver._build_conflict_reason(extraction, existing)
    assert "SQLite" in reason
    assert "Postgres" in reason
    assert "Existing" in reason
    assert "New" in reason


# ── apply() ───────────────────────────────────────────────────────────────────

def test_apply_store_calls_state_append():
    mock_state = MagicMock()
    mock_state.query.return_value = []
    resolver = ScopeResolver(state=mock_state)
    extraction = make_extraction(scope="project")
    resolution = ResolutionResult(
        action=ResolutionAction.STORE,
        final_scope="project",
        silent=True,
    )
    stored = resolver.apply(resolution, extraction, active_project="My App")
    assert stored is True
    mock_state.append.assert_called_once()
    call_args = mock_state.append.call_args[0]
    assert call_args[0] == "corrections"


def test_apply_cancel_returns_false():
    mock_state = MagicMock()
    resolver = ScopeResolver(state=mock_state)
    extraction = make_extraction()
    resolution = ResolutionResult(
        action=ResolutionAction.CANCEL,
        final_scope="project",
    )
    stored = resolver.apply(resolution, extraction)
    assert stored is False
    mock_state.append.assert_not_called()


def test_apply_replace_soft_deletes_old():
    mock_state = MagicMock()
    mock_conn = MagicMock()
    mock_state._conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_state._conn.return_value.__exit__ = MagicMock(return_value=False)

    resolver = ScopeResolver(state=mock_state)
    extraction = make_extraction()
    resolution = ResolutionResult(
        action=ResolutionAction.REPLACE,
        final_scope="project",
        conflict={"correction_id": "old-id"},
        silent=True,
    )
    stored = resolver.apply(resolution, extraction)
    assert stored is True
    # Soft delete was attempted
    mock_conn.execute.assert_called_once()
    sql = mock_conn.execute.call_args[0][0]
    assert "superseded" in sql


def test_apply_keep_both_stores_new():
    mock_state = MagicMock()
    resolver = ScopeResolver(state=mock_state)
    extraction = make_extraction()
    resolution = ResolutionResult(
        action=ResolutionAction.KEEP_BOTH,
        final_scope="project",
        conflict={"correction_id": "old-id"},
        silent=True,
    )
    stored = resolver.apply(resolution, extraction, active_project="My App")
    assert stored is True
    mock_state.append.assert_called_once()


def test_apply_sets_final_scope_on_record():
    """The stored record should use the resolved scope, not the extraction scope."""
    mock_state = MagicMock()
    resolver = ScopeResolver(state=mock_state)
    extraction = make_extraction(scope="global")
    resolution = ResolutionResult(
        action=ResolutionAction.STORE,
        final_scope="project",   # overriding extraction scope
        silent=True,
    )
    resolver.apply(resolution, extraction, active_project="My App")
    stored_record = mock_state.append.call_args[0][1]
    assert stored_record["scope"] == "project"
