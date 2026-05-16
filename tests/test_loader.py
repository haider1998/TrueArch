"""
Tests for FrameworkLoader (src/data/loader.py).
Uses the session-scoped `loaded_frameworks` fixture from conftest.py.
"""
import os
import pytest
from pathlib import Path
from src.data.loader import FrameworkLoader


def test_loader_initialization():
    """Default data_dir is set correctly on construction."""
    loader = FrameworkLoader()
    assert loader.data_dir == Path("data/frameworks")


def test_load_all_frameworks(loaded_frameworks):
    """All 25 seed framework YAMLs are loaded and parsed without errors."""
    # 25 frameworks (schema.yaml is excluded by the loader)
    assert len(loaded_frameworks) == 25


def test_known_framework_ids_present(loaded_frameworks):
    """Key frameworks are present in the loaded database."""
    required = {"langgraph", "fastapi", "qdrant", "llamaindex", "mcp_sdk_python", "a2a"}
    for fw_id in required:
        assert fw_id in loaded_frameworks, f"Missing expected framework: {fw_id}"


def test_schema_fields_parsed_correctly(loaded_frameworks):
    """LangGraph is parsed with correct identity and genome fields."""
    lg = loaded_frameworks["langgraph"]
    assert lg.name == "LangGraph"
    assert lg.category == "orchestration"
    assert lg.genome_dimension.key == "D8_orchestrator"
    assert lg.genome_dimension.value == "LGR"
    assert lg.curation.status == "curated"


def test_get_by_category(loaded_frameworks):
    """get_by_category returns all frameworks in the orchestration category."""
    loader = FrameworkLoader(data_dir="data/frameworks")
    loader.frameworks = loaded_frameworks  # inject pre-loaded data

    orch = loader.get_by_category("orchestration")
    ids = {f.id for f in orch}

    assert len(orch) >= 5
    assert "langgraph" in ids
    assert "crewai" in ids
    assert "autogen" in ids


def test_get_by_genome_dimension(loaded_frameworks):
    """get_by_genome_dimension correctly filters by D8_orchestrator."""
    loader = FrameworkLoader(data_dir="data/frameworks")
    loader.frameworks = loaded_frameworks

    d8 = loader.get_by_genome_dimension("D8_orchestrator")
    assert len(d8) >= 5
    for fw in d8:
        assert fw.genome_dimension.key == "D8_orchestrator"


def test_unknown_framework_raises(loaded_frameworks):
    """Requesting a missing framework ID raises KeyError."""
    loader = FrameworkLoader(data_dir="data/frameworks")
    loader.frameworks = loaded_frameworks

    with pytest.raises(KeyError, match="nonexistent"):
        loader.get_framework("nonexistent")
