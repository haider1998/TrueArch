import os
import sqlite3
import json
import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional


def _db_path() -> str:
    """Resolve the telemetry DB path at call time so tests/env overrides apply."""
    return os.environ.get("TRUEARCH_DB_PATH", "data/telemetry.db")


def _init_db() -> None:
    path = _db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with sqlite3.connect(path) as conn:
        # WAL mode: safe for concurrent readers + one writer (multi-worker uvicorn)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                genome_short TEXT,
                framework_ids TEXT,
                compliance TEXT,
                scale TEXT,
                priority TEXT
            )
        """)
        conn.commit()


# Initialize DB on load (best-effort; read-only environments should not crash import)
try:
    _init_db()
except OSError:
    pass


def log_recommendation(
    query_problem: str,
    genome_short: Optional[str],
    framework_ids: List[str],
    compliance: List[str],
    scale: str,
    priority: str
) -> None:
    """Logs the outcomes of a recommendation for future flywheel analysis.

    Privacy: the raw problem text is never stored. Only a stable, non-reversible
    SHA-256 prefix is kept for dedup/volume analysis.
    """
    # Stable across processes (unlike builtin hash(), which is per-process salted)
    query_hash = hashlib.sha256((query_problem or "").encode("utf-8")).hexdigest()[:16]

    timestamp = datetime.now(timezone.utc).isoformat()
    frameworks_json = json.dumps(framework_ids)
    compliance_json = json.dumps(compliance)

    path = _db_path()
    _init_db()
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO recommendation_outcomes
            (timestamp, query_hash, genome_short, framework_ids, compliance, scale, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, query_hash, genome_short, frameworks_json, compliance_json, scale, priority)
        )
        conn.commit()


def _rows(top_n: int = 10) -> List[sqlite3.Row]:
    path = _db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM recommendation_outcomes ORDER BY timestamp DESC"
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_insights(top_n: int = 10) -> dict:
    """Aggregate local telemetry into usage insights.

    Returns totals, the most-recommended individual frameworks and full stacks,
    scale/priority/compliance distributions, and the most recent queries
    (identified only by genome + hash — never raw problem text).
    """
    top_n = min(max(top_n, 1), 20)
    path = _db_path()

    if not os.path.exists(path):
        return {
            "total_queries": 0,
            "note": (
                "No telemetry recorded yet. Serve at least one recommendation "
                "query for insights to populate."
            ),
        }

    rows = _rows()
    total = len(rows)
    if total == 0:
        return {"total_queries": 0, "note": "Telemetry database is empty."}

    framework_counter: Counter = Counter()
    stack_counter: Counter = Counter()
    scale_counter: Counter = Counter()
    priority_counter: Counter = Counter()
    compliance_counter: Counter = Counter()

    today_str = datetime.now(timezone.utc).date().isoformat()
    queries_today = 0

    for r in rows:
        ids: List[str] = []
        try:
            ids = json.loads(r["framework_ids"]) if r["framework_ids"] else []
        except (json.JSONDecodeError, TypeError):
            ids = []
        for fid in ids:
            framework_counter[fid] += 1
        if ids:
            stack_counter[" + ".join(ids)] += 1

        if r["scale"]:
            scale_counter[r["scale"]] += 1
        if r["priority"]:
            priority_counter[r["priority"]] += 1

        comp: List[str] = []
        try:
            comp = json.loads(r["compliance"]) if r["compliance"] else []
        except (json.JSONDecodeError, TypeError):
            comp = []
        for c in comp or ["none"]:
            compliance_counter[c or "none"] += 1

        ts = r["timestamp"] or ""
        if ts[:10] == today_str:
            queries_today += 1

    recent = [
        {
            "genome": r["genome_short"] or "N/A",
            "query_hash": r["query_hash"],
            "timestamp": r["timestamp"],
        }
        for r in rows[:5]
    ]

    return {
        "total_queries": total,
        "queries_today": queries_today,
        "top_frameworks": [
            {"framework": f, "count": c}
            for f, c in framework_counter.most_common(top_n)
        ],
        "top_stacks_recommended": [
            {"stack": s, "count": c}
            for s, c in stack_counter.most_common(top_n)
        ],
        "scale_distribution": dict(scale_counter.most_common()),
        "priority_distribution": dict(priority_counter.most_common()),
        "compliance_distribution": dict(compliance_counter.most_common()),
        "recent_queries": recent,
        "data_note": (
            "Telemetry is local-only and privacy-preserving: raw problem text is "
            "never stored, only a hashed identifier. Nothing leaves your environment."
        ),
    }
