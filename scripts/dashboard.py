#!/usr/bin/env python3
"""
TrueArch Telemetry Dashboard — CLI

Shows real-time usage insights from local telemetry data.

Usage:
    python scripts/dashboard.py
    TRUEARCH_DB_PATH=data/telemetry.db python scripts/dashboard.py
    python scripts/dashboard.py --top 20
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure the project root is importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.telemetry.storage import get_insights  # noqa: E402


def _horizontal_bar(value: int, max_value: int, width: int = 30) -> str:
    """Draw a simple ASCII bar chart."""
    if max_value == 0:
        return " " * width
    filled = int((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)


def _print_header(title: str) -> None:
    print()
    print(f"  {'─' * 60}")
    print(f"  ┃  {title}")
    print(f"  {'─' * 60}")


def _print_row(label: str, value: int, max_value: int, extra: str = "") -> None:
    bar = _horizontal_bar(value, max_value)
    print(f"  {label:<28} {bar}  {value:>5}{extra}")


def _print_dist(title: str, dist: dict, default_label: str = "unknown") -> None:
    if not dist:
        return
    max_cnt = max(dist.values())
    _print_header(title)
    for label, cnt in dist.items():
        _print_row((label or default_label).ljust(20), cnt, max_cnt, " queries")


def run_dashboard(top_n: int = 10) -> None:
    insights = get_insights(top_n=top_n)

    # ── Header ──────────────────────────────────────────────────────────────
    print()
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║        TrueArch Telemetry Dashboard  •  v2.0.0              ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print(f"  Database: {os.environ.get('TRUEARCH_DB_PATH', 'data/telemetry.db')}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    total = insights.get("total_queries", 0)
    if total == 0:
        print()
        print(f"  ℹ️  {insights.get('note', 'No telemetry recorded yet.')}")
        print()
        return

    # ── Query volume ─────────────────────────────────────────────────────────
    _print_header("📊 Query Volume")
    print(f"  Total queries logged:      {total:>8,}")
    print(f"  Queries today:             {insights.get('queries_today', 0):>8,}")

    # ── Top frameworks ───────────────────────────────────────────────────────
    top_frameworks = insights.get("top_frameworks", [])
    if top_frameworks:
        max_freq = top_frameworks[0]["count"]
        _print_header("🔥 Most-Recommended Frameworks")
        for i, row in enumerate(top_frameworks, 1):
            _print_row(f"  {i:>2}. {row['framework'][:22]}", row["count"], max_freq, " uses")

    # ── Top stacks ───────────────────────────────────────────────────────────
    top_stacks = insights.get("top_stacks_recommended", [])
    if top_stacks:
        max_freq = top_stacks[0]["count"]
        _print_header("🧩 Top Recommended Stacks")
        for i, row in enumerate(top_stacks, 1):
            _print_row(f"  {i:>2}. {row['stack'][:22]}", row["count"], max_freq, " queries")

    # ── Distributions ────────────────────────────────────────────────────────
    _print_dist("⚡ Scale Distribution", insights.get("scale_distribution", {}))
    _print_dist("🎯 Priority Distribution", insights.get("priority_distribution", {}))
    _print_dist("🔒 Compliance Requirements", insights.get("compliance_distribution", {}), "none")

    # ── Recent queries (privacy-preserving: genome + hash only) ──────────────
    recent = insights.get("recent_queries", [])
    if recent:
        _print_header("🕐 Recent Queries")
        for row in recent:
            ts = (row.get("timestamp") or "")[:16]
            print(f"  [{ts}]  Genome: {row.get('genome', 'N/A')}")
            print(f"              → Query hash: {row.get('query_hash', '')}")
            print()

    # ── Footer ──────────────────────────────────────────────────────────────
    print(f"  {'─' * 60}")
    print("  ℹ️  Local-only & privacy-preserving. Raw queries are never stored.")
    print(f"  {'─' * 60}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="TrueArch Telemetry Dashboard")
    parser.add_argument(
        "--db",
        default=None,
        help="Path to telemetry SQLite database (overrides TRUEARCH_DB_PATH).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top results to show per category (default: 10)",
    )
    args = parser.parse_args()

    if args.db:
        os.environ["TRUEARCH_DB_PATH"] = args.db

    run_dashboard(top_n=args.top)


if __name__ == "__main__":
    main()
