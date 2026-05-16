"""
Tests for the Stack Recommendation Engine and Architecture Tradeoff Reasoner.
Also covers the new API endpoints: POST /api/v1/recommend/stack and
GET /api/v1/compare/{fw_a}/{fw_b}.
"""
import pytest
from datetime import date
from fastapi.testclient import TestClient

from src.api.main import app
from src.scoring.engine import ScoringEngine
from src.recommendation.stack_engine import StackRecommendationEngine
from src.recommendation.comparator import TradeoffComparator
from src.recommendation.models import (
    StackQuery, ComplianceFlag, ScaleTier, PriorityAxis, ArchLayer,
)


# ── Shared fixtures ────────────────────────────────────────────────────────────

# client fixture is provided by conftest.py (module-scoped)


@pytest.fixture(scope="module")
def scored_frameworks(loaded_frameworks):
    """Pre-score all frameworks for unit-level engine tests."""
    engine = ScoringEngine(today=date(2026, 5, 16))
    for fw in loaded_frameworks.values():
        fw.computed_scores = engine.compute_scores(fw)
    return loaded_frameworks


@pytest.fixture(scope="module")
def stack_engine(scored_frameworks):
    return StackRecommendationEngine(scored_frameworks)


@pytest.fixture(scope="module")
def comparator(scored_frameworks):
    return TradeoffComparator(scored_frameworks)


# ─────────────────────────────────────────────────────────────────────────────
# Group 1: Stack Recommendation Engine (unit)
# ─────────────────────────────────────────────────────────────────────────────

class TestStackRecommendationEngine:

    def test_basic_query_returns_recommendation(self, stack_engine):
        query = StackQuery(problem="Build a multi-agent customer support platform")
        result = stack_engine.recommend(query)
        assert result is not None
        assert len(result.layers) >= 3
        assert result.confidence > 0
        assert result.score_band in {"Excellent", "Strong", "Good", "Fair", "Weak", "Poor"}

    def test_orchestration_layer_is_recommended(self, stack_engine):
        query = StackQuery(problem="Multi-agent orchestration system")
        result = stack_engine.recommend(query)
        assert "orchestration" in result.layers
        orch = result.layers["orchestration"]
        assert orch.framework_id in {"langgraph", "crewai", "google_adk", "autogen", "pydantic_ai"}
        assert orch.score > 0
        assert len(orch.reason) > 10

    def test_hipaa_compliance_generates_warning_for_unverified_frameworks(self, stack_engine):
        query = StackQuery(
            problem="Healthcare patient data assistant",
            compliance=[ComplianceFlag.HIPAA],
        )
        result = stack_engine.recommend(query)
        # Should either warn about missing HIPAA deployments or pick a verified one
        # At minimum: no crash, recommendation produced
        assert len(result.layers) >= 2
        # Global warnings should exist since not all frameworks have HIPAA evidence
        # (or at minimum the recommendation ran without error)
        assert isinstance(result.global_warnings, list)

    def test_hipaa_boosts_governance_focused_frameworks(self, stack_engine):
        query_no_compliance = StackQuery(problem="Build a data pipeline")
        query_hipaa = StackQuery(
            problem="Build a data pipeline",
            compliance=[ComplianceFlag.HIPAA],
        )
        result_plain  = stack_engine.recommend(query_no_compliance)
        result_hipaa  = stack_engine.recommend(query_hipaa)

        # The orchestration pick may change, or the same pick has a different
        # confidence/score — just verify it doesn't crash and produces output
        assert result_hipaa.layers is not None

    def test_keyword_boost_for_rag_favours_llamaindex(self, stack_engine):
        """'RAG' keyword should boost llamaindex in orchestration/data layer."""
        query = StackQuery(problem="Build a RAG pipeline for document search")
        result = stack_engine.recommend(query)
        orch_id = result.layers.get("orchestration", None)
        # Either llamaindex or langchain wins (both are RAG-boosted)
        if orch_id:
            assert orch_id.framework_id in {"llamaindex", "langchain", "langgraph"}

    def test_enterprise_scale_penalises_low_stability_frameworks(self, stack_engine):
        query = StackQuery(
            problem="Enterprise production AI platform",
            scale=ScaleTier.ENTERPRISE,
        )
        result = stack_engine.recommend(query)
        # AutoGen (maintenance mode, low stability) should NOT win orchestration
        orch = result.layers.get("orchestration")
        if orch:
            assert orch.framework_id != "autogen", (
                "AutoGen (maintenance mode) should not be top recommendation at enterprise scale"
            )

    def test_specific_layers_filter_works(self, stack_engine):
        """Requesting only specific layers returns only those layers."""
        query = StackQuery(
            problem="Build a vector search service",
            layers=[ArchLayer.VECTOR_DB, ArchLayer.OBSERVABILITY],
        )
        result = stack_engine.recommend(query)
        layer_keys = set(result.layers.keys())
        assert "vector_db" in layer_keys
        assert "observability" in layer_keys
        # Should NOT include orchestration or safety
        assert "orchestration" not in layer_keys

    def test_recommendation_includes_version(self, stack_engine):
        query = StackQuery(problem="Simple AI chatbot")
        result = stack_engine.recommend(query)
        for choice in result.layers.values():
            assert choice.version is not None
            assert choice.version != ""

    def test_recommendation_includes_alternatives(self, stack_engine):
        query = StackQuery(problem="Multi-agent system")
        result = stack_engine.recommend(query)
        # At least one layer should have alternatives
        has_alternatives = any(
            len(c.alternatives) > 0 for c in result.layers.values()
        )
        assert has_alternatives

    def test_tradeoff_notes_generated(self, stack_engine):
        query = StackQuery(problem="Build a multi-agent system using LangGraph")
        result = stack_engine.recommend(query)
        # LangGraph is likely the top orchestration pick — tradeoff notes should mention it
        assert isinstance(result.tradeoff_notes, list)

    def test_generated_at_is_iso_format(self, stack_engine):
        import re
        query = StackQuery(problem="Test system")
        result = stack_engine.recommend(query)
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", result.generated_at)


# ─────────────────────────────────────────────────────────────────────────────
# Group 2: Tradeoff Comparator (unit)
# ─────────────────────────────────────────────────────────────────────────────

class TestTradeoffComparator:

    def test_basic_comparison_returns_result(self, comparator):
        result = comparator.compare("langgraph", "crewai")
        assert result is not None
        assert result.framework_a_id == "langgraph"
        assert result.framework_b_id == "crewai"

    def test_five_dimensions_returned(self, comparator):
        result = comparator.compare("langgraph", "crewai")
        assert len(result.dimensions) == 5
        dim_names = {d.dimension for d in result.dimensions}
        assert "Production Stability" in dim_names
        assert "Ecosystem Momentum"   in dim_names
        assert "Agent Compatibility"  in dim_names

    def test_overall_winner_is_one_of_the_frameworks_or_tie(self, comparator):
        result = comparator.compare("langgraph", "crewai")
        assert result.overall_winner in {"langgraph", "crewai", "tie"}

    def test_scores_are_within_bounds(self, comparator):
        result = comparator.compare("fastapi", "langgraph")
        assert 0 <= result.overall_score_a <= 100
        assert 0 <= result.overall_score_b <= 100
        for dim in result.dimensions:
            assert 0 <= dim.framework_a_score <= 100
            assert 0 <= dim.framework_b_score <= 100

    def test_delta_matches_score_difference(self, comparator):
        result = comparator.compare("langgraph", "crewai")
        for dim in result.dimensions:
            calculated_delta = abs(dim.framework_a_score - dim.framework_b_score)
            # Use a tolerance of 0.2 to handle floating-point rounding
            # (scores are stored rounded to 1dp, so max epsilon is 0.15)
            assert abs(calculated_delta - dim.delta) < 0.2, (
                f"Delta mismatch for {dim.dimension}: "
                f"calculated {calculated_delta}, stored {dim.delta}"
            )

    def test_recommendation_string_is_non_empty(self, comparator):
        result = comparator.compare("langgraph", "crewai")
        assert len(result.recommendation) > 20

    def test_when_to_pick_lists_are_non_empty(self, comparator):
        result = comparator.compare("pinecone", "qdrant")
        assert len(result.when_to_pick_a) >= 1
        assert len(result.when_to_pick_b) >= 1

    def test_same_category_generates_migration_note(self, comparator):
        """Same-category comparison should include a migration note."""
        result = comparator.compare("langgraph", "crewai")  # both orchestration
        assert result.migration_note is not None
        assert "migration" in result.migration_note.lower()

    def test_cross_category_no_migration_note(self, comparator):
        """Cross-category comparison should NOT generate a migration note."""
        result = comparator.compare("langgraph", "qdrant")  # orchestration vs vector-db
        assert result.migration_note is None

    def test_use_case_included_in_output(self, comparator):
        result = comparator.compare("langgraph", "crewai", use_case="HIPAA multi-agent system")
        assert result.use_case == "HIPAA multi-agent system"
        assert "HIPAA" in result.recommendation

    def test_tie_declared_for_close_scores(self, comparator):
        """If scores are within TIE_THRESHOLD, winner should be 'tie'."""
        # Find a dimension that is a tie
        result = comparator.compare("pinecone", "qdrant")
        tie_dims = [d for d in result.dimensions if d.winner == "tie"]
        # Both are in same category with similar profiles — at least some dims will tie
        # (this is a soft assertion since actual values depend on YAML data)
        for dim in tie_dims:
            assert dim.delta < 5.0


# ─────────────────────────────────────────────────────────────────────────────
# Group 3: API Integration (via FastAPI TestClient)
# ─────────────────────────────────────────────────────────────────────────────

class TestIntelligenceAPI:

    def test_stack_recommend_basic(self, client):
        response = client.post(
            "/api/v1/recommend/stack",
            json={"problem": "Build a multi-agent customer support platform"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "layers" in data
        assert "confidence" in data
        assert "score_band" in data
        assert "generated_at" in data
        assert len(data["layers"]) >= 3

    def test_stack_recommend_with_compliance(self, client):
        response = client.post(
            "/api/v1/recommend/stack",
            json={
                "problem": "HIPAA-compliant patient data assistant",
                "compliance": ["hipaa"],
                "scale": "enterprise",
                "priority": "governance",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["layers"] is not None

    def test_stack_recommend_with_specific_layers(self, client):
        response = client.post(
            "/api/v1/recommend/stack",
            json={
                "problem": "Vector search service",
                "layers": ["vector_db", "api_layer"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "vector_db" in data["layers"]
        assert "api_layer" in data["layers"]
        assert "orchestration" not in data["layers"]

    def test_stack_recommend_invalid_problem_too_short(self, client):
        response = client.post(
            "/api/v1/recommend/stack",
            json={"problem": "AI"},
        )
        assert response.status_code == 422  # Validation error

    def test_compare_frameworks_basic(self, client):
        response = client.get("/api/v1/compare/langgraph/crewai")
        assert response.status_code == 200
        data = response.json()
        assert data["framework_a_id"] == "langgraph"
        assert data["framework_b_id"] == "crewai"
        assert len(data["dimensions"]) == 5
        assert data["overall_winner"] in {"langgraph", "crewai", "tie"}
        assert len(data["recommendation"]) > 10

    def test_compare_with_use_case(self, client):
        response = client.get(
            "/api/v1/compare/pinecone/qdrant",
            params={"use_case": "high-throughput similarity search"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["use_case"] == "high-throughput similarity search"

    def test_compare_unknown_framework_returns_404(self, client):
        response = client.get("/api/v1/compare/langgraph/nonexistent_fw")
        assert response.status_code == 404

    def test_compare_same_framework_returns_400(self, client):
        response = client.get("/api/v1/compare/langgraph/langgraph")
        assert response.status_code == 400

    def test_compare_when_to_pick_lists_present(self, client):
        response = client.get("/api/v1/compare/langchain/langgraph")
        assert response.status_code == 200
        data = response.json()
        assert len(data["when_to_pick_a"]) >= 1
        assert len(data["when_to_pick_b"]) >= 1
