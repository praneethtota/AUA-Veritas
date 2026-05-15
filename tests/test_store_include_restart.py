"""Tests for StoreUtilityScorer, IncludeUtilityScorer, RestartPromptBuilder."""
import math
import time
import pytest
from unittest.mock import MagicMock

from core.store_utility import (
    StoreUtilityScorer,
    StoreDecision,
    StoreUtilityResult,
    THRESHOLD_AUTO_SAVE,
    THRESHOLD_REVIEW_CARD,
)
from core.include_utility import IncludeUtilityScorer, ScoredCorrection
from core.restart_prompt import RestartPromptBuilder, RestartPrompt, LAYER_ORDER
from core.memory_extractor import ExtractionResult


# ── Shared helpers ────────────────────────────────────────────────────────────

def make_extraction(**kwargs) -> ExtractionResult:
    defaults = dict(
        extraction_id="test-id",
        type="factual_correction",
        scope="project",
        corrective_instruction="Use Postgres not SQLite.",
        reason="Wrong DB.",
        canonical_query="database_choice",
        domain="software_engineering",
        confidence=0.95,
        decay_class="A",
        model_id="gpt-4o",
        query_preview="What database?",
        extracted_via="rules",
    )
    defaults.update(kwargs)
    return ExtractionResult(**defaults)


def make_correction(**kwargs) -> dict:
    defaults = dict(
        correction_id="c1",
        type="factual_correction",
        scope="project",
        corrective_instruction="Use Postgres not SQLite.",
        canonical_query="database_choice",
        domain="software_engineering",
        confidence=0.90,
        decay_class="A",
        pinned=False,
        created_at=time.time(),
    )
    defaults.update(kwargs)
    return defaults


# ═══════════════════════════════════════════════════════════════════════════════
# STORE UTILITY SCORER
# ═══════════════════════════════════════════════════════════════════════════════

class TestStoreUtilityScorer:

    @pytest.fixture
    def scorer(self):
        return StoreUtilityScorer()

    def test_returns_store_utility_result(self, scorer):
        extraction = make_extraction(confidence=0.95, type="factual_correction")
        result = scorer.score(extraction, user_message="No, that's wrong.")
        assert isinstance(result, StoreUtilityResult)
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.decision, StoreDecision)
        assert isinstance(result.breakdown, dict)

    def test_breakdown_has_all_keys(self, scorer):
        extraction = make_extraction()
        result = scorer.score(extraction, user_message="Wrong.")
        keys = {
            "correction_strength", "future_reuse", "project_relevance",
            "user_explicitness", "severity", "ambiguity", "sensitivity_risk"
        }
        assert keys.issubset(result.breakdown.keys())

    def test_high_confidence_factual_auto_saves(self, scorer):
        """Clear, confident factual correction with explicit language should auto-save."""
        extraction = make_extraction(
            type="factual_correction",
            confidence=0.95,
            scope="project",
        )
        result = scorer.score(
            extraction,
            # 'must' hits _EXPLICIT_PHRASES (+0.35) pushing score above 0.85
            user_message="This is wrong and you must use Postgres not SQLite.",
            active_project="My App",
        )
        assert result.decision == StoreDecision.AUTO_SAVE
        assert result.score >= THRESHOLD_AUTO_SAVE
        assert result.should_store is True
        assert result.is_auto is True

    def test_failure_pattern_scores_high(self, scorer):
        """Repeated failures always score high."""
        extraction = make_extraction(
            type="failure_pattern",
            confidence=0.90,
            scope="project",
        )
        result = scorer.score(
            extraction,
            user_message="You keep suggesting SQLite. Stop.",
            active_project="My App",
        )
        assert result.score >= THRESHOLD_REVIEW_CARD
        assert result.should_store is True

    def test_preference_scores_lower(self, scorer):
        """Vague preferences score lower than factual corrections."""
        factual = scorer.score(
            make_extraction(type="factual_correction", confidence=0.95),
            user_message="No that's wrong.",
        )
        pref = scorer.score(
            make_extraction(type="preference", confidence=0.70),
            user_message="I sort of prefer briefer answers.",
        )
        assert factual.score > pref.score

    def test_ambiguous_message_lowers_score(self, scorer):
        """Hedged, ambiguous corrections should score lower."""
        clear = scorer.score(
            make_extraction(confidence=0.95),
            user_message="Use Postgres not SQLite.",
        )
        hedged = scorer.score(
            make_extraction(confidence=0.95),
            user_message="Maybe sometimes possibly use Postgres, I think, kind of.",
        )
        assert clear.score > hedged.score

    def test_sensitive_content_penalized(self, scorer):
        """Messages containing passwords or credentials should score lower."""
        normal = scorer.score(
            make_extraction(),
            user_message="Use Postgres not SQLite.",
        )
        sensitive = scorer.score(
            make_extraction(),
            user_message="The password is secret123 for the database.",
        )
        assert normal.score > sensitive.score

    def test_global_scope_higher_than_conversation(self, scorer):
        """Global memories score higher than conversation-only memories."""
        global_ext = make_extraction(scope="global")
        conv_ext = make_extraction(scope="conversation")
        global_result = scorer.score(global_ext, user_message="Always use async.")
        conv_result   = scorer.score(conv_ext,   user_message="Use async here.")
        assert global_result.score > conv_result.score

    def test_decision_thresholds(self, scorer):
        """Test that decision boundaries are correct."""
        assert THRESHOLD_AUTO_SAVE   == 0.85
        assert THRESHOLD_REVIEW_CARD == 0.60
        assert THRESHOLD_AUTO_SAVE   > THRESHOLD_REVIEW_CARD

    def test_should_store_true_for_auto_and_review(self, scorer):
        auto   = StoreUtilityResult(score=0.90, decision=StoreDecision.AUTO_SAVE,   breakdown={})
        review = StoreUtilityResult(score=0.70, decision=StoreDecision.REVIEW_CARD, breakdown={})
        discard = StoreUtilityResult(score=0.40, decision=StoreDecision.DISCARD,    breakdown={})
        assert auto.should_store   is True
        assert review.should_store is True
        assert discard.should_store is False

    def test_score_clamped_to_0_1(self, scorer):
        """Score must never go below 0 or above 1."""
        for conf in [0.0, 0.5, 1.0]:
            for corr_type in ["factual_correction", "preference", "failure_pattern"]:
                extraction = make_extraction(confidence=conf, type=corr_type)
                result = scorer.score(extraction)
                assert 0.0 <= result.score <= 1.0, \
                    f"score={result.score} out of range for conf={conf}, type={corr_type}"


# ═══════════════════════════════════════════════════════════════════════════════
# INCLUDE UTILITY SCORER
# ═══════════════════════════════════════════════════════════════════════════════

class TestIncludeUtilityScorer:

    @pytest.fixture
    def scorer(self):
        return IncludeUtilityScorer()

    def test_returns_scored_correction(self, scorer):
        c = make_correction()
        result = scorer.score(c, query="What database?", domain="software_engineering")
        assert isinstance(result, ScoredCorrection)
        assert 0.0 <= result.include_score <= 1.0
        assert result.correction is c

    def test_breakdown_has_all_keys(self, scorer):
        c = make_correction()
        result = scorer.score(c, query="What database?", domain="software_engineering")
        keys = {
            "relevance", "failure_prevention", "importance",
            "recency", "confidence", "pinned", "staleness", "token_cost"
        }
        assert keys.issubset(result.breakdown.keys())

    def test_domain_match_boosts_relevance(self, scorer):
        matching = make_correction(domain="software_engineering")
        other    = make_correction(domain="mathematics")
        r1 = scorer.score(matching, "What database?", "software_engineering")
        r2 = scorer.score(other,    "What database?", "software_engineering")
        assert r1.breakdown["relevance"] > r2.breakdown["relevance"]

    def test_failure_pattern_has_highest_prevention(self, scorer):
        fp  = make_correction(type="failure_pattern")
        fc  = make_correction(type="factual_correction")
        pref = make_correction(type="preference")
        r_fp   = scorer.score(fp,   "query", "software_engineering")
        r_fc   = scorer.score(fc,   "query", "software_engineering")
        r_pref = scorer.score(pref, "query", "software_engineering")
        assert r_fp.breakdown["failure_prevention"] >= r_fc.breakdown["failure_prevention"]
        assert r_fc.breakdown["failure_prevention"] > r_pref.breakdown["failure_prevention"]

    def test_pinned_correction_gets_boost(self, scorer):
        pinned   = make_correction(pinned=True)
        unpinned = make_correction(pinned=False)
        r1 = scorer.score(pinned,   "query", "software_engineering")
        r2 = scorer.score(unpinned, "query", "software_engineering")
        assert r1.breakdown["pinned"] == 1.0
        assert r2.breakdown["pinned"] == 0.0
        assert r1.include_score > r2.include_score

    def test_permanent_decay_never_stale(self, scorer):
        old_correction = make_correction(
            decay_class="A",
            created_at=time.time() - (365 * 5 * 86400),  # 5 years old
        )
        result = scorer.score(old_correction, "query", "software_engineering")
        assert result.breakdown["staleness"] == 0.0

    def test_fast_decay_class_d_becomes_stale(self, scorer):
        very_old = make_correction(
            decay_class="D",
            created_at=time.time() - (365 * 86400),  # 1 year old, threshold=180 days
        )
        result = scorer.score(very_old, "query", "general")
        assert result.breakdown["staleness"] > 0.0

    def test_keyword_overlap_boosts_relevance(self, scorer):
        with_overlap = make_correction(
            canonical_query="database_postgres_choice",
            corrective_instruction="Use Postgres not SQLite for the database.",
        )
        no_overlap = make_correction(
            canonical_query="code_style_preference",
            corrective_instruction="Use snake_case for variable names.",
        )
        r1 = scorer.score(with_overlap, "What database should I use?", "software_engineering")
        r2 = scorer.score(no_overlap,   "What database should I use?", "software_engineering")
        assert r1.breakdown["relevance"] > r2.breakdown["relevance"]

    def test_long_instruction_has_higher_token_cost(self, scorer):
        short = make_correction(corrective_instruction="Use Postgres.")
        long  = make_correction(corrective_instruction=" ".join(["word"] * 150))
        r1 = scorer.score(short, "query", "software_engineering")
        r2 = scorer.score(long,  "query", "software_engineering")
        assert r2.breakdown["token_cost"] > r1.breakdown["token_cost"]

    def test_select_returns_empty_for_no_corrections(self, scorer):
        result = scorer.select("query", "software_engineering", corrections=[])
        assert result == []

    def test_select_filters_superseded(self, scorer):
        corrections = [
            make_correction(scope="superseded", type="factual_correction"),
            make_correction(type="factual_correction"),
        ]
        result = scorer.select("query", "software_engineering", corrections=corrections)
        assert len(result) == 1

    def test_select_respects_max_corrections(self, scorer):
        corrections = [make_correction(correction_id=str(i)) for i in range(10)]
        result = scorer.select("query", "software_engineering", corrections, max_corrections=3)
        assert len(result) <= 3

    def test_select_returns_highest_scoring_first(self, scorer):
        corrections = [
            make_correction(type="failure_pattern", domain="software_engineering", pinned=True),
            make_correction(type="preference", domain="mathematics"),
        ]
        result = scorer.select("database query", "software_engineering", corrections)
        assert len(result) >= 1
        # First result should be from software_engineering (domain match + type)
        if len(result) >= 2:
            r0 = scorer.score(result[0], "database query", "software_engineering")
            r1 = scorer.score(result[1], "database query", "software_engineering")
            assert r0.include_score >= r1.include_score

    def test_select_applies_min_score_filter(self, scorer):
        """Corrections below min_score threshold are excluded."""
        very_irrelevant = make_correction(
            domain="mathematics",
            type="preference",
            confidence=0.30,
            decay_class="D",
            created_at=time.time() - (200 * 86400),  # old and stale
        )
        result = scorer.select(
            "Write a Python function",
            "software_engineering",
            [very_irrelevant],
            min_score=0.80,
        )
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# RESTART PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def make_state_with_corrections(corrections: list[dict]) -> MagicMock:
    """Create a mocked VeritasState returning the given corrections."""
    mock_state = MagicMock()

    def mock_query(table, filters=None, limit=100):
        if table != "corrections":
            return []
        filters = filters or {}
        result = []
        for c in corrections:
            if all(c.get(k) == v for k, v in filters.items()):
                result.append(c)
        return result[:limit]

    mock_state.query.side_effect = mock_query
    return mock_state


class TestRestartPromptBuilder:

    @pytest.fixture
    def builder_empty(self):
        return RestartPromptBuilder(state=make_state_with_corrections([]))

    def test_empty_returns_restart_prompt(self, builder_empty):
        result = builder_empty.build()
        assert isinstance(result, RestartPrompt)
        assert result.item_count == 0
        assert "No memories" in result.veritas_format or "No project" in result.veritas_format

    def test_empty_ide_format_contains_helpful_message(self, builder_empty):
        result = builder_empty.build(active_project="My App")
        assert "My App" in result.ide_format or "no project" in result.ide_format.lower() or "No project" in result.ide_format

    def test_with_corrections_returns_correct_count(self):
        corrections = [
            make_correction(type="factual_correction",     scope="project", user_id="local", correction_id="1"),
            make_correction(type="project_decision",       scope="project", user_id="local", correction_id="2",
                            canonical_query="electron_choice",
                            corrective_instruction="Use Electron for the desktop app."),
            make_correction(type="persistent_instruction", scope="global",  user_id="local", correction_id="3",
                            canonical_query="type_hints",
                            corrective_instruction="Always add type hints to Python functions."),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="My App")
        assert result.item_count > 0

    def test_veritas_format_contains_layer_headers(self):
        corrections = [
            make_correction(type="factual_correction", scope="project", user_id="local", correction_id="1"),
            make_correction(type="preference", scope="global", user_id="local", correction_id="2",
                            canonical_query="style_pref",
                            corrective_instruction="Prefer concise explanations."),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="My App", include_global=True)
        # Veritas format should have layer structure
        assert "===" in result.veritas_format

    def test_ide_format_starts_with_before_answering(self):
        corrections = [
            make_correction(type="factual_correction", scope="project", user_id="local",
                            correction_id="1", corrective_instruction="Use Postgres not SQLite."),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="My App")
        assert result.ide_format.startswith("Before answering")

    def test_ide_format_contains_numbered_items(self):
        corrections = [
            make_correction(type="factual_correction", scope="project", user_id="local",
                            correction_id="1", corrective_instruction="Use Postgres not SQLite."),
            make_correction(type="persistent_instruction", scope="project", user_id="local",
                            correction_id="2", canonical_query="type_hints",
                            corrective_instruction="Always add type hints."),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="My App")
        assert "1." in result.ide_format
        assert "2." in result.ide_format

    def test_project_name_appears_in_output(self):
        corrections = [
            make_correction(type="factual_correction", scope="project", user_id="local",
                            correction_id="1", corrective_instruction="Use Postgres."),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="AUA-Veritas")
        assert "AUA-Veritas" in result.veritas_format or "AUA-Veritas" in result.ide_format

    def test_superseded_corrections_excluded(self):
        corrections = [
            make_correction(scope="superseded", user_id="local", correction_id="1",
                            corrective_instruction="Old instruction that was superseded."),
            make_correction(scope="project", user_id="local", correction_id="2",
                            corrective_instruction="Use Postgres not SQLite."),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="My App")
        assert "Old instruction" not in result.veritas_format
        assert "Old instruction" not in result.ide_format

    def test_layer_order_in_ide_format(self):
        """Preferences come before factual corrections in the output."""
        corrections = [
            make_correction(type="factual_correction", scope="project", user_id="local",
                            correction_id="1", corrective_instruction="Factual: Use Postgres."),
            make_correction(type="preference", scope="global", user_id="local",
                            correction_id="2", canonical_query="style",
                            corrective_instruction="Preference: Concise answers."),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="My App", include_global=True)
        # In IDE format, preferences (layer 1) should appear before factual (layer 5)
        pref_pos    = result.ide_format.find("Concise")
        factual_pos = result.ide_format.find("Postgres")
        if pref_pos != -1 and factual_pos != -1:
            assert pref_pos < factual_pos

    def test_no_duplicate_corrections(self):
        """Same canonical_query should not appear twice."""
        corrections = [
            make_correction(scope="project", user_id="local", correction_id="1",
                            canonical_query="database_choice",
                            corrective_instruction="Use Postgres. (project)"),
            make_correction(scope="global", user_id="local", correction_id="2",
                            canonical_query="database_choice",  # same key
                            corrective_instruction="Use Postgres. (global)"),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="My App", include_global=True)
        # One version should appear, not both
        count = result.ide_format.count("Use Postgres")
        assert count == 1

    def test_layer_counts_populated(self):
        corrections = [
            make_correction(type="factual_correction", scope="project", user_id="local",
                            correction_id="1", corrective_instruction="Use Postgres."),
            make_correction(type="project_decision", scope="project", user_id="local",
                            correction_id="2", canonical_query="electron",
                            corrective_instruction="Use Electron."),
        ]
        builder = RestartPromptBuilder(state=make_state_with_corrections(corrections))
        result = builder.build(active_project="My App")
        assert isinstance(result.layer_counts, dict)
        assert result.layer_counts.get("factual_correction", 0) >= 1

    def test_result_has_generated_at(self):
        builder = RestartPromptBuilder(state=make_state_with_corrections([]))
        result = builder.build()
        assert result.generated_at > 0
        assert result.generated_at <= time.time()
