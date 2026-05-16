import os
import pytest
from fastapi.testclient import TestClient

from src.api.main import app, startup_event
import asyncio

# Create the test client
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_api_data():
    """Ensure data is loaded before running API tests"""
    # Force the path for tests
    os.environ["DATA_DIR"] = "." if os.path.exists("data/frameworks") else "../.."
    # Run the startup event directly to populate global state
    asyncio.run(startup_event())

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["frameworks_loaded"] == 25

def test_list_frameworks():
    response = client.get("/api/v1/frameworks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 25
    
    # Check if they are sorted by overall_score descending
    scores = [fw["overall_score"] for fw in data]
    assert scores == sorted(scores, reverse=True)

def test_list_frameworks_with_category_filter():
    response = client.get("/api/v1/frameworks?category=orchestration")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5
    for fw in data:
        assert fw["category"] == "orchestration"

def test_get_framework_detail():
    response = client.get("/api/v1/frameworks/langgraph")
    assert response.status_code == 200
    data = response.json()
    assert "framework" in data
    assert "scores" in data
    assert data["framework"]["id"] == "langgraph"
    assert data["scores"]["confidence"] > 0

def test_get_recommendations():
    response = client.get("/api/v1/recommendations?category=vector-db")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    # Top recommendation should have highest score
    assert data[0]["overall_score"] >= data[-1]["overall_score"]
