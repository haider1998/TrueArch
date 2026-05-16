import os
import pytest
from datetime import date
from src.data.loader import FrameworkLoader
from src.scoring.engine import ScoringEngine

@pytest.fixture
def loaded_frameworks():
    base_dir = "." if os.path.exists("data/frameworks") else "../.."
    data_dir = os.path.join(base_dir, "data/frameworks")
    loader = FrameworkLoader(data_dir=data_dir)
    return loader.load_all()

def test_engine_computes_all_scores(loaded_frameworks):
    engine = ScoringEngine(today=date(2026, 5, 16))
    fw = loaded_frameworks["langgraph"]
    
    scores = engine.compute_scores(fw)
    
    assert scores.production_stability is not None
    assert scores.ecosystem_momentum is not None
    assert scores.migration_risk is not None
    assert scores.governance_readiness is not None
    assert scores.agent_compatibility is not None
    assert scores.overall is not None
    assert scores.confidence is not None
    
    assert 0 <= scores.overall <= 100
    assert 0 <= scores.confidence <= 100
    assert scores.score_band in ["Excellent", "Strong", "Good", "Fair", "Weak", "Poor"]

def test_reverse_scoring_logic_for_migration_risk(loaded_frameworks):
    # Migration risk is reverse-scored (higher score = easier to leave)
    engine = ScoringEngine()
    fw = loaded_frameworks["langgraph"]
    scores = engine.compute_scores(fw)
    
    # LangGraph has 4 alternatives and 3 migration guides, meaning it's fairly easy to migrate from,
    # so we expect a higher migration risk score (e.g. > 50).
    assert scores.migration_risk > 50

def test_confidence_cap(loaded_frameworks):
    # Confidence should never exceed 99%
    engine = ScoringEngine()
    for fw in loaded_frameworks.values():
        scores = engine.compute_scores(fw)
        assert scores.confidence <= 99.0
        
def test_maintenance_mode_penalty(loaded_frameworks):
    engine = ScoringEngine()
    autogen = loaded_frameworks.get("autogen")
    if autogen:
        scores = engine.compute_scores(autogen)
        # Production stability for unmaintained should be overridden to 5.0
        assert scores.production_stability == 5.0
