"""Tests for the telemetry storage read/write path (Phase A1)."""
import importlib
import os

import pytest


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    """Point the telemetry DB at a temp file and return a fresh storage module."""
    db_file = tmp_path / "telemetry.db"
    monkeypatch.setenv("TRUEARCH_DB_PATH", str(db_file))
    import src.telemetry.storage as storage_mod
    importlib.reload(storage_mod)
    return storage_mod


def test_roundtrip_write_then_read(storage):
    storage.log_recommendation(
        query_problem="multi-agent HIPAA patient support in Python",
        genome_short="MA-STAT-HIPAA-PY",
        framework_ids=["langgraph", "qdrant", "logfire"],
        compliance=["HIPAA"],
        scale="startup",
        priority="production_stability",
    )
    insights = storage.get_insights()

    assert insights["total_queries"] == 1
    frameworks = {f["framework"] for f in insights["top_frameworks"]}
    assert {"langgraph", "qdrant", "logfire"} <= frameworks
    assert insights["scale_distribution"]["startup"] == 1
    assert insights["compliance_distribution"]["HIPAA"] == 1
    assert insights["top_stacks_recommended"][0]["stack"] == "langgraph + qdrant + logfire"


def test_recent_queries_never_store_problem_text(storage):
    secret = "super secret proprietary problem description"
    storage.log_recommendation(
        query_problem=secret,
        genome_short="X",
        framework_ids=["fastapi"],
        compliance=[],
        scale="startup",
        priority="speed",
    )
    insights = storage.get_insights()
    recent = insights["recent_queries"][0]
    # Only genome + hash + timestamp — never the raw text.
    assert "problem" not in recent
    assert secret not in str(insights)
    assert len(recent["query_hash"]) == 16


def test_query_hash_is_stable_across_calls(storage):
    storage.log_recommendation("same query", "G", ["fastapi"], [], "startup", "speed")
    storage.log_recommendation("same query", "G", ["fastapi"], [], "startup", "speed")
    insights = storage.get_insights()
    hashes = {r["query_hash"] for r in insights["recent_queries"]}
    assert len(hashes) == 1  # identical queries produce identical hashes


def test_empty_db_returns_zero(storage):
    insights = storage.get_insights()
    assert insights["total_queries"] == 0
    assert "note" in insights


def test_missing_db_file_is_graceful(tmp_path, monkeypatch):
    missing = tmp_path / "does_not_exist" / "telemetry.db"
    monkeypatch.setenv("TRUEARCH_DB_PATH", str(missing))
    import src.telemetry.storage as storage_mod
    importlib.reload(storage_mod)
    # Read before any write: no file yet.
    if missing.exists():
        missing.unlink()
    insights = storage_mod.get_insights()
    assert insights["total_queries"] == 0


def test_mcp_tool_wrapper_returns_data(storage, monkeypatch):
    """The get_telemetry_insights MCP tool should return real data without error."""
    storage.log_recommendation("q", "G", ["crewai"], [], "startup", "speed")
    import src.mcp.server as server_mod
    # server imported get_insights at module load; point it at our reloaded fn.
    monkeypatch.setattr(server_mod, "get_insights", storage.get_insights)
    result = server_mod.get_telemetry_insights(top_n=5)
    assert result["total_queries"] == 1
    assert "error" not in result
