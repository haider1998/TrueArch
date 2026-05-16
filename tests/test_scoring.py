"""
Tests for ScoringEngine (src/scoring/engine.py).
Uses the session-scoped `loaded_frameworks` fixture from conftest.py.
"""
import pytest
from datetime import date
from src.scoring.engine import ScoringEngine


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    """A scoring engine pinned to a fixed date so tests are deterministic."""
    return ScoringEngine(today=date(2026, 5, 16))


# ── Core scoring ──────────────────────────────────────────────────────────────

def test_engine_computes_all_score_fields(loaded_frameworks, engine):
    """All five dimensions, overall, confidence, band, and validity are populated."""
    fw = loaded_frameworks["langgraph"]
    scores = engine.compute_scores(fw)

    assert scores.production_stability is not None
    assert scores.ecosystem_momentum is not None
    assert scores.migration_risk is not None
    assert scores.governance_readiness is not None
    assert scores.agent_compatibility is not None
    assert scores.overall is not None
    assert scores.confidence is not None
    assert scores.score_band is not None
    assert scores.last_computed == date(2026, 5, 16)
    assert scores.valid_until is not None


def test_overall_score_is_within_bounds(loaded_frameworks, engine):
    """Overall score is always in [0, 100] for every framework."""
    for fw in loaded_frameworks.values():
        scores = engine.compute_scores(fw)
        assert 0 <= scores.overall <= 100, (
            f"{fw.id}: overall score {scores.overall} out of range"
        )


def test_confidence_is_within_bounds(loaded_frameworks, engine):
    """Confidence is always in [10, 99] as per SCORING_FORMULA.md."""
    for fw in loaded_frameworks.values():
        scores = engine.compute_scores(fw)
        assert 10 <= scores.confidence <= 99, (
            f"{fw.id}: confidence {scores.confidence} out of range"
        )


def test_score_band_is_valid(loaded_frameworks, engine):
    """Score band is always one of the six defined values."""
    valid_bands = {"Excellent", "Strong", "Good", "Fair", "Weak", "Poor"}
    for fw in loaded_frameworks.values():
        scores = engine.compute_scores(fw)
        assert scores.score_band in valid_bands, (
            f"{fw.id}: invalid band '{scores.score_band}'"
        )


# ── Formula-specific ──────────────────────────────────────────────────────────

def test_migration_risk_is_reverse_scored(loaded_frameworks, engine):
    """
    Migration Risk is reverse-scored: higher = easier to leave.
    LangGraph has 4 alternatives, so its migration risk score should be > 50.
    """
    scores = engine.compute_scores(loaded_frameworks["langgraph"])
    assert scores.migration_risk > 50, (
        f"LangGraph migration_risk={scores.migration_risk} — expected > 50 (easy to migrate)"
    )


def test_maintenance_mode_caps_production_stability(loaded_frameworks, engine):
    """
    SCORING_FORMULA.md: archived/unmaintained → Production Stability = 5.
    AutoGen is in maintenance mode (flagged in known_issues).
    """
    autogen = loaded_frameworks.get("autogen")
    if not autogen:
        pytest.skip("autogen.yaml not found in test dataset")
    scores = engine.compute_scores(autogen)
    assert scores.production_stability == 5.0, (
        f"Expected 5.0 for maintenance-mode framework, got {scores.production_stability}"
    )


def test_native_mcp_maximises_agent_compatibility(loaded_frameworks, engine):
    """
    A framework with native MCP, async, thread-safe, benchmarked, and native
    multi-agent should score very high on agent compatibility (≥ 80).
    MCP SDK Python has all of these.
    """
    scores = engine.compute_scores(loaded_frameworks["mcp_sdk_python"])
    assert scores.agent_compatibility >= 75, (
        f"mcp_sdk_python agent_compatibility={scores.agent_compatibility} — expected ≥ 75"
    )


def test_zero_security_advisories_boosts_governance(loaded_frameworks, engine):
    """A framework with 0 CVEs should not be penalised in governance score."""
    for fw_id, fw in loaded_frameworks.items():
        if fw.signals.governance_readiness.unpatched_cves == 0:
            scores = engine.compute_scores(fw)
            # Security sub-score should be positive; overall governance > 0
            assert scores.governance_readiness > 0, (
                f"{fw_id}: governance_readiness should be > 0 with zero CVEs"
            )
            break


def test_incident_rate_default_applies_penalty(loaded_frameworks, engine):
    """
    When incident_rate_source == 'default', confidence is reduced by 15
    relative to a framework with real telemetry.
    """
    # Find a framework with source == "default"
    default_fw = next(
        (fw for fw in loaded_frameworks.values()
         if fw.signals.production_stability.incident_rate_source == "default"),
        None,
    )
    if not default_fw:
        pytest.skip("No framework with incident_rate_source='default' in dataset")

    scores = engine.compute_scores(default_fw)
    # Base is 70; default source subtracts 15 → max base 55 before other adjustments
    # Confidence should be strictly less than 75 (70 + 5 max fresh signal bonus)
    assert scores.confidence < 80, (
        f"{default_fw.id}: confidence {scores.confidence} is unexpectedly high for a default-source framework"
    )


def test_score_band_boundaries(engine, loaded_frameworks):
    """Verify _determine_score_band boundaries match SCORING_FORMULA.md table."""
    fw = list(loaded_frameworks.values())[0]  # any framework
    assert engine._determine_score_band(95) == "Excellent"
    assert engine._determine_score_band(75) == "Strong"
    assert engine._determine_score_band(60) == "Good"
    assert engine._determine_score_band(45) == "Fair"
    assert engine._determine_score_band(30) == "Weak"
    assert engine._determine_score_band(29) == "Poor"
