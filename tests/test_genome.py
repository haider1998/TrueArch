"""
Tests for the Architecture Genome™ Generator and Genome comparison utilities.
"""
import pytest
from datetime import date

from src.recommendation.genome import GenomeGenerator, genome_similarity, genome_matches
from src.recommendation.models import (
    StackQuery, FrameworkChoice, ArchLayer, ComplianceFlag, ScaleTier, PriorityAxis,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def generator():
    return GenomeGenerator()


def _make_choice(framework_id: str, name: str, score: float = 80.0) -> FrameworkChoice:
    return FrameworkChoice(
        layer=ArchLayer.ORCHESTRATION,
        framework_id=framework_id,
        framework_name=name,
        score=score,
        confidence=75.0,
        reason="Test choice",
        version="1.0.0",
        alternatives=[],
        warnings=[],
    )


# ── D1: Pattern detection ──────────────────────────────────────────────────────

class TestD1Pattern:

    def test_multi_agent_keywords(self, generator):
        for problem in ["multi-agent system", "multi agent platform", "multiagent"]:
            short, _ = generator.generate({}, _make_query(problem=problem))
            assert short.startswith("MA-"), f"Expected MA for '{problem}', got {short}"

    def test_rag_keyword(self, generator):
        short, _ = generator.generate({}, _make_query(problem="Build a RAG pipeline"))
        assert short.startswith("RAG-")

    def test_retrieval_keyword(self, generator):
        short, _ = generator.generate({}, _make_query(problem="Document retrieval system"))
        assert short.startswith("RAG-")

    def test_pipeline_keyword(self, generator):
        short, _ = generator.generate({}, _make_query(problem="Data pipeline processor"))
        assert short.startswith("PIPE-")

    def test_chatbot_defaults_to_single_agent(self, generator):
        short, _ = generator.generate({}, _make_query(problem="Customer support chatbot"))
        assert short.startswith("SA-")

    def test_unknown_problem_defaults_to_sa(self, generator):
        short, _ = generator.generate({}, _make_query(problem="Generic AI application tool"))
        assert short.startswith("SA-")


# ── D2: Memory strategy ───────────────────────────────────────────────────────

class TestD2Memory:

    def test_redis_gives_stateful(self, generator):
        layers = {"database": _make_choice("redis", "Redis")}
        short, _ = generator.generate(layers, _make_query())
        d2 = short.split("-")[1]
        assert d2 == "STAT"

    def test_qdrant_gives_vector(self, generator):
        layers = {"vector_db": _make_choice("qdrant", "Qdrant")}
        short, _ = generator.generate(layers, _make_query())
        d2 = short.split("-")[1]
        assert d2 == "VECT"

    def test_both_redis_and_qdrant_gives_hybrid(self, generator):
        layers = {
            "database": _make_choice("redis", "Redis"),
            "vector_db": _make_choice("qdrant", "Qdrant"),
        }
        short, _ = generator.generate(layers, _make_query())
        d2 = short.split("-")[1]
        assert d2 == "HYB"

    def test_no_store_gives_sess_default(self, generator):
        short, _ = generator.generate({}, _make_query())
        d2 = short.split("-")[1]
        assert d2 == "SESS"


# ── D3: Scaling ───────────────────────────────────────────────────────────────

class TestD3Scaling:

    def test_enterprise_gives_horizontal(self, generator):
        short, _ = generator.generate({}, _make_query(scale=ScaleTier.ENTERPRISE))
        d3 = short.split("-")[2]
        assert d3 == "HOR"

    def test_prototype_gives_vertical(self, generator):
        short, _ = generator.generate({}, _make_query(scale=ScaleTier.PROTOTYPE))
        d3 = short.split("-")[2]
        assert d3 == "VER"

    def test_growth_gives_horizontal(self, generator):
        short, _ = generator.generate({}, _make_query(scale=ScaleTier.GROWTH))
        d3 = short.split("-")[2]
        assert d3 == "HOR"


# ── D4: Compliance ────────────────────────────────────────────────────────────

class TestD4Compliance:

    def test_hipaa_compliance(self, generator):
        short, _ = generator.generate(
            {}, _make_query(compliance=[ComplianceFlag.HIPAA])
        )
        d4 = short.split("-")[3]
        assert d4 == "HIPAA"

    def test_no_compliance_gives_open(self, generator):
        short, _ = generator.generate(
            {}, _make_query(compliance=[ComplianceFlag.NONE])
        )
        d4 = short.split("-")[3]
        assert d4 == "OPEN"

    def test_multiple_compliance_flags(self, generator):
        short, _ = generator.generate(
            {}, _make_query(compliance=[ComplianceFlag.HIPAA, ComplianceFlag.SOC2])
        )
        d4 = short.split("-")[3]
        assert "HIPAA" in d4 and "SOC2" in d4


# ── D5: Language ──────────────────────────────────────────────────────────────

class TestD5Language:

    def test_python(self, generator):
        short, _ = generator.generate({}, _make_query(language="python"))
        d5 = short.split("-")[4]
        assert d5 == "PY"

    def test_typescript(self, generator):
        short, _ = generator.generate({}, _make_query(language="typescript"))
        d5 = short.split("-")[4]
        assert d5 == "TS"

    def test_unknown_language_truncated(self, generator):
        short, _ = generator.generate({}, _make_query(language="haskell"))
        d5 = short.split("-")[4]
        assert len(d5) <= 4


# ── D6: Protocol ──────────────────────────────────────────────────────────────

class TestD6Protocol:

    def test_mcp_sdk_gives_mcp(self, generator):
        layers = {"protocol": _make_choice("mcp_sdk_python", "MCP SDK")}
        short, _ = generator.generate(layers, _make_query())
        d6 = short.split("-")[5]
        assert d6 == "MCP"

    def test_langgraph_gives_mcp(self, generator):
        layers = {"orchestration": _make_choice("langgraph", "LangGraph")}
        short, _ = generator.generate(layers, _make_query())
        d6 = short.split("-")[5]
        assert d6 == "MCP"

    def test_default_protocol_is_rest(self, generator):
        short, _ = generator.generate({}, _make_query())
        d6 = short.split("-")[5]
        assert d6 == "REST"


# ── D7: Store ─────────────────────────────────────────────────────────────────

class TestD7Store:

    def test_redis_in_database_layer(self, generator):
        layers = {"database": _make_choice("redis", "Redis")}
        short, _ = generator.generate(layers, _make_query())
        d7 = short.split("-")[6]
        assert d7 == "REDIS"

    def test_qdrant_in_vector_db_layer(self, generator):
        layers = {"vector_db": _make_choice("qdrant", "Qdrant")}
        short, _ = generator.generate(layers, _make_query())
        d7 = short.split("-")[6]
        assert d7 == "QDRANT"

    def test_no_store_defaults_to_mem(self, generator):
        short, _ = generator.generate({}, _make_query())
        d7 = short.split("-")[6]
        assert d7 == "MEM"


# ── Full Genome structure ─────────────────────────────────────────────────────

class TestGenomeStructure:

    def test_short_genome_has_7_parts(self, generator):
        short, _ = generator.generate({}, _make_query())
        assert len(short.split("-")) == 7

    def test_full_genome_contains_short(self, generator):
        short, full = generator.generate({}, _make_query())
        assert full.startswith(short)

    def test_full_genome_has_three_extra_dims(self, generator):
        short, full = generator.generate({}, _make_query())
        extra = full[len(short):]
        # Full genome appends +D8+D9+D10
        assert extra.count("+") == 3

    def test_genome_is_deterministic(self, generator):
        query = _make_query(
            problem="Build a multi-agent HIPAA system",
            compliance=[ComplianceFlag.HIPAA],
            scale=ScaleTier.ENTERPRISE,
        )
        layers = {
            "orchestration": _make_choice("langgraph", "LangGraph"),
            "database": _make_choice("redis", "Redis"),
        }
        short1, full1 = generator.generate(layers, query)
        short2, full2 = generator.generate(layers, query)
        assert short1 == short2
        assert full1 == full2

    def test_hipaa_multi_agent_langgraph_redis_genome(self, generator):
        """Spot-check the canonical HIPAA multi-agent genome."""
        query = _make_query(
            problem="multi-agent patient support platform",
            compliance=[ComplianceFlag.HIPAA],
            scale=ScaleTier.ENTERPRISE,
            language="python",
        )
        layers = {
            "orchestration": _make_choice("langgraph", "LangGraph"),
            "database": _make_choice("redis", "Redis"),
            "protocol": _make_choice("mcp_sdk_python", "MCP SDK"),
        }
        short, full = generator.generate(layers, query)
        assert short == "MA-STAT-HOR-HIPAA-PY-MCP-REDIS"
        assert "LGR" in full


# ── genome_similarity ─────────────────────────────────────────────────────────

class TestGenomeSimilarity:

    def test_identical_genomes_score_1(self):
        result = genome_similarity(
            "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
            "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
        )
        assert result["similarity_score"] == 1.0

    def test_completely_different_genomes_score_low(self):
        result = genome_similarity(
            "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
            "SA-VECT-VER-OPEN-TS-REST-PGVEC",
        )
        assert result["similarity_score"] < 0.30

    def test_wildcard_matches_any_value(self):
        result = genome_similarity(
            "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
            "MA-*-*-HIPAA-*-*-*",
        )
        assert result["similarity_score"] == 1.0

    def test_compliance_mismatch_sets_hard_filter(self):
        result = genome_similarity(
            "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
            "MA-STAT-HOR-OPEN-PY-MCP-REDIS",
        )
        assert result["hard_filter_mismatch"] is True

    def test_same_compliance_no_hard_filter(self):
        result = genome_similarity(
            "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
            "SA-VECT-VER-HIPAA-TS-REST-QDRANT",
        )
        assert result["hard_filter_mismatch"] is False

    def test_result_contains_required_keys(self):
        result = genome_similarity("MA-STAT-HOR-HIPAA-PY-MCP-REDIS", "SA-VECT-VER-OPEN-TS-REST-PG")
        assert "similarity_score" in result
        assert "matching_dimensions" in result
        assert "mismatching_dimensions" in result
        assert "hard_filter_mismatch" in result
        assert "genome_a" in result
        assert "genome_b" in result


# ── genome_matches ────────────────────────────────────────────────────────────

class TestGenomeMatches:

    def test_exact_match(self):
        assert genome_matches("MA-STAT-HOR-HIPAA-PY-MCP-REDIS", "MA-STAT-HOR-HIPAA-PY-MCP-REDIS")

    def test_wildcard_matches_all(self):
        assert genome_matches("MA-STAT-HOR-HIPAA-PY-MCP-REDIS", "*-*-*-HIPAA-*-*-*")

    def test_partial_wildcard(self):
        assert genome_matches("MA-STAT-HOR-HIPAA-PY-MCP-REDIS", "MA-*-*-HIPAA-*-*-*")

    def test_mismatch_returns_false(self):
        assert not genome_matches("MA-STAT-HOR-HIPAA-PY-MCP-REDIS", "SA-*-*-HIPAA-*-*-*")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_query(
    problem: str = "Build an AI system",
    compliance=None,
    scale=ScaleTier.GROWTH,
    priority=PriorityAxis.RELIABILITY,
    language="python",
) -> StackQuery:
    return StackQuery(
        problem=problem,
        compliance=compliance or [ComplianceFlag.NONE],
        scale=scale,
        priority=priority,
        language=language,
    )
