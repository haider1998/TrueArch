"""Tests for the telemetry storage read/write path (Phase A1)."""
import importlib
import os
from pathlib import Path

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


# ── Read-only / unwritable environments ──────────────────────────────────────
# Regression guard for the Hugging Face Spaces crash: the container ran as UID
# 1000 against a root-owned /app/data, so sqlite3 raised OperationalError
# ("unable to open database file") at import time and killed the whole server.
# sqlite3.Error is NOT an OSError, so a bare `except OSError` did not catch it.


@pytest.fixture()
def readonly_storage(tmp_path, monkeypatch):
    """Point the telemetry DB at a directory that cannot be written to."""
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)  # r-x — cannot create files inside
    monkeypatch.setenv("TRUEARCH_DB_PATH", str(locked / "telemetry.db"))
    import src.telemetry.storage as storage_mod
    importlib.reload(storage_mod)
    yield storage_mod
    os.chmod(locked, 0o700)  # let pytest clean the tmp dir up


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_importing_storage_never_raises_on_unwritable_db(readonly_storage):
    """Importing telemetry must not crash the server (the HF Spaces regression)."""
    assert readonly_storage.telemetry_available() is False


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_logging_is_a_noop_when_db_unwritable(readonly_storage):
    """A telemetry write failure must never propagate to the caller's request."""
    readonly_storage.log_recommendation(
        "q", "G", ["langgraph"], [], "startup", "speed"
    )  # must not raise


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_insights_reports_unavailable_rather_than_failing(readonly_storage):
    insights = readonly_storage.get_insights()
    assert insights["total_queries"] == 0
    assert insights["telemetry_available"] is False
    assert "TRUEARCH_DB_PATH" in insights["note"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_falls_back_to_tmp_when_default_path_unwritable(tmp_path, monkeypatch):
    """With no explicit override, an unwritable ./data must fall back to the temp dir.

    This is what keeps telemetry working (rather than silently off) in a
    container whose app directory is not writable by the runtime user.
    """
    import tempfile

    fallback = Path(tempfile.gettempdir()) / "truearch_telemetry.db"
    for suffix in ("", "-wal", "-shm"):
        Path(str(fallback) + suffix).unlink(missing_ok=True)

    monkeypatch.delenv("TRUEARCH_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    os.chmod(tmp_path / "data", 0o500)  # r-x — ./data/telemetry.db is impossible

    import src.telemetry.storage as storage_mod
    importlib.reload(storage_mod)
    try:
        assert storage_mod.telemetry_available() is True
        assert storage_mod._db_path() == str(fallback)
        storage_mod.log_recommendation("q", "G", ["qdrant"], [], "startup", "speed")
        assert storage_mod.get_insights()["total_queries"] == 1
    finally:
        os.chmod(tmp_path / "data", 0o700)
        for suffix in ("", "-wal", "-shm"):
            Path(str(fallback) + suffix).unlink(missing_ok=True)
