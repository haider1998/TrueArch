"""Phase B2: the context optimizer must be active in the live serving path,
not only in the benchmark. These tests exercise it through the MCP tools.
"""
import json

import pytest

from src.mcp.server import quick_context, recommend_ai_stack


class TestQuickContextUsesOptimizer:

    def test_returns_optimized_context_and_intent(self):
        result = quick_context(problem="Build a multi-agent customer support platform")
        assert "optimized_context" in result
        assert "intent" in result
        assert "estimated_tokens" in result
        # optimized_context is a JSON string produced by compress_context
        parsed = json.loads(result["optimized_context"])
        assert isinstance(parsed, list)

    def test_respects_token_budget(self):
        result = quick_context(
            problem="Build a HIPAA multi-agent healthcare assistant with RAG",
            token_budget=400,
        )
        # Compression aims for the budget; allow the optimizer's own 1.5x ceiling.
        assert result["estimated_tokens"] <= 400 * 1.5

    def test_comparison_intent_is_detected(self):
        result = quick_context(problem="Should I use LangGraph vs CrewAI for orchestration?")
        assert result["intent"] == "comparison"

    def test_preserves_backward_compatible_keys(self):
        result = quick_context(problem="Build a multi-agent system with vector search")
        assert "context_brief" in result
        assert "genome_short" in result
        assert "confidence" in result
        assert "\\n" not in result["context_brief"]  # G4 regression


class TestRecommendCompressionOptIn:

    def test_no_token_budget_means_no_optimized_context(self):
        result = recommend_ai_stack(problem="Build a production AI assistant platform")
        assert "optimized_context" not in result

    def test_token_budget_adds_optimized_context(self):
        result = recommend_ai_stack(
            problem="Build a production AI assistant platform", token_budget=500
        )
        assert "optimized_context" in result
        assert "intent" in result
        assert isinstance(json.loads(result["optimized_context"]), list)
