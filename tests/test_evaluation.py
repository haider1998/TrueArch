"""
TrueArch Semantic Correctness Evaluation Harness.

This is the most important test file in the project. It answers the question:
"Does TrueArch actually recommend the RIGHT thing?"

Standard pytest can tell us "the code ran without error." This file tells us
"the code produced the architecturally correct recommendation for the given constraints."

Design principles:
  - Every test case has a human-curated RATIONALE explaining WHY a specific framework
    must or must not win. This is the ground truth.
  - Tests are deliberately declarative (no logic inside tests themselves).
  - Tests use soft assertions where the domain is ambiguous (multiple correct answers).
  - Tests use hard assertions where correctness is non-negotiable (e.g. AutoGen at enterprise).

This file acts as the "contract" between the scoring data and the product promise.
If a test here fails, it means either:
  (a) The YAML data for a framework has drifted from reality, or
  (b) The scoring/recommendation logic has a regression.
"""
import re
import pytest
from datetime import date

from src.data.loader import FrameworkLoader
from src.scoring.engine import ScoringEngine
from src.recommendation.stack_engine import StackRecommendationEngine
from src.recommendation.models import (
    StackQuery, ComplianceFlag, ScaleTier, PriorityAxis, ArchLayer,
    StackRecommendation,
)


# ── Session-scoped engine (load once for all evaluation tests) ────────────────

@pytest.fixture(scope="module")
def eval_engine(loaded_frameworks):
    """
    Module-scoped engine fixture pinned to 2026-05-16 for reproducibility.
    Uses the session-scoped loaded_frameworks from conftest.py.
    """
    engine = ScoringEngine(today=date(2026, 5, 16))
    scored = {}
    for fid, fw in loaded_frameworks.items():
        fw.computed_scores = engine.compute_scores(fw)
        scored[fid] = fw
    return StackRecommendationEngine(scored)


def _recommend(eval_engine, **kwargs) -> StackRecommendation:
    """Helper: build a StackQuery and run the engine."""
    query = StackQuery(**kwargs)
    return eval_engine.recommend(query)


# ── Group 1: AutoGen must NEVER win enterprise ────────────────────────────────

class TestAutoGenNeverWinsEnterprise:
    """
    RATIONALE: AutoGen v0.2 is in maintenance mode (flagged in autogen.yaml known_issues).
    The ScoringEngine caps production_stability at 5.0 for maintenance-mode frameworks.
    At enterprise scale, the _scale_modifier applies an additional -15 penalty for stability < 50.
    AutoGen's final modified score should be too low to compete with LangGraph, CrewAI, etc.
    """

    def test_autogen_does_not_win_orchestration_enterprise(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Enterprise multi-agent AI platform for production use",
            scale=ScaleTier.ENTERPRISE,
            priority=PriorityAxis.RELIABILITY,
        )
        orch = result.layers.get("orchestration")
        assert orch is not None, "Orchestration layer must always be recommended."
        assert orch.framework_id != "autogen", (
            f"AutoGen (maintenance mode) MUST NOT win orchestration at enterprise scale. "
            f"Got: {orch.framework_id} (score={orch.score:.1f})"
        )

    def test_autogen_does_not_win_hipaa_enterprise_governance(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="HIPAA-compliant enterprise multi-agent patient support system",
            compliance=[ComplianceFlag.HIPAA],
            scale=ScaleTier.ENTERPRISE,
            priority=PriorityAxis.GOVERNANCE,
        )
        orch = result.layers.get("orchestration")
        if orch:
            assert orch.framework_id != "autogen"

    def test_autogen_not_in_top2_alternatives_enterprise(self, eval_engine):
        """AutoGen should not appear in the top-2 runners-up at enterprise scale."""
        result = _recommend(
            eval_engine,
            problem="Enterprise AI orchestration platform with reliability requirements",
            scale=ScaleTier.ENTERPRISE,
        )
        orch = result.layers.get("orchestration")
        if orch and len(orch.alternatives) >= 2:
            assert "autogen" not in orch.alternatives[:2], (
                "AutoGen should not be a top-2 alternative for enterprise orchestration."
            )


# ── Group 2: Correct orchestration by problem type ───────────────────────────

class TestOrchestrationCorrectness:
    """
    RATIONALE:
    - Multi-agent problems: keyword_boost gives LangGraph +10, Google ADK +8, CrewAI +6
    - RAG problems: keyword_boost gives LlamaIndex +10, LangChain +6
    - LangGraph has state_management_rating=100/100 — best for stateful workflows
    """

    def test_multi_agent_picks_multiagent_capable_orchestrator(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Build a multi-agent customer support system with handoffs between agents",
        )
        orch = result.layers.get("orchestration")
        assert orch is not None
        valid = {"langgraph", "crewai", "google_adk", "pydantic_ai", "smolagents"}
        assert orch.framework_id in valid, (
            f"Multi-agent query should pick a multi-agent orchestrator. Got: {orch.framework_id}"
        )

    def test_rag_keyword_boosts_retrieval_frameworks(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Build a RAG pipeline for enterprise document search and question answering",
        )
        orch = result.layers.get("orchestration")
        assert orch is not None
        valid_rag = {"llamaindex", "langchain", "langgraph", "dspy"}
        assert orch.framework_id in valid_rag, (
            f"RAG query should pick a retrieval-focused orchestrator. Got: {orch.framework_id}"
        )

    def test_stateful_multi_agent_favors_langgraph(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Build a stateful multi-agent workflow with persistent memory and checkpointing",
        )
        orch = result.layers.get("orchestration")
        assert orch is not None
        valid_stateful = {"langgraph", "pydantic_ai", "google_adk", "crewai"}
        assert orch.framework_id in valid_stateful

    def test_orchestration_confidence_above_50(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Build an AI assistant with tool use and memory",
        )
        assert result.confidence >= 50, (
            f"Confidence is too low: {result.confidence}%. Frameworks may have insufficient data."
        )


# ── Group 3: Vector DB correctness ───────────────────────────────────────────

class TestVectorDBCorrectness:
    """
    RATIONALE: Chroma is flagged as prototype-only. At enterprise scale it should
    not win because: (a) scale_modifier penalizes low-stability frameworks,
    (b) the keyword_boost system does not boost it for production use cases.
    Qdrant and Pinecone are the production leaders with higher stability scores.
    """

    def test_chroma_does_not_win_enterprise_vector_search(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="High-throughput vector similarity search at enterprise scale",
            scale=ScaleTier.ENTERPRISE,
        )
        vdb = result.layers.get("vector_db")
        if vdb:
            assert vdb.framework_id != "chroma", (
                "Chroma is prototype-only and must NOT win enterprise vector search. "
                f"Got: {vdb.framework_id} (score={vdb.score:.1f})"
            )

    def test_production_vector_db_has_adequate_score(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Production vector search for 10M+ document corpus",
            scale=ScaleTier.SCALE,
        )
        vdb = result.layers.get("vector_db")
        if vdb:
            assert vdb.score >= 55, (
                f"Production vector DB winner {vdb.framework_id} scored {vdb.score:.1f}. "
                "Expected >= 55 for a production-scale recommendation."
            )

    def test_vector_keyword_query_includes_vector_db_layer(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Semantic search with vector embeddings for document retrieval",
            layers=[ArchLayer.VECTOR_DB],
        )
        assert "vector_db" in result.layers, "vector_db layer must be recommended"
        valid = {"qdrant", "pinecone", "weaviate", "chroma", "postgresql_pgvector"}
        assert result.layers["vector_db"].framework_id in valid


# ── Group 4: Compliance constraint correctness ───────────────────────────────

class TestComplianceConstraints:
    """
    RATIONALE: Compliance flags are hard score modifiers (-20 for HIPAA-unverified, etc.)
    The recommendation output must reflect these constraints through warnings and score changes.
    """

    def test_hipaa_query_produces_valid_recommendation(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Patient health data assistant for healthcare providers",
            compliance=[ComplianceFlag.HIPAA],
        )
        assert isinstance(result.global_warnings, list)
        assert len(result.layers) >= 2

    def test_gdpr_aws_generates_data_residency_warning(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="EU citizen data processing platform for financial services",
            compliance=[ComplianceFlag.GDPR],
            cloud="aws",
        )
        all_text = " ".join(result.global_warnings).lower()
        assert "gdpr" in all_text or "region" in all_text or "eu" in all_text, (
            "GDPR + AWS query must generate a data residency warning."
        )

    def test_soc2_query_still_produces_layers(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="SOC2-compliant AI chatbot for financial services customers",
            compliance=[ComplianceFlag.SOC2],
            scale=ScaleTier.GROWTH,
        )
        assert len(result.layers) >= 2


# ── Group 5: Scale tier modifier correctness ─────────────────────────────────

class TestScaleTierCorrectness:
    """
    RATIONALE: Scale modifier boosts/penalizes based on stability and momentum scores.
    FastAPI dominates the API layer due to its high ecosystem_momentum and production_stability.
    At enterprise scale, only frameworks with stability >= 50 survive without penalty.
    """

    def test_enterprise_api_layer_picks_fastapi(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Enterprise API gateway for AI microservices",
            scale=ScaleTier.ENTERPRISE,
            layers=[ArchLayer.API_LAYER],
        )
        api = result.layers.get("api_layer")
        if api:
            assert api.framework_id == "fastapi", (
                f"FastAPI must win the API layer at enterprise scale. Got: {api.framework_id}"
            )

    def test_prototype_scale_produces_valid_result(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Quick prototype AI chatbot for internal demos",
            scale=ScaleTier.PROTOTYPE,
        )
        assert len(result.layers) >= 2
        assert result.confidence > 0

    def test_enterprise_scale_result_has_positive_confidence(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Enterprise production AI system at massive scale",
            scale=ScaleTier.ENTERPRISE,
        )
        assert result.confidence > 0


# ── Group 6: Genome encoding correctness ─────────────────────────────────────

class TestGenomeCorrectness:
    """
    RATIONALE: The Architecture Genome must deterministically encode constraints.
    Multi-agent → D1=MA, RAG → D1=RAG, HIPAA → D4=HIPAA,
    enterprise → D3=HOR, python → D5=PY.
    """

    def test_multi_agent_encodes_d1_as_ma(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Build a multi-agent AI orchestration system with complex workflows",
        )
        parts = (result.genome_short or "").split("-")
        assert len(parts) == 7
        assert parts[0] == "MA", f"D1 should be 'MA' for multi-agent. Got: {parts[0]}"

    def test_rag_problem_encodes_d1_as_rag(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Build a RAG retrieval augmented generation system for document Q&A",
        )
        parts = (result.genome_short or "").split("-")
        assert len(parts) == 7
        assert parts[0] == "RAG", f"D1 should be 'RAG' for RAG problem. Got: {parts[0]}"

    def test_hipaa_compliance_encodes_d4_as_hipaa(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Healthcare AI assistant for patient management",
            compliance=[ComplianceFlag.HIPAA],
        )
        parts = (result.genome_short or "").split("-")
        assert len(parts) == 7
        assert parts[3] == "HIPAA", f"D4 should be 'HIPAA'. Got: {parts[3]}"

    def test_enterprise_encodes_d3_as_hor(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Enterprise AI platform for 10M+ users",
            scale=ScaleTier.ENTERPRISE,
        )
        parts = (result.genome_short or "").split("-")
        assert len(parts) == 7
        assert parts[2] == "HOR", f"D3 should be 'HOR' for enterprise. Got: {parts[2]}"

    def test_python_language_encodes_d5_as_py(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Build a multi-agent AI platform for production",
            language="python",
        )
        parts = (result.genome_short or "").split("-")
        assert len(parts) == 7
        assert parts[4] == "PY", f"D5 should be 'PY' for Python. Got: {parts[4]}"

    def test_genome_is_deterministic_for_same_query(self, eval_engine):
        """Same query must always produce the same Genome — zero randomness."""
        query = StackQuery(
            problem="Build a multi-agent HIPAA patient support platform with Redis memory",
            compliance=[ComplianceFlag.HIPAA],
            scale=ScaleTier.ENTERPRISE,
        )
        r1 = eval_engine.recommend(query)
        r2 = eval_engine.recommend(query)
        assert r1.genome_short == r2.genome_short, "Genome must be deterministic."
        assert r1.layers.keys() == r2.layers.keys()


# ── Group 7: Priority axis directional correctness ───────────────────────────

class TestPriorityAxisCorrectness:
    """
    RATIONALE: Priority adjustments push scores in a defined direction.
    Governance priority → gov-score-heavy frameworks win.
    Developer speed → high-momentum frameworks win.
    Cost efficiency → open-source MIT/Apache frameworks get a +5 boost.
    """

    def test_governance_priority_does_not_pick_autogen(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="AI platform with strict compliance and audit log requirements",
            priority=PriorityAxis.GOVERNANCE,
        )
        orch = result.layers.get("orchestration")
        if orch:
            assert orch.framework_id != "autogen"

    def test_developer_speed_does_not_pick_maintenance_mode(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Fast prototype AI agent for internal team tooling",
            priority=PriorityAxis.DEVELOPER_SPEED,
            scale=ScaleTier.PROTOTYPE,
        )
        orch = result.layers.get("orchestration")
        if orch:
            assert orch.framework_id != "autogen"

    def test_any_priority_produces_valid_result(self, eval_engine):
        for priority in PriorityAxis:
            result = _recommend(
                eval_engine,
                problem="Build a multi-agent AI system for production use",
                priority=priority,
            )
            assert len(result.layers) >= 2, f"Priority {priority} produced no layers."
            assert result.confidence > 0


# ── Group 8: Tradeoff notes generation ───────────────────────────────────────

class TestTradeoffNotes:
    """
    RATIONALE: The engine generates specific cross-layer tradeoff notes.
    HIPAA compliance always triggers a PHI/encryption warning in tradeoff notes.
    """

    def test_hipaa_generates_compliance_tradeoff_note(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="HIPAA-compliant multi-agent healthcare AI platform",
            compliance=[ComplianceFlag.HIPAA],
        )
        all_text = " ".join(result.tradeoff_notes + result.global_warnings).lower()
        assert "hipaa" in all_text or "phi" in all_text or "encrypt" in all_text, (
            "HIPAA query must generate a compliance-related tradeoff note or warning."
        )

    def test_tradeoff_notes_is_list(self, eval_engine):
        result = _recommend(
            eval_engine,
            problem="Build a multi-agent system using LangGraph for orchestration",
        )
        assert isinstance(result.tradeoff_notes, list)


# ── Group 9: ADR quality ──────────────────────────────────────────────────────

class TestADRQuality:
    """
    RATIONALE: The ADR generator must produce documents that are:
    - Committable (valid Markdown with correct heading structure)
    - Informative (Genome, rationale, alternatives, risks)
    - Agent-usable (Agent Context Brief section for system prompt injection)
    """

    @pytest.fixture(scope="class")
    def hipaa_adr(self, eval_engine):
        from src.recommendation.adr_generator import ADRGenerator
        query = StackQuery(
            problem="HIPAA-compliant multi-agent patient support platform",
            compliance=[ComplianceFlag.HIPAA],
            scale=ScaleTier.ENTERPRISE,
            priority=PriorityAxis.GOVERNANCE,
        )
        rec = eval_engine.recommend(query)
        gen = ADRGenerator()
        return gen.generate(rec, adr_number=1, project_name="MediAssist", team="AI Platform")

    def test_adr_starts_with_h1_heading(self, hipaa_adr):
        assert hipaa_adr.startswith("# ADR-001:")

    def test_adr_contains_genome_section(self, hipaa_adr):
        assert "## Architecture Genome" in hipaa_adr

    def test_adr_contains_rationale_section(self, hipaa_adr):
        assert "## Rationale" in hipaa_adr

    def test_adr_contains_agent_context_brief(self, hipaa_adr):
        """G8 regression: ADR must include Agent Context Brief section."""
        assert "## Agent Context Brief" in hipaa_adr, (
            "ADR must contain '## Agent Context Brief' section. G8 fix may have regressed."
        )

    def test_adr_context_brief_has_stack_line(self, hipaa_adr):
        if "## Agent Context Brief" in hipaa_adr:
            section = hipaa_adr.split("## Agent Context Brief")[1]
            assert "Stack:" in section

    def test_adr_has_project_and_team(self, hipaa_adr):
        assert "MediAssist" in hipaa_adr
        assert "AI Platform" in hipaa_adr

    def test_adr_has_review_schedule(self, hipaa_adr):
        assert "## Review Schedule" in hipaa_adr
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", hipaa_adr)
        assert len(dates) >= 2

    def test_adr_has_alternatives_rejected(self, hipaa_adr):
        assert "## Alternatives Rejected" in hipaa_adr

    def test_adr_id_is_8_hex_chars(self, hipaa_adr):
        matches = re.findall(r"truearch/([0-9a-f]{8})", hipaa_adr)
        assert len(matches) >= 1, "ADR must contain a truearch/XXXXXXXX ID"

    def test_adr_is_deterministic(self, eval_engine):
        from src.recommendation.adr_generator import ADRGenerator
        query = StackQuery(problem="Build a multi-agent AI system for enterprise use cases")
        rec = eval_engine.recommend(query)
        gen = ADRGenerator()
        adr1 = gen.generate(rec, adr_number=1)
        adr2 = gen.generate(rec, adr_number=1)
        assert adr1 == adr2, "ADR generation must be deterministic for the same recommendation."
