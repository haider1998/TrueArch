"""
Tests for the FastAPI layer (src/api/main.py).

FastAPI's TestClient triggers the lifespan context manager automatically
when used as a context manager (`with TestClient(app) as client:`).
This is the correct modern pattern — do not call startup_event() directly.
"""
import pytest
from fastapi.testclient import TestClient

from src.api.main import app


# ── Shared client fixture ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Module-scoped TestClient. Enters the app's lifespan once per module,
    which loads and scores all 25 frameworks.
    """
    with TestClient(app) as c:
        yield c


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["frameworks_loaded"] == 25


# ── Framework listing ─────────────────────────────────────────────────────────

def test_list_all_frameworks(client):
    """All 25 frameworks are returned, sorted by score descending."""
    response = client.get("/api/v1/frameworks")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 25

    scores = [fw["overall_score"] for fw in data]
    assert scores == sorted(scores, reverse=True), "Frameworks should be sorted by score"


def test_list_frameworks_required_fields(client):
    """Every framework in the list has the expected response fields."""
    response = client.get("/api/v1/frameworks")
    required_fields = {"id", "name", "category", "genome_dimension", "overall_score",
                       "confidence", "score_band", "url", "docs_url"}
    for fw in response.json():
        assert required_fields.issubset(fw.keys()), f"Missing fields in: {fw['id']}"


def test_list_frameworks_category_filter(client):
    """Filtering by category=orchestration returns only orchestration frameworks."""
    response = client.get("/api/v1/frameworks?category=orchestration")
    assert response.status_code == 200

    data = response.json()
    assert len(data) >= 5
    for fw in data:
        assert fw["category"] == "orchestration"


def test_list_frameworks_genome_filter(client):
    """Filtering by genome_dimension=D8_orchestrator returns correct frameworks."""
    response = client.get("/api/v1/frameworks?genome_dimension=D8_orchestrator")
    assert response.status_code == 200

    data = response.json()
    assert len(data) >= 5
    for fw in data:
        assert fw["genome_dimension"] in {"LGR", "AUTOG", "CREW", "SWARM", "SEMK", "PADK", "ADK", "PYDAI", "LANG", "LLMIND"}


def test_list_frameworks_unknown_category_returns_empty(client):
    """Filtering by a non-existent category returns an empty list (not 404)."""
    response = client.get("/api/v1/frameworks?category=nonexistent_category")
    assert response.status_code == 200
    assert response.json() == []


# ── Framework detail ──────────────────────────────────────────────────────────

def test_get_framework_detail(client):
    """Framework detail endpoint returns full data and computed scores."""
    response = client.get("/api/v1/frameworks/langgraph")
    assert response.status_code == 200

    data = response.json()
    assert "framework" in data
    assert "scores" in data
    assert data["framework"]["id"] == "langgraph"
    assert data["scores"]["confidence"] > 0
    assert data["scores"]["overall"] is not None


def test_get_framework_detail_not_found(client):
    """Requesting a missing framework ID returns 404 with a helpful message."""
    response = client.get("/api/v1/frameworks/does_not_exist")
    assert response.status_code == 404
    assert "does_not_exist" in response.json()["detail"]


# ── Recommendations ───────────────────────────────────────────────────────────

def test_recommendations_returns_sorted_results(client):
    """Recommendations are sorted by score, highest first."""
    response = client.get("/api/v1/recommendations?category=vector-db")
    assert response.status_code == 200

    data = response.json()
    assert len(data) > 0
    scores = [fw["overall_score"] for fw in data]
    assert scores == sorted(scores, reverse=True)


def test_recommendations_excludes_poor_scores(client):
    """Recommendations endpoint filters out frameworks scoring below 60."""
    response = client.get("/api/v1/recommendations?category=orchestration")
    assert response.status_code == 200

    data = response.json()
    # AutoGen is in maintenance mode and should score very low
    ids = [fw["id"] for fw in data]
    # If any result is present, all should be >= 60 (or it's a fallback scenario)
    for fw in data:
        assert fw["overall_score"] >= 60 or len(data) == 1, (
            f"{fw['id']} scored {fw['overall_score']} but should be filtered out"
        )


def test_recommendations_missing_category_returns_404(client):
    """Requesting recommendations for a non-existent category returns 404."""
    response = client.get("/api/v1/recommendations?category=nonexistent")
    assert response.status_code == 404


def test_recommendations_requires_category_param(client):
    """Omitting the category query param returns 422 Unprocessable Entity."""
    response = client.get("/api/v1/recommendations")
    assert response.status_code == 422
