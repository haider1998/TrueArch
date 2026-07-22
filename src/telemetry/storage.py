"""Local-only, privacy-preserving telemetry.

Design rule: telemetry is a *nice-to-have*. It must NEVER be able to take the
server down. Every entry point degrades to a no-op if the database can't be
opened (read-only container, missing volume, permission mismatch), and the
failure is reported once on stderr rather than raised.

Resolution order for the DB location:
  1. $TRUEARCH_DB_PATH            (explicit override; used by tests & deploys)
  2. data/telemetry.db            (repo checkout / writable image)
  3. $TMPDIR/truearch_telemetry.db (ephemeral fallback — containers)
  4. disabled                     (everything else)
"""
import os
import sqlite3
import json
import hashlib
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional

_SCHEMA = """
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
"""

# Resolved lazily on first use: None = not yet probed, "" = telemetry disabled.
_resolved_path: Optional[str] = None
_warned = False


def _candidate_paths() -> List[str]:
    """Candidate DB locations, most-preferred first."""
    env = os.environ.get("TRUEARCH_DB_PATH")
    if env:
        # An explicit override is honored alone — never silently redirected.
        return [env]
    return [
        "data/telemetry.db",
        os.path.join(tempfile.gettempdir(), "truearch_telemetry.db"),
    ]


def _try_open(path: str) -> bool:
    """Create the schema at `path`. True if the DB is usable."""
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with sqlite3.connect(path, timeout=5) as conn:
            # WAL: safe for concurrent readers + one writer (multi-worker uvicorn)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_SCHEMA)
            conn.commit()
        return True
    except (OSError, sqlite3.Error):
        return False


def _db_path() -> str:
    """Resolve (once) a writable DB path, or "" if telemetry is unavailable."""
    global _resolved_path, _warned
    if _resolved_path is not None:
        return _resolved_path

    for candidate in _candidate_paths():
        if _try_open(candidate):
            _resolved_path = candidate
            return _resolved_path

    _resolved_path = ""
    if not _warned:
        _warned = True
        print(
            "[TrueArch] Telemetry disabled: no writable database location "
            f"(tried: {', '.join(_candidate_paths())}). "
            "The server runs normally; only usage insights are unavailable.",
            file=sys.stderr,
        )
    return _resolved_path


def reset_path_cache() -> None:
    """Re-probe the DB location. Used by tests that monkeypatch TRUEARCH_DB_PATH."""
    global _resolved_path, _warned
    _resolved_path = None
    _warned = False


def telemetry_available() -> bool:
    """Whether usage insights can be recorded in this environment."""
    return bool(_db_path())


def log_recommendation(
    query_problem: str,
    genome_short: Optional[str],
    framework_ids: List[str],
    compliance: List[str],
    scale: str,
    priority: str
) -> None:
    """Log a recommendation outcome for later flywheel analysis.

    Privacy: the raw problem text is never stored. Only a stable, non-reversible
    SHA-256 prefix is kept for dedup/volume analysis.

    Never raises — a telemetry failure must not fail the caller's request.
    """
    path = _db_path()
    if not path:
        return

    # Stable across processes (unlike builtin hash(), which is per-process salted)
    query_hash = hashlib.sha256((query_problem or "").encode("utf-8")).hexdigest()[:16]

    try:
        with sqlite3.connect(path, timeout=5) as conn:
            conn.execute(
                """
                INSERT INTO recommendation_outcomes
                (timestamp, query_hash, genome_short, framework_ids, compliance, scale, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    query_hash,
                    genome_short,
                    json.dumps(framework_ids),
                    json.dumps(compliance),
                    scale,
                    priority,
                ),
            )
            conn.commit()
    except (OSError, sqlite3.Error) as exc:
        print(f"[TrueArch] Telemetry write skipped: {exc}", file=sys.stderr)


def _rows() -> List[sqlite3.Row]:
    path = _db_path()
    if not path:
        return []
    try:
        conn = sqlite3.connect(path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM recommendation_outcomes ORDER BY timestamp DESC")
            return cur.fetchall()
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return []


def get_insights(top_n: int = 10) -> dict:
    """Aggregate local telemetry into usage insights.

    Returns totals, the most-recommended individual frameworks and full stacks,
    scale/priority/compliance distributions, and the most recent queries
    (identified only by genome + hash — never raw problem text).
    """
    top_n = min(max(top_n, 1), 20)

    if not telemetry_available():
        return {
            "total_queries": 0,
            "telemetry_available": False,
            "note": (
                "Telemetry is unavailable in this environment (no writable "
                "database location). Set TRUEARCH_DB_PATH to a writable path "
                "to enable usage insights. All other tools are unaffected."
            ),
        }

    rows = _rows()
    total = len(rows)
    if total == 0:
        return {
            "total_queries": 0,
            "telemetry_available": True,
            "note": (
                "No telemetry recorded yet. Serve at least one recommendation "
                "query for insights to populate."
            ),
        }

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
        "telemetry_available": True,
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
