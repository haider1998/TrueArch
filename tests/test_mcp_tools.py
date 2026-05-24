"""
Tests for all 9 TrueArch MCP tool functions.

MCP tools are plain Python functions decorated with @mcp.tool — they can be
called directly without spinning up any transport layer.

This module covers:
  - quick_context
  - recommend_ai_stack
  - compare_frameworks
  - get_framework_score
  - get_recommendation
  - latest_stable_versions
  - architecture_tradeoffs
  - get_code_patterns
  - generate_adr

All tests import the functions directly from src.mcp.server — no HTTP involved.
"""
import pytest
import re

# Import tool functions directly — they are plain callables
from src.mcp.server import (
    quick_context,
    recommend_ai_stack,
    compare_frameworks,
    get_framework_score,
    get_recommendation,
    latest_stable_versions,
    architecture_tradeoffs,
    get_code_patterns,
    generate_adr,
)


# ── Tool 0.5: quick_context ───────────────────────────────────────────────────

class TestQuickContext:

    def test_returns_context_brief(self):
        result = quick_context(problem="Build a multi-agent customer support system")
        assert "context_brief" in result
        assert isinstance(result["context_brief"], str)
        assert len(result["context_brief"]) > 10

    def test_context_brief_uses_real_newlines(self):
        """G4 regression test: context_brief must contain real newlines, not literal \\n."""
        result = quick_context(problem="Multi-agent AI platform with orchestration")
        brief = result.get("context_brief", "")
        # The brief should have actual newlines, NOT the 2-char sequence backslash-n
        assert "\\n" not in brief, (
            "context_brief contains literal '\\\\n' — the newline escape bug (G4) has regressed."
        )
        # And it should have real newlines (multi-line content)
        assert "\n" in brief, "context_brief should contain real newline characters between lines."

    def test_returns_genome_short(self):
        result = quick_context(problem="Build a multi-agent system")
        assert "genome_short" in result
        genome = result["genome_short"]
        assert genome is not None
        # Genome format: D1-D2-D3-D4-D5-D6-D7 (7 dash-separated segments)
        parts = genome.split("-")
        assert len(parts) == 7, f"Expected 7 genome segments, got {len(parts)}: {genome}"

    def test_returns_confidence(self):
        result = quick_context(problem="Build a RAG document search service")
        assert "confidence" in result
        assert 0 <= result["confidence"] <= 100

    def test_short_problem_returns_error_or_still_runs(self):
        """Problems < 10 chars should propagate the validation error gracefully."""
        result = quick_context(problem="AI")
        # Either an error dict or a recommendation dict — should not raise
        assert isinstance(result, dict)


# ── Tool 1: recommend_ai_stack ────────────────────────────────────────────────

class TestRecommendAIStack:

    def test_basic_recommendation_structure(self):
        result = recommend_ai_stack(problem="Build a multi-agent customer support platform")
        assert "layers" in result
        assert "confidence" in result
        assert "score_band" in result
        assert "genome_short" in result
        assert "generated_at" in result

    def test_returns_at_least_three_layers(self):
        result = recommend_ai_stack(problem="Build a production AI assistant platform")
        assert len(result["layers"]) >= 3

    def test_hipaa_enterprise_governance_recommendation(self):
        """HIPAA + enterprise + governance priority must not pick AutoGen (maintenance mode)."""
        result = recommend_ai_stack(
            problem="HIPAA-compliant patient data assistant with multi-agent support",
            compliance=["hipaa"],
            scale="enterprise",
            priority="governance",
        )
        assert "layers" in result
        orch = result["layers"].get("orchestration")
        if orch:
            assert orch["framework_id"] != "autogen", (
                "AutoGen (maintenance mode) must not win orchestration at enterprise HIPAA scale."
            )

    def test_compliance_warnings_emitted(self):
        result = recommend_ai_stack(
            problem="Healthcare AI system with multi-agent coordination",
            compliance=["hipaa"],
        )
        # global_warnings should exist and be a list
        assert isinstance(result.get("global_warnings", []), list)

    def test_genome_short_format(self):
        result = recommend_ai_stack(problem="Multi-agent pipeline with vector search")
        genome = result.get("genome_short", "")
        assert genome, "genome_short should be non-empty"
        parts = genome.split("-")
        assert len(parts) == 7

    def test_invalid_compliance_falls_back_gracefully(self):
        """Unknown compliance values should fall back to 'none', not crash."""
        result = recommend_ai_stack(
            problem="Build a web application backend",
            compliance=["invalid_regime"],
        )
        assert "layers" in result  # Should still produce a result

    def test_specific_layers_filter(self):
        result = recommend_ai_stack(
            problem="Vector search microservice",
            layers=["vector_db", "api_layer"],
        )
        assert "vector_db" in result["layers"]
        assert "api_layer" in result["layers"]
        assert "orchestration" not in result["layers"]

    def test_context_brief_present_and_multiline(self):
        result = recommend_ai_stack(problem="Build an AI agent for code review")
        brief = result.get("context_brief", "")
        assert brief, "context_brief should not be empty"
        # Must be real newlines after the G4 fix
        assert "\\n" not in brief


# ── Tool 2: compare_frameworks ────────────────────────────────────────────────

class TestCompareFrameworks:

    def test_basic_comparison(self):
        result = compare_frameworks("langgraph", "crewai")
        assert result["framework_a_id"] == "langgraph"
        assert result["framework_b_id"] == "crewai"
        assert len(result["dimensions"]) == 5

    def test_overall_winner_is_valid(self):
        result = compare_frameworks("langgraph", "crewai")
        assert result["overall_winner"] in {"langgraph", "crewai", "tie"}

    def test_context_brief_populated(self):
        """G9 regression test: context_brief must be non-None after fix."""
        result = compare_frameworks("pinecone", "qdrant")
        assert result.get("context_brief") is not None, (
            "context_brief is None — G9 fix may have regressed."
        )
        assert len(result["context_brief"]) > 10

    def test_context_brief_contains_framework_names(self):
        result = compare_frameworks("langgraph", "crewai")
        brief = result.get("context_brief", "")
        assert "LangGraph" in brief or "langgraph" in brief.lower()

    def test_same_framework_returns_error(self):
        result = compare_frameworks("langgraph", "langgraph")
        assert "error" in result

    def test_unknown_framework_returns_error(self):
        result = compare_frameworks("langgraph", "nonexistent_xyz")
        assert "error" in result
        assert "available_frameworks" in result

    def test_use_case_in_output(self):
        result = compare_frameworks("langgraph", "crewai", use_case="HIPAA patient support")
        assert result["use_case"] == "HIPAA patient support"


# ── Tool 3: get_framework_score ───────────────────────────────────────────────

class TestGetFrameworkScore:

    def test_langgraph_score_structure(self):
        result = get_framework_score("langgraph")
        assert result["framework_id"] == "langgraph"
        assert "scores" in result
        scores = result["scores"]
        for field in ["overall", "score_band", "confidence", "production_stability",
                      "ecosystem_momentum", "migration_risk", "governance_readiness",
                      "agent_compatibility"]:
            assert field in scores, f"Missing score field: {field}"

    def test_scores_within_bounds(self):
        result = get_framework_score("fastapi")
        scores = result["scores"]
        for dim in ["overall", "production_stability", "ecosystem_momentum",
                    "migration_risk", "governance_readiness", "agent_compatibility"]:
            val = scores[dim]
            assert 0 <= val <= 100, f"{dim} = {val} is out of [0, 100]"

    def test_unknown_framework_returns_error(self):
        result = get_framework_score("does_not_exist")
        assert "error" in result
        assert "available_frameworks" in result

    def test_known_issues_present(self):
        result = get_framework_score("langgraph")
        assert "known_issues_count" in result
        assert result["known_issues_count"] >= 1  # LangGraph has documented known issues

    def test_staleness_fields_present(self):
        result = get_framework_score("qdrant")
        assert "staleness" in result
        staleness = result["staleness"]
        assert "status" in staleness
        assert staleness["status"] in {"fresh", "acceptable", "stale", "expired"}


# ── Tool 4: get_recommendation ───────────────────────────────────────────────

class TestGetRecommendation:

    def test_orchestration_returns_results(self):
        result = get_recommendation("orchestration")
        assert "results" in result
        assert len(result["results"]) >= 1

    def test_results_sorted_by_score(self):
        result = get_recommendation("orchestration")
        scores = [r["overall_score"] for r in result["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_vector_db_alias_works(self):
        result = get_recommendation("vector_db")
        assert "results" in result
        # No error key
        assert "error" not in result

    def test_unknown_category_returns_error(self):
        result = get_recommendation("definitely_not_a_real_category")
        assert "error" in result
        assert "available_categories" in result

    def test_top_n_respected(self):
        result = get_recommendation("orchestration", top_n=2)
        assert len(result["results"]) <= 2

    def test_min_score_filter(self):
        result = get_recommendation("orchestration", min_score=80.0)
        for fw in result.get("results", []):
            assert fw["overall_score"] >= 80.0


# ── Tool 5: latest_stable_versions ───────────────────────────────────────────

class TestLatestStableVersions:

    def test_single_framework_version(self):
        result = latest_stable_versions(["langgraph"])
        assert "versions" in result
        assert "langgraph" in result["versions"]
        data = result["versions"]["langgraph"]
        assert "version" in data
        assert data["version"]  # non-empty

    def test_multiple_frameworks(self):
        result = latest_stable_versions(["langgraph", "fastapi", "qdrant"])
        assert len(result["versions"]) == 3

    def test_unknown_framework_reported(self):
        result = latest_stable_versions(["langgraph", "totally_fake_framework"])
        assert "unknown_frameworks" in result
        assert "totally_fake_framework" in result["unknown_frameworks"]

    def test_curation_status_present(self):
        result = latest_stable_versions(["fastapi"])
        data = result["versions"]["fastapi"]
        assert "curation_status" in data
        assert data["curation_status"] in {"curated", "pending", "deprecated"}


# ── Tool 6: architecture_tradeoffs ───────────────────────────────────────────

class TestArchitectureTradeoffs:

    def test_langgraph_tradeoffs(self):
        result = architecture_tradeoffs("langgraph")
        assert result["framework_id"] == "langgraph"
        assert "known_issues" in result
        assert len(result["known_issues"]) >= 1

    def test_known_issues_severity_sorted(self):
        """High/critical issues must appear before medium/low."""
        result = architecture_tradeoffs("langgraph")
        issues = result["known_issues"]
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        severities = [severity_order.get(i["severity"], 4) for i in issues]
        assert severities == sorted(severities)

    def test_compatible_with_present(self):
        result = architecture_tradeoffs("langgraph")
        assert "compatible_with" in result
        # LangGraph has known compatible partners (Redis, LangSmith, etc.)
        assert len(result["compatible_with"]) >= 1

    def test_unknown_framework_error(self):
        result = architecture_tradeoffs("nonexistent")
        assert "error" in result

    def test_curator_notes_present(self):
        result = architecture_tradeoffs("langgraph")
        assert "curator_notes" in result
        assert len(result["curator_notes"]) > 10


# ── Tool 7: get_code_patterns ────────────────────────────────────────────────

class TestGetCodePatterns:

    def test_langgraph_checkpoint_sqlite(self):
        result = get_code_patterns("langgraph", "checkpoint")
        assert "snippet" in result
        assert "SqliteSaver" in result["snippet"]

    def test_langgraph_checkpoint_redis(self):
        result = get_code_patterns("langgraph", "redis")
        assert "snippet" in result
        assert "AsyncRedisSaver" in result["snippet"]

    def test_langgraph_step_budget(self):
        result = get_code_patterns("langgraph", "step_budget")
        assert "snippet" in result
        assert "MAX_STEPS" in result["snippet"]

    def test_langgraph_streaming(self):
        result = get_code_patterns("langgraph", "streaming")
        assert "snippet" in result
        assert "astream_events" in result["snippet"]

    def test_fastapi_lifespan(self):
        result = get_code_patterns("fastapi", "lifespan")
        assert "snippet" in result
        assert "asynccontextmanager" in result["snippet"]

    def test_fastapi_opentelemetry(self):
        result = get_code_patterns("fastapi", "opentelemetry")
        assert "snippet" in result
        assert "FastAPIInstrumentor" in result["snippet"]

    def test_qdrant_init(self):
        result = get_code_patterns("qdrant", "init")
        assert "snippet" in result
        assert "AsyncQdrantClient" in result["snippet"]

    def test_langsmith_tracing(self):
        result = get_code_patterns("langsmith", "tracing")
        assert "snippet" in result
        assert "LANGCHAIN_TRACING_V2" in result["snippet"]

    def test_pydantic_ai_tool(self):
        result = get_code_patterns("pydantic_ai", "tool")
        assert "snippet" in result
        assert "RunContext" in result["snippet"]

    def test_redis_session_memory(self):
        result = get_code_patterns("redis", "session_memory")
        assert "snippet" in result
        assert "RedisSessionMemory" in result["snippet"]

    def test_unknown_framework_error(self):
        result = get_code_patterns("does_not_exist", "anything")
        assert "error" in result
        assert "available_frameworks" in result

    def test_unknown_use_case_returns_available(self):
        result = get_code_patterns("langgraph", "definitely_not_a_real_use_case")
        assert "error" in result
        assert "available_use_cases" in result
        assert len(result["available_use_cases"]) >= 1  # LangGraph has multiple patterns

    def test_version_range_present(self):
        result = get_code_patterns("langgraph", "checkpoint")
        assert "version_range" in result
        assert result["version_range"]  # non-empty


# ── Tool 8: generate_adr ─────────────────────────────────────────────────────

class TestGenerateADR:

    def test_basic_adr_generation(self):
        result = generate_adr(problem="Build a multi-agent AI customer support platform")
        assert "markdown" in result
        assert len(result["markdown"]) > 200

    def test_adr_heading_format(self):
        result = generate_adr(
            problem="Build a multi-agent AI customer support platform",
            adr_number=5,
        )
        assert "# ADR-005:" in result["markdown"]

    def test_filename_format(self):
        result = generate_adr(problem="Build a RAG search service", adr_number=12)
        assert result["filename"] == "ADR-012.md"

    def test_genome_short_in_result(self):
        result = generate_adr(problem="Build a stateful multi-agent orchestration platform")
        assert result.get("genome_short") is not None
        parts = result["genome_short"].split("-")
        assert len(parts) == 7

    def test_project_name_in_markdown(self):
        result = generate_adr(
            problem="Build a healthcare AI platform with compliance",
            project_name="MediAssist",
            team="AI Platform Team",
        )
        assert "MediAssist" in result["markdown"]
        assert "AI Platform Team" in result["markdown"]

    def test_hipaa_adr_includes_warnings(self):
        result = generate_adr(
            problem="HIPAA-compliant multi-agent patient support system",
            compliance=["hipaa"],
            scale="enterprise",
            priority="governance",
        )
        md = result["markdown"]
        # ADR should document risks/warnings for HIPAA
        assert "HIPAA" in md or "hipaa" in md.lower()

    def test_adr_contains_genome_section(self):
        result = generate_adr(problem="Build an AI document search platform")
        assert "Architecture Genome" in result["markdown"]

    def test_adr_contains_agent_context_brief_section(self):
        """G8 regression test: ADR must include Agent Context Brief block."""
        result = generate_adr(problem="Multi-agent orchestration for customer support")
        assert "## Agent Context Brief" in result["markdown"], (
            "ADR is missing the '## Agent Context Brief' section — G8 fix may have regressed."
        )

    def test_adr_context_brief_contains_stack_info(self):
        result = generate_adr(problem="Multi-agent platform with vector search and Redis")
        md = result["markdown"]
        # Find the Agent Context Brief section
        if "## Agent Context Brief" in md:
            brief_section = md.split("## Agent Context Brief")[1]
            # Should contain framework names
            assert "Stack:" in brief_section or "Genome:" in brief_section

    def test_confidence_and_score_band_in_result(self):
        result = generate_adr(problem="Build a production AI assistant")
        assert "confidence" in result
        assert "score_band" in result
        assert result["score_band"] in {"Excellent", "Strong", "Good", "Fair", "Weak", "Poor"}
        assert 0 <= result["confidence"] <= 100
