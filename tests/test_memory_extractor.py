"""Tests for MemoryExtractor — rule-based and LLM extraction paths."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.memory_extractor import (
    ExtractionResult,
    MemoryExtractor,
    CORRECTION_TYPES,
    KNOWN_DOMAINS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def extractor_no_backends():
    """Extractor with no backends — rule-based only."""
    return MemoryExtractor(backends={})


@pytest.fixture
def extractor_with_judge():
    """Extractor with a mocked judge backend."""
    mock_backend = AsyncMock()
    return MemoryExtractor(backends={"gpt-4o-mini": mock_backend}), mock_backend


# ── ExtractionResult ──────────────────────────────────────────────────────────

def make_result(**kwargs) -> ExtractionResult:
    defaults = dict(
        extraction_id="test-id",
        type="factual_correction",
        scope="project",
        corrective_instruction="Use Postgres not SQLite.",
        reason="Recommended SQLite after user specified Postgres.",
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


def test_score_delta_factual_correction():
    r = make_result(type="factual_correction", confidence=0.95)
    assert r._score_delta() == -round(0.95 * 15)
    assert r._score_delta() < 0


def test_score_delta_failure_pattern():
    r = make_result(type="failure_pattern", confidence=0.80)
    assert r._score_delta() == -round(0.80 * 10)


def test_score_delta_instruction_no_penalty():
    r = make_result(type="persistent_instruction", confidence=0.90)
    assert r._score_delta() == 0


def test_score_delta_preference_no_penalty():
    r = make_result(type="preference", confidence=0.80)
    assert r._score_delta() == 0


def test_to_correction_record_has_required_fields():
    r = make_result()
    record = r.to_correction_record(active_project="My App")
    required = {
        "correction_id", "model_id", "score_delta", "reason",
        "corrective_instruction", "scope", "domain", "canonical_query",
        "query_preview", "confidence", "decay_class",
    }
    assert required.issubset(record.keys())
    assert record["active_project"] == "My App"


def test_to_audit_event_has_required_fields():
    r = make_result()
    event = r.to_audit_event(score_before=72, score_after=58)
    assert event["score_before"] == 72
    assert event["score_after"] == 58
    assert event["correction_stored"] is True
    assert event["model_id"] == "gpt-4o"
    assert "audit_id" in event


# ── Rule-based extraction ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rules_factual_correction(extractor_no_backends):
    result = await extractor_no_backends.extract(
        user_message="No, that's wrong. Use Postgres not SQLite.",
        original_query="What database should I use for production?",
        ai_response="I recommend SQLite for simplicity.",
        model_id="gpt-4o",
    )
    assert result is not None
    assert result.type == "factual_correction"
    assert result.extracted_via == "rules"
    assert result.model_id == "gpt-4o"
    assert "postgres" in result.corrective_instruction.lower() or "wrong" in result.corrective_instruction.lower()


@pytest.mark.asyncio
async def test_rules_persistent_instruction(extractor_no_backends):
    result = await extractor_no_backends.extract(
        user_message="Going forward always add type hints to every function.",
        original_query="Write a function to sort a list.",
        ai_response="def sort_list(items): return sorted(items)",
        model_id="gpt-4o",
    )
    assert result is not None
    assert result.type == "persistent_instruction"
    assert result.scope == "global"


@pytest.mark.asyncio
async def test_rules_project_decision(extractor_no_backends):
    result = await extractor_no_backends.extract(
        user_message="We decided to use Postgres for this project.",
        original_query="What database should I use?",
        ai_response="SQLite is fine for small projects.",
        model_id="claude-sonnet-4-6",
        active_project="My App",
    )
    assert result is not None
    assert result.type == "project_decision"
    assert result.scope == "project"


@pytest.mark.asyncio
async def test_rules_preference(extractor_no_backends):
    result = await extractor_no_backends.extract(
        user_message="I prefer concise explanations without examples.",
        original_query="Explain async/await.",
        ai_response="Here is a long explanation with many examples...",
        model_id="gpt-4o",
    )
    assert result is not None
    assert result.type == "preference"
    assert result.scope == "global"


@pytest.mark.asyncio
async def test_rules_failure_pattern(extractor_no_backends):
    result = await extractor_no_backends.extract(
        user_message="You keep suggesting SQLite. Stop doing that.",
        original_query="Storage options for the API?",
        ai_response="SQLite would work well here.",
        model_id="gpt-4o",
    )
    assert result is not None
    assert result.type == "failure_pattern"


@pytest.mark.asyncio
async def test_rules_empty_message_returns_none(extractor_no_backends):
    result = await extractor_no_backends.extract(
        user_message="",
        original_query="What is merge sort?",
        ai_response="Merge sort is...",
        model_id="gpt-4o",
    )
    assert result is None


@pytest.mark.asyncio
async def test_rules_whitespace_returns_none(extractor_no_backends):
    result = await extractor_no_backends.extract(
        user_message="   ",
        original_query="What is merge sort?",
        ai_response="Merge sort is...",
        model_id="gpt-4o",
    )
    assert result is None


def test_rules_canonical_query_is_snake_case(extractor_no_backends):
    canonical = extractor_no_backends._extract_via_rules(
        "No, use Postgres.",
        "What database should I use for production?",
        "gpt-4o",
        None,
        "What database...",
    ).canonical_query
    # No spaces, no special chars, all lowercase
    assert " " not in canonical
    assert canonical == canonical.lower()
    assert all(c.isalnum() or c == "_" for c in canonical)


def test_rules_canonical_query_max_60_chars(extractor_no_backends):
    long_query = "This is a very long query about many different topics " * 5
    result = extractor_no_backends._extract_via_rules(
        "Wrong.", long_query, "gpt-4o", None, "This is..."
    )
    assert len(result.canonical_query) <= 60


# ── Domain detection ──────────────────────────────────────────────────────────

def test_domain_software_engineering(extractor_no_backends):
    d = extractor_no_backends._guess_domain("use async SQLAlchemy for the database")
    assert d == "software_engineering"


def test_domain_mathematics(extractor_no_backends):
    d = extractor_no_backends._guess_domain("the complexity of this algorithm is O(n log n)")
    assert d == "mathematics"


def test_domain_legal(extractor_no_backends):
    d = extractor_no_backends._guess_domain("under contract law this clause is invalid")
    assert d == "legal"


def test_domain_general_fallback(extractor_no_backends):
    d = extractor_no_backends._guess_domain("this is a general statement about things")
    assert d == "general"


# ── LLM extraction path ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_extraction_happy_path(extractor_with_judge):
    extractor, mock_backend = extractor_with_judge
    mock_backend.complete.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "type": "factual_correction",
            "scope": "project",
            "corrective_instruction": "Use Postgres with JSONB for this project.",
            "reason": "Recommended SQLite after user specified Postgres.",
            "canonical_query": "database_storage_choice",
            "domain": "software_engineering",
            "confidence": 0.95,
            "decay_class": "A",
        })}}]
    }
    result = await extractor.extract(
        user_message="No, use Postgres not SQLite.",
        original_query="What database should we use?",
        ai_response="I recommend SQLite for simplicity.",
        model_id="gpt-4o",
        active_project="My App",
    )
    assert result is not None
    assert result.type == "factual_correction"
    assert result.domain == "software_engineering"
    assert result.confidence == 0.95
    assert "llm" in result.extracted_via


@pytest.mark.asyncio
async def test_llm_extraction_falls_back_on_json_error(extractor_with_judge):
    extractor, mock_backend = extractor_with_judge
    mock_backend.complete.return_value = {
        "choices": [{"message": {"content": "This is not valid JSON at all."}}]
    }
    # Should fall back to rule-based
    result = await extractor.extract(
        user_message="No, use Postgres.",
        original_query="What database?",
        ai_response="Use SQLite.",
        model_id="gpt-4o",
    )
    assert result is not None
    assert result.extracted_via == "rules"


@pytest.mark.asyncio
async def test_llm_extraction_falls_back_on_backend_error(extractor_with_judge):
    extractor, mock_backend = extractor_with_judge
    mock_backend.complete.side_effect = Exception("API timeout")
    result = await extractor.extract(
        user_message="No, use Postgres.",
        original_query="What database?",
        ai_response="Use SQLite.",
        model_id="gpt-4o",
    )
    assert result is not None
    assert result.extracted_via == "rules"


def test_llm_parse_strips_markdown_fences(extractor_no_backends):
    raw = '```json\n{"type":"factual_correction","scope":"global","corrective_instruction":"Use X.","reason":"Wrong.","canonical_query":"x","domain":"general","confidence":0.9,"decay_class":"A"}\n```'
    result = extractor_no_backends._parse_llm_response(
        raw, "gpt-4o", "Query?", "llm:test"
    )
    assert result is not None
    assert result.type == "factual_correction"


def test_llm_parse_invalid_type_defaults_to_factual(extractor_no_backends):
    raw = json.dumps({
        "type": "totally_made_up_type",
        "scope": "global",
        "corrective_instruction": "Use X.",
        "reason": "Wrong.",
        "canonical_query": "x",
        "domain": "general",
        "confidence": 0.9,
        "decay_class": "A",
    })
    result = extractor_no_backends._parse_llm_response(
        raw, "gpt-4o", "Query?", "llm:test"
    )
    assert result is not None
    assert result.type == "factual_correction"


def test_llm_parse_missing_fields_returns_none(extractor_no_backends):
    raw = json.dumps({"type": "factual_correction"})  # missing required fields
    result = extractor_no_backends._parse_llm_response(
        raw, "gpt-4o", "Query?", "llm:test"
    )
    assert result is None


# ── Judge model selection ─────────────────────────────────────────────────────

def test_pick_judge_prefers_gemini_flash(extractor_no_backends):
    extractor_no_backends._backends = {
        "gpt-4o": MagicMock(),
        "gemini-2.0-flash": MagicMock(),
        "gpt-4o-mini": MagicMock(),
    }
    judge = extractor_no_backends._pick_judge(exclude="gpt-4o")
    assert judge == "gemini-2.0-flash"


def test_pick_judge_falls_back_to_mini(extractor_no_backends):
    extractor_no_backends._backends = {
        "gpt-4o": MagicMock(),
        "gpt-4o-mini": MagicMock(),
    }
    judge = extractor_no_backends._pick_judge(exclude="gpt-4o")
    assert judge == "gpt-4o-mini"


def test_pick_judge_excludes_penalized_model(extractor_no_backends):
    extractor_no_backends._backends = {
        "gpt-4o-mini": MagicMock(),
    }
    judge = extractor_no_backends._pick_judge(exclude="gpt-4o-mini")
    assert judge is None  # only model is excluded


def test_pick_judge_no_backends():
    e = MemoryExtractor(backends={})
    assert e._pick_judge(exclude="gpt-4o") is None
