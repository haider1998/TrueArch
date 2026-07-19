#!/usr/bin/env python3
"""
TrueArch daily-loop demo — reproducible, runs against the real server.

Shows the exact flow to record for the README GIF:
  1. An agent writes v2 Pinecone code → validate_code catches it (critical).
  2. The corrected code passes clean.
  3. Version-awareness: the same code on an older pin is NOT flagged.
  4. latest_stable_versions returns real pins + honest data age.

Usage:
    python scripts/demo/daily_loop.py
    # For a terminal recording:
    #   vhs scripts/demo/daily_loop.tape   (if you have charmbracelet/vhs)
    #   or: asciinema rec -c 'python scripts/demo/daily_loop.py'
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.mcp.server import validate_code, latest_stable_versions  # noqa: E402


def _rule(title: str) -> None:
    print(f"\n\033[1m━━ {title} \033[0m" + "━" * max(0, 56 - len(title)))


def main() -> None:
    print("\033[1mTrueArch — daily loop\033[0m  (the hallucination killer)\n")

    _rule("1. The agent just wrote this (trained on Pinecone v2)")
    bad = "import pinecone\npinecone.init(api_key='xxx')\nindex = pinecone.Index('docs')"
    print(bad)

    _rule("2. validate_code catches it")
    res = validate_code(code=bad, framework_id="pinecone")
    print(f"verdict: {res['verdict']}")
    for v in res.get("violations", []):
        print(f"  ✗ [{v['severity']}] {v['pattern_id']}: {v['description']}")
        print(f"    fix → {v['correct_example'].splitlines()[0]} ...")
        print(f"    docs: {v.get('docs_url')}")

    _rule("3. The corrected code passes clean")
    good = "from pinecone import Pinecone\npc = Pinecone(api_key='xxx')\nindex = pc.Index('docs')"
    print(good)
    res2 = validate_code(code=good, framework_id="pinecone")
    print(f"\nverdict: {res2['verdict']}  →  {res2['summary']}")

    _rule("4. Version-aware: on Pinecone 2.2.4 the old API is still valid")
    res3 = validate_code(code=bad, framework_id="pinecone", version="2.2.4")
    print(f"verdict: {res3['verdict']}  (no false alarm on the version you actually run)")

    _rule("5. Real version pins for your lockfile")
    versions = latest_stable_versions(framework_ids=["langgraph", "anthropic_sdk", "qdrant"])
    for fid, data in versions.get("versions", {}).items():
        print(f"  {fid:<16} {str(data.get('version')):<12} "
              f"(data age: {data.get('data_age_days')}d)")
    if versions.get("staleness_warning"):
        print(f"\n  ⚠️  {versions['staleness_warning']}")

    print("\n\033[1mThat's the loop.\033[0m Ground it, pin it, validate it — every session.\n")


if __name__ == "__main__":
    main()
