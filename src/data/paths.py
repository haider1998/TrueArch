"""Robust resolution of the framework data directory.

Works both in-repo (running from a checkout) and when installed as a wheel via
`pip`/`uvx`, because the build ships `data/` alongside `src/` at the same level,
so `parents[2] / data / frameworks` points at the right place in both layouts.
"""
import os
from pathlib import Path


def frameworks_dir() -> str:
    """Return the absolute path to data/frameworks, honoring TRUEARCH_DATA_DIR."""
    env = os.environ.get("TRUEARCH_DATA_DIR")
    if env:
        return env
    # src/data/paths.py → parents[2] is the repo root (or the wheel install root),
    # which contains the data/ directory in both layouts.
    candidate = Path(__file__).resolve().parents[2] / "data" / "frameworks"
    if candidate.exists():
        return str(candidate)
    # Last-resort CWD-relative fallback (e.g. exotic packaging).
    return "data/frameworks"
