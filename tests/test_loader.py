import os
import pytest
from pathlib import Path
from src.data.loader import FrameworkLoader

def test_loader_initialization():
    loader = FrameworkLoader()
    assert loader.data_dir == Path("data/frameworks")

def test_load_all_frameworks():
    base_dir = "." if os.path.exists("data/frameworks") else "../.."
    data_dir = os.path.join(base_dir, "data/frameworks")
    
    loader = FrameworkLoader(data_dir=data_dir)
    frameworks = loader.load_all()
    
    # We expect 25 frameworks to be loaded from our seed data
    assert len(frameworks) == 25
    
    # Test specific well-known frameworks are present
    assert "langgraph" in frameworks
    assert "fastapi" in frameworks
    assert "qdrant" in frameworks
    
    # Test that the schema parsed them correctly
    lg = frameworks["langgraph"]
    assert lg.name == "LangGraph"
    assert lg.category == "orchestration"
    assert lg.genome_dimension.key == "D8_orchestrator"
    
def test_get_by_category():
    base_dir = "." if os.path.exists("data/frameworks") else "../.."
    data_dir = os.path.join(base_dir, "data/frameworks")
    loader = FrameworkLoader(data_dir=data_dir)
    loader.load_all()
    
    orch = loader.get_by_category("orchestration")
    # LangGraph, Autogen, CrewAI, Swarm, Semantic Kernel
    assert len(orch) >= 5
    ids = [f.id for f in orch]
    assert "langgraph" in ids
    assert "crewai" in ids

def test_get_by_genome_dimension():
    base_dir = "." if os.path.exists("data/frameworks") else "../.."
    data_dir = os.path.join(base_dir, "data/frameworks")
    loader = FrameworkLoader(data_dir=data_dir)
    loader.load_all()
    
    d8 = loader.get_by_genome_dimension("D8_orchestrator")
    assert len(d8) >= 5
