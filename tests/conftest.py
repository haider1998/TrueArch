"""
Shared pytest fixtures for the TrueArch test suite.
Loaded automatically by pytest from any test file.
"""
import os
import pytest
from fastapi.testclient import TestClient

from src.data.loader import FrameworkLoader
from src.scoring.engine import ScoringEngine

# ── Path resolution ──────────────────────────────────────────────────────────

DATA_DIR = "data/frameworks" if os.path.exists("data/frameworks") else "../../data/frameworks"


@pytest.fixture(scope="session")
def data_dir() -> str:
    return DATA_DIR


@pytest.fixture(scope="session")
def loaded_frameworks():
    """
    Session-scoped fixture: loads all framework YAMLs once per test session.
    Avoids repeated disk I/O across tests.
    """
    loader = FrameworkLoader(data_dir=DATA_DIR)
    return loader.load_all()


@pytest.fixture(scope="session")
def scored_frameworks(loaded_frameworks):
    """
    Session-scoped fixture: loads and scores all frameworks.
    Required by test_adr.py, test_recommendation.py, and other engine tests.
    """
    engine = ScoringEngine()
    for fw in loaded_frameworks.values():
        fw.computed_scores = engine.compute_scores(fw)
    return loaded_frameworks


@pytest.fixture(scope="module")
def client():
    """
    Module-scoped TestClient. Enters the app's lifespan once per module,
    loading and scoring all frameworks.
    """
    from src.api.main import app
    with TestClient(app) as c:
        yield c
