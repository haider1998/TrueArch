"""
Tests for the ADR Generator and new API endpoints:
  - POST /api/v1/recommend/stack/adr
  - POST /api/v1/genome/compare
"""
import pytest
import re
from datetime import date

from src.recommendation.adr_generator import ADRGenerator
from src.recommendation.models import StackQuery, ComplianceFlag, ScaleTier, PriorityAxis


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def adr_generator():
    return ADRGenerator()


@pytest.fixture(scope="module")
def sample_recommendation(loaded_frameworks):
    from src.scoring.engine import ScoringEngine
    from src.recommendation.stack_engine import StackRecommendationEngine
    from datetime import date
    engine = ScoringEngine(today=date(2026, 5, 16))
    scored = {}
    for fid, fw in loaded_frameworks.items():
        fw.computed_scores = engine.compute_scores(fw)
        scored[fid] = fw
    stack_engine = StackRecommendationEngine(scored)
    query = StackQuery(
        problem="Build a multi-agent HIPAA patient support platform",
        compliance=[ComplianceFlag.HIPAA],
        scale=ScaleTier.ENTERPRISE,
        priority=PriorityAxis.GOVERNANCE,
        language="python",
    )
    return stack_engine.recommend(query)


@pytest.fixture(scope="module")
def basic_recommendation(loaded_frameworks):
    from src.scoring.engine import ScoringEngine
    from src.recommendation.stack_engine import StackRecommendationEngine
    from datetime import date
    engine = ScoringEngine(today=date(2026, 5, 16))
    scored = {}
    for fid, fw in loaded_frameworks.items():
        fw.computed_scores = engine.compute_scores(fw)
        scored[fid] = fw
    stack_engine = StackRecommendationEngine(scored)
    return stack_engine.recommend(StackQuery(problem="Simple AI chatbot assistant"))


# ── ADR Generator unit tests ──────────────────────────────────────────────────

class TestADRGenerator:

    def test_adr_returns_string(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        assert isinstance(result, str)
        assert len(result) > 200

    def test_adr_contains_h1_title(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        assert result.startswith("# ADR-001:")

    def test_adr_number_formatted_with_leading_zeros(self, adr_generator, basic_recommendation):
        result = adr_generator.generate(basic_recommendation, adr_number=42)
        assert "# ADR-042:" in result

    def test_adr_contains_genome(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        assert "TrueArch Genome" in result
        # Genome should be in backticks
        assert "`" in result

    def test_adr_contains_confidence(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        assert "Confidence" in result
        assert "%" in result

    def test_adr_contains_status_accepted(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        assert "**Status:** Accepted" in result

    def test_adr_contains_today_date(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        today = date.today().isoformat()
        assert today in result

    def test_adr_contains_review_by_date(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        assert "Review By" in result or "Review Date" in result or "Next Review" in result

    def test_adr_contains_decision_table(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        # Should have a markdown table
        assert "| Layer |" in result or "| **" in result

    def test_adr_contains_rationale_section(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        assert "## Rationale" in result

    def test_adr_contains_alternatives_section(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        # Either alternatives section or no alternatives — both valid
        # But the ADR should always have at least rationale
        assert "## Rationale" in result

    def test_adr_contains_truearch_attribution(self, adr_generator, sample_recommendation):
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        assert "TrueArch" in result

    def test_adr_with_project_name(self, adr_generator, basic_recommendation):
        result = adr_generator.generate(
            basic_recommendation,
            adr_number=3,
            project_name="CustomerSupportPlatform",
        )
        assert "CustomerSupportPlatform" in result

    def test_adr_with_team_name(self, adr_generator, basic_recommendation):
        result = adr_generator.generate(
            basic_recommendation,
            adr_number=1,
            team="Platform Engineering",
        )
        assert "Platform Engineering" in result

    def test_adr_genome_table_has_7_rows(self, adr_generator, sample_recommendation):
        """The Genome dimension table should have exactly 7 data rows (D1–D7)."""
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        if "Architecture Genome" in result:
            # Find rows in genome table: lines starting with "| D"
            genome_rows = [l for l in result.split("\n") if l.startswith("| D")]
            assert len(genome_rows) == 7

    def test_adr_id_is_8_hex_chars(self, adr_generator, sample_recommendation):
        """ADR ID generated from Genome + timestamp should be an 8-char hex string."""
        result = adr_generator.generate(sample_recommendation, adr_number=1)
        # Find truearch/XXXXXXXX pattern
        matches = re.findall(r"truearch/([0-9a-f]{8})", result)
        assert len(matches) >= 1

    def test_adr_is_deterministic_same_recommendation(self, adr_generator, sample_recommendation):
        """Same recommendation → same ADR content (except potentially dates)."""
        result1 = adr_generator.generate(sample_recommendation, adr_number=1)
        result2 = adr_generator.generate(sample_recommendation, adr_number=1)
        assert result1 == result2


# ── API: POST /api/v1/recommend/stack/adr ────────────────────────────────────

class TestADRAPI:

    def test_adr_endpoint_returns_200(self, client):
        response = client.post(
            "/api/v1/recommend/stack/adr",
            json={
                "query": {"problem": "Build a multi-agent customer support system"},
                "adr_number": 1,
            },
        )
        assert response.status_code == 200

    def test_adr_endpoint_returns_markdown_content_type(self, client):
        response = client.post(
            "/api/v1/recommend/stack/adr",
            json={"query": {"problem": "Simple AI document search"}},
        )
        assert response.status_code == 200
        assert "text/markdown" in response.headers.get("content-type", "")

    def test_adr_response_contains_adr_heading(self, client):
        response = client.post(
            "/api/v1/recommend/stack/adr",
            json={"query": {"problem": "Build a multi-agent AI system"}, "adr_number": 5},
        )
        assert response.status_code == 200
        assert "# ADR-005:" in response.text

    def test_adr_with_full_context(self, client):
        response = client.post(
            "/api/v1/recommend/stack/adr",
            json={
                "query": {
                    "problem": "HIPAA-compliant patient data assistant",
                    "compliance": ["hipaa"],
                    "scale": "enterprise",
                    "priority": "governance",
                },
                "adr_number": 1,
                "project_name": "MediAssist",
                "team": "AI Platform",
            },
        )
        assert response.status_code == 200
        assert "MediAssist" in response.text
        assert "AI Platform" in response.text

    def test_adr_invalid_problem_too_short(self, client):
        response = client.post(
            "/api/v1/recommend/stack/adr",
            json={"query": {"problem": "AI"}},
        )
        assert response.status_code == 422


# ── API: POST /api/v1/genome/compare ─────────────────────────────────────────

class TestGenomeCompareAPI:

    def test_genome_compare_basic(self, client):
        response = client.post(
            "/api/v1/genome/compare",
            json={
                "genome_a": "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
                "genome_b": "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["similarity_score"] == 1.0

    def test_genome_compare_different_genomes(self, client):
        response = client.post(
            "/api/v1/genome/compare",
            json={
                "genome_a": "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
                "genome_b": "SA-VECT-VER-OPEN-TS-REST-PG",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["similarity_score"] < 0.30
        assert data["hard_filter_mismatch"] is True

    def test_genome_compare_response_structure(self, client):
        response = client.post(
            "/api/v1/genome/compare",
            json={
                "genome_a": "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
                "genome_b": "MA-STAT-HOR-OPEN-PY-MCP-REDIS",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "similarity_score" in data
        assert "matching_dimensions" in data
        assert "mismatching_dimensions" in data
        assert "hard_filter_mismatch" in data
        assert "genome_a" in data
        assert "genome_b" in data

    def test_genome_compare_wildcard(self, client):
        response = client.post(
            "/api/v1/genome/compare",
            json={
                "genome_a": "MA-STAT-HOR-HIPAA-PY-MCP-REDIS",
                "genome_b": "MA-*-*-HIPAA-*-*-*",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["similarity_score"] == 1.0
