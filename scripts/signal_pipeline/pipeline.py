"""
TrueArch Signal Refresh Pipeline — Orchestrator

Runs all signal crawlers for a batch of frameworks and generates a
patch report showing what changed vs the current YAML data.

Usage:
    # Refresh all frameworks in the catalog:
    python scripts/signal_pipeline/pipeline.py

    # Refresh specific frameworks only:
    python scripts/signal_pipeline/pipeline.py --frameworks langgraph pinecone qdrant

    # Dry run (show what would change without writing):
    python scripts/signal_pipeline/pipeline.py --dry-run

Outputs:
    - Console summary of changed signals
    - data/signal_patches/YYYY-MM-DD.json (patch file for human review)

IMPORTANT: Human review before applying patches to YAML files.
The pipeline NEVER writes directly to data/frameworks/*.yaml.
Changes require a PR review per CURATION_POLICY.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.signal_pipeline.github_crawler import fetch_repo_signals
from scripts.signal_pipeline.pypi_crawler import fetch_pypi_signals
from scripts.signal_pipeline.npm_crawler import fetch_npm_signals


# ── Framework → Source Mapping ────────────────────────────────────────────────
# Maps TrueArch framework IDs to their GitHub repo and package registry entry.
# Use "pypi" for Python packages and "npm" for JS/TS packages. Managed services
# with no installable package use github-only (release tags) or are omitted.

FRAMEWORK_SOURCES: Dict[str, Dict[str, Optional[str]]] = {
    "langgraph":         {"github": "langchain-ai/langgraph",        "pypi": "langgraph"},
    "langchain":         {"github": "langchain-ai/langchain",         "pypi": "langchain"},
    "crewai":            {"github": "crewAIInc/crewAI",               "pypi": "crewai"},
    "autogen":           {"github": "microsoft/autogen",              "pypi": "pyautogen"},
    "pydantic_ai":       {"github": "pydantic/pydantic-ai",           "pypi": "pydantic-ai"},
    "smolagents":        {"github": "huggingface/smolagents",          "pypi": "smolagents"},
    "dspy":              {"github": "stanfordnlp/dspy",               "pypi": "dspy-ai"},
    "llamaindex":        {"github": "run-llama/llama_index",          "pypi": "llama-index"},
    "fastapi":           {"github": "fastapi/fastapi",                "pypi": "fastapi"},
    "pinecone":          {"github": "pinecone-io/pinecone-python-client", "pypi": "pinecone"},
    "qdrant":            {"github": "qdrant/qdrant-client",           "pypi": "qdrant-client"},
    "weaviate":          {"github": "weaviate/weaviate",              "pypi": "weaviate-client"},
    "chroma":            {"github": "chroma-core/chroma",             "pypi": "chromadb"},
    "milvus":            {"github": "milvus-io/milvus",               "pypi": "pymilvus"},
    "redis":             {"github": "redis/redis-py",                 "pypi": "redis"},
    "opentelemetry":     {"github": "open-telemetry/opentelemetry-python", "pypi": "opentelemetry-api"},
    "langsmith":         {"github": "langchain-ai/langsmith-sdk",     "pypi": "langsmith"},
    "openai_sdk":        {"github": "openai/openai-python",           "pypi": "openai"},
    "anthropic_sdk":     {"github": "anthropics/anthropic-sdk-python", "pypi": "anthropic"},
    "ollama":            {"github": "ollama/ollama",                  "pypi": "ollama"},
    "haystack":          {"github": "deepset-ai/haystack",            "pypi": "haystack-ai"},
    "semantic_kernel":   {"github": "microsoft/semantic-kernel",      "pypi": "semantic-kernel"},
    "logfire":           {"github": "pydantic/logfire",               "pypi": "logfire"},
    "weights_biases":    {"github": "wandb/wandb",                    "pypi": "wandb"},
    "mastra":            {"github": "mastra-ai/mastra",               "npm": "@mastra/core"},
    "vercel_ai_sdk":     {"github": "vercel/ai",                      "npm": "ai"},
    "mcp_sdk_python":    {"github": "modelcontextprotocol/python-sdk", "pypi": "mcp"},
    "google_adk":        {"github": "google/adk-python",              "pypi": "google-adk"},
    # ── Extended coverage (previously unmapped) ──────────────────────────────
    "a2a":               {"github": "a2aproject/A2A",                 "pypi": "a2a-sdk"},
    "arize":             {"github": "Arize-ai/phoenix",               "pypi": "arize-phoenix"},
    "guardrails_ai":     {"github": "guardrails-ai/guardrails",       "pypi": "guardrails-ai"},
    "helicone":          {"github": "Helicone/helicone",              "npm": "@helicone/helicone"},
    "modal":             {"github": "modal-labs/modal-client",        "pypi": "modal"},
    "mongodb":           {"github": "mongodb/mongo-python-driver",    "pypi": "pymongo"},
    "nemo_guardrails":   {"github": "NVIDIA/NeMo-Guardrails",         "pypi": "nemoguardrails"},
    "postgresql_pgvector": {"github": "pgvector/pgvector",            "pypi": None},  # C extension; github releases only
    "supabase":          {"github": "supabase/supabase-py",          "pypi": "supabase"},
    "flyio":             {"github": "superfly/flyctl",                "pypi": None},  # managed platform; release tags only
}


def refresh_framework(framework_id: str, versions_only: bool = False) -> Dict[str, Any]:
    """Run all applicable crawlers for a framework and return the patch.

    versions_only: skip the (slower, rate-limited) GitHub crawl and fetch only
    the registry version/release date — the "fast lane".
    """
    sources = FRAMEWORK_SOURCES.get(framework_id)
    if not sources:
        return {
            "framework_id": framework_id,
            "status": "skipped",
            "reason": "No source mapping defined.",
        }

    patch: Dict[str, Any] = {
        "framework_id": framework_id,
        "status": "ok",
        "github_signals": None,
        "pypi_signals": None,
        "errors": [],
    }

    print(f"\n[{framework_id}]")

    # GitHub signals (skipped in versions-only mode)
    if sources.get("github") and not versions_only:
        try:
            github_data = fetch_repo_signals(sources["github"])
            if "error" in github_data:
                patch["errors"].append(github_data["error"])
            else:
                patch["github_signals"] = github_data
        except Exception as e:
            patch["errors"].append(f"GitHub crawler error: {e}")

    # Registry signals: PyPI for Python packages, npm for JS/TS packages.
    if sources.get("pypi"):
        try:
            pypi_data = fetch_pypi_signals(sources["pypi"])
            if "error" in pypi_data:
                patch["errors"].append(pypi_data["error"])
            else:
                patch["pypi_signals"] = pypi_data
        except Exception as e:
            patch["errors"].append(f"PyPI crawler error: {e}")
    elif sources.get("npm"):
        try:
            npm_data = fetch_npm_signals(sources["npm"])
            if "error" in npm_data:
                patch["errors"].append(npm_data["error"])
            else:
                # apply_patch treats pypi_signals as the canonical version source.
                patch["pypi_signals"] = npm_data
        except Exception as e:
            patch["errors"].append(f"npm crawler error: {e}")

    if patch["errors"]:
        patch["status"] = "partial" if (patch["github_signals"] or patch["pypi_signals"]) else "error"

    return patch


def run_pipeline(
    framework_ids: Optional[List[str]] = None,
    dry_run: bool = False,
) -> None:
    target_ids = framework_ids or list(FRAMEWORK_SOURCES.keys())
    total = len(target_ids)

    print("=" * 64)
    print(f"  TrueArch Signal Refresh Pipeline")
    print(f"  Refreshing {total} framework(s)...")
    if dry_run:
        print("  [DRY RUN] No files will be written.")
    print("=" * 64)

    patches = []
    ok_count = 0
    error_count = 0

    for i, fid in enumerate(target_ids, 1):
        print(f"\n  [{i}/{total}] ", end="")
        result = refresh_framework(fid)
        patches.append(result)
        if result["status"] == "ok":
            ok_count += 1
        else:
            error_count += 1

    # Write patch file
    patch_dir = Path("data/signal_patches")
    patch_dir.mkdir(exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    patch_file = patch_dir / f"{today}.json"

    if not dry_run:
        with open(patch_file, "w") as f:
            json.dump({
                "generated": datetime.utcnow().isoformat(),
                "status": "human_review_required",
                "note": (
                    "This file contains proposed signal updates. "
                    "Human review is REQUIRED before applying to data/frameworks/*.yaml. "
                    "Do not merge automatically."
                ),
                "patches": patches,
            }, f, indent=2)
        print(f"\n\n  ✅ Patch file written: {patch_file}")
        print("  ⚠️  HUMAN REVIEW REQUIRED before applying patches to YAML files.")
    else:
        print(f"\n\n  [DRY RUN] Would write: {patch_file}")

    # Summary
    print(f"\n  {'─' * 50}")
    print(f"  Pipeline complete: {ok_count}/{total} OK  |  {error_count} errors")
    print(f"  {'─' * 50}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="TrueArch Signal Refresh Pipeline")
    parser.add_argument(
        "--frameworks",
        nargs="+",
        help="Specific framework IDs to refresh (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing any files",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all frameworks with source mappings and exit",
    )
    args = parser.parse_args()

    if args.list:
        print("\n  Framework → Source Mappings:")
        print("  " + "-" * 50)
        for fid, srcs in FRAMEWORK_SOURCES.items():
            gh = srcs.get("github") or "—"
            pypi = srcs.get("pypi") or "—"
            print(f"  {fid:<22} github={gh}")
            print(f"  {'':22} pypi={pypi}")
        return

    run_pipeline(
        framework_ids=args.frameworks,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
