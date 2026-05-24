import os
import sqlite3
import json
from datetime import datetime, timezone
from typing import List, Optional

_DB_PATH = os.environ.get("TRUEARCH_DB_PATH", "data/telemetry.db")

def _init_db():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
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

# Initialize DB on load
_init_db()

def log_recommendation(
    query_problem: str,
    genome_short: Optional[str],
    framework_ids: List[str],
    compliance: List[str],
    scale: str,
    priority: str
) -> None:
    """Logs the outcomes of a recommendation for future flywheel analysis."""
    # Create a simple hash of the query for deduplication/analysis without storing PII
    query_hash = str(hash(query_problem))
    
    timestamp = datetime.now(timezone.utc).isoformat()
    frameworks_json = json.dumps(framework_ids)
    compliance_json = json.dumps(compliance)
    
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO recommendation_outcomes 
            (timestamp, query_hash, genome_short, framework_ids, compliance, scale, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, query_hash, genome_short, frameworks_json, compliance_json, scale, priority)
        )
        conn.commit()
