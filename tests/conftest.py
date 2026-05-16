"""
Shared pytest fixtures for the TrueArch test suite.
Loaded automatically by pytest from any test file.
"""
import os
import pytest
from src.data.loader import FrameworkLoader

# ── Path resolution ──────────────────────────────────────────────────────────

DATA_DIR = "data/frameworks" if os.path.exists("data/frameworks") else "../../data/frameworks"


@pytest.fixture(scope="session")
def data_dir() -> str:
    return DATA_DIR


@pytest.fixture(scope="session")
def loaded_frameworks():
    """
    Session-scoped fixture: loads all 25 framework YAMLs once per test session.
    Avoids repeated disk I/O across tests.
    """
    loader = FrameworkLoader(data_dir=DATA_DIR)
    return loader.load_all()
