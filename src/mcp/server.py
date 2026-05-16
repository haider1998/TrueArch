"""
TrueArch MCP Server — FastMCP v1.27.1

Provides the following tools to AI agents and IDEs:
  1. recommend_ai_stack          → Full multi-layer stack recommendation with Genome
  2. compare_frameworks          → Dimension-by-dimension tradeoff comparison
  3. get_framework_score         → TrueArch score for a single framework
  4. get_recommendation          → Best frameworks in a specific category
  5. latest_stable_versions      → Latest verified stable versions for requested frameworks
  6. architecture_tradeoffs      → Key tradeoffs for a chosen framework

Transport:
  - Phase 1: stdio  (default — works with Cursor, Claude Code, any MCP client)
  - Phase 2: streamable-http  (run with --http flag for HTTP deployments)

Usage:
  python -m src.mcp.server            # stdio
  python -m src.mcp.server --http     # streamable HTTP on :8001/mcp
"""
from __future__ import annotations

import sys
import os
import json
from datetime import date
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

from src.data.loader import FrameworkLoader
from src.data.models import FrameworkSchema
from src.scoring.engine import ScoringEngine
from src.recommendation.stack_engine import StackRecommendationEngine
from src.recommendation.comparator import TradeoffComparator
from src.recommendation.models import (
    StackQuery, ComplianceFlag, ScaleTier, PriorityAxis, ArchLayer,
)

# ── Bootstrap ────────────────────────────────────────────────────────────────

_DATA_DIR = os.environ.get("TRUEARCH_DATA_DIR", "data/frameworks")

_loader = FrameworkLoader(data_dir=_DATA_DIR)
_frameworks = _loader.load_all()

# Score all frameworks at startup (deterministic, cached in memory)
_scoring_engine = ScoringEngine()
for _fw in _frameworks.values():
    _fw.computed_scores = _scoring_engine.compute_scores(_fw)

_stack_engine = StackRecommendationEngine(_frameworks)
_comparator = TradeoffComparator(_frameworks)

_FRAMEWORK_COUNT = len(_frameworks)
_FRAMEWORK_IDS = sorted(_frameworks.keys())

# ── FastMCP Server ────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="truearch-intelligence",
    instructions=(
        "TrueArch is the architecture intelligence layer for AI-native engineering. "
        "Use it to get deterministic, scored, and auditable framework recommendations "
        "for any AI system you are building. Every recommendation includes an Architecture "
        f"Genome, confidence score, and tradeoff notes. "
        f"Loaded: {_FRAMEWORK_COUNT} frameworks ({', '.join(_FRAMEWORK_IDS[:8])}...)."
    ),
    port=8001,
    stateless_http=True,
)


# ── Tool 1: recommend_ai_stack ───────────────────────────────────────────────

@mcp.tool(
    description=(
        "Get a full multi-layer AI stack recommendation for a system you're building. "
        "Returns the best framework for each architectural layer (orchestration, vector_db, "
        "observability, safety, api_layer, database, deployment) with TrueArch scores, "
        "confidence, alternatives, an Architecture Genome fingerprint, and an ADR summary. "
        "Always call this first when starting a new AI system."
    )
)
def recommend_ai_stack(
    problem: str,
    compliance: list[str] | None = None,
    scale: str = "growth",
    priority: str = "reliability",
    language: str = "python",
    layers: list[str] | None = None,
) -> dict:
    """
    Args:
        problem:    Description of the system to build (min 10 chars).
        compliance: List of compliance requirements: hipaa, soc2, gdpr, none.
        scale:      prototype | growth | scale | enterprise.
        priority:   low_latency | cost_efficiency | reliability | developer_speed | governance.
        language:   Primary programming language (default: python).
        layers:     Specific layers to recommend. Omit for all layers.
    """
    compliance_flags = []
    for c in (compliance or ["none"]):
        try:
            compliance_flags.append(ComplianceFlag(c.lower()))
        except ValueError:
            pass
    if not compliance_flags:
        compliance_flags = [ComplianceFlag.NONE]

    try:
        scale_enum = ScaleTier(scale.lower())
    except ValueError:
        scale_enum = ScaleTier.GROWTH

    try:
        priority_enum = PriorityAxis(priority.lower())
    except ValueError:
        priority_enum = PriorityAxis.RELIABILITY

    arch_layers = None
    if layers:
        arch_layers = []
        for l in layers:
            try:
                arch_layers.append(ArchLayer(l.lower()))
            except ValueError:
                pass

    query = StackQuery(
        problem=problem,
        compliance=compliance_flags,
        scale=scale_enum,
        priority=priority_enum,
        language=language,
        layers=arch_layers,
    )

    rec = _stack_engine.recommend(query)
    result = rec.model_dump()

    # Add staleness warning if any layer uses stale data
    stale_layers = []
    for layer_name, choice in rec.layers.items():
        fw = _frameworks.get(choice.framework_id)
        if fw:
            scores = fw.computed_scores
            if scores.valid_until and scores.valid_until < date.today():
                stale_layers.append(choice.framework_name)

    if stale_layers:
        result["staleness_warning"] = (
            f"Signals for {', '.join(stale_layers)} may be stale (>30 days). "
            "Confidence scores are reduced accordingly."
        )

    return result


# ── Tool 2: compare_frameworks ───────────────────────────────────────────────

@mcp.tool(
    description=(
        "Compare two frameworks head-to-head across all 5 TrueArch scoring dimensions: "
        "Production Stability, Ecosystem Momentum, Migration Risk, Governance Readiness, "
        "Agent Compatibility. Returns dimension-by-dimension analysis, overall winner, "
        "concrete 'when to pick' scenarios, and an ADR-ready recommendation narrative. "
        "Use when choosing between two specific options."
    )
)
def compare_frameworks(
    framework_a: str,
    framework_b: str,
    use_case: str | None = None,
) -> dict:
    """
    Args:
        framework_a: ID of first framework (e.g. 'langgraph', 'crewai').
        framework_b: ID of second framework.
        use_case:    Optional context for the comparison (e.g. 'HIPAA patient data assistant').

    Raises:
        ValueError if either framework_id is unknown.
    """
    if framework_a == framework_b:
        return {
            "error": "Cannot compare a framework with itself.",
            "available_frameworks": _FRAMEWORK_IDS,
        }

    if framework_a not in _frameworks:
        return {
            "error": f"Unknown framework: '{framework_a}'.",
            "available_frameworks": _FRAMEWORK_IDS,
        }
    if framework_b not in _frameworks:
        return {
            "error": f"Unknown framework: '{framework_b}'.",
            "available_frameworks": _FRAMEWORK_IDS,
        }

    comparison = _comparator.compare(framework_a, framework_b, use_case=use_case)
    return comparison.model_dump()


# ── Tool 3: get_framework_score ───────────────────────────────────────────────

@mcp.tool(
    description=(
        "Get the full TrueArch score for a single framework. Returns all 5 dimension scores "
        "(0-100), overall score, confidence, score band (Excellent/Strong/Good/Fair/Weak/Poor), "
        "and data freshness. Use when you want to evaluate one specific framework's current health."
    )
)
def get_framework_score(framework_id: str) -> dict:
    """
    Args:
        framework_id: The framework ID (e.g. 'langgraph', 'fastapi', 'qdrant').
    """
    if framework_id not in _frameworks:
        return {
            "error": f"Unknown framework: '{framework_id}'.",
            "available_frameworks": _FRAMEWORK_IDS,
        }

    fw = _frameworks[framework_id]
    scores = fw.computed_scores

    # Staleness status
    staleness_status = "fresh"
    if scores.valid_until:
        days_remaining = (scores.valid_until - date.today()).days
        if days_remaining < 0:
            staleness_status = "expired"
        elif days_remaining < 7:
            staleness_status = "stale"
        elif days_remaining < 15:
            staleness_status = "acceptable"

    return {
        "framework_id": fw.id,
        "framework_name": fw.name,
        "version": fw.latest_stable_version,
        "category": fw.category,
        "genome_code": fw.genome_dimension.value,
        "genome_dimension": fw.genome_dimension.key,
        "scores": {
            "overall": scores.overall,
            "score_band": scores.score_band,
            "confidence": scores.confidence,
            "production_stability": scores.production_stability,
            "ecosystem_momentum": scores.ecosystem_momentum,
            "migration_risk": scores.migration_risk,
            "governance_readiness": scores.governance_readiness,
            "agent_compatibility": scores.agent_compatibility,
        },
        "staleness": {
            "status": staleness_status,
            "last_computed": scores.last_computed.isoformat() if scores.last_computed else None,
            "valid_until": scores.valid_until.isoformat() if scores.valid_until else None,
        },
        "known_issues_count": len(fw.known_issues),
        "critical_issues": [
            {"id": i.id, "severity": i.severity, "description": i.description[:120]}
            for i in fw.known_issues
            if i.severity in ("critical", "high")
        ],
    }


# ── Tool 4: get_recommendation ───────────────────────────────────────────────

@mcp.tool(
    description=(
        "Get the top-ranked frameworks in a specific architectural category, sorted by "
        "TrueArch score. Categories: orchestration, vector_db (or vector-db), observability, "
        "api (api_layer), database (db), deployment, safety (guardrails), protocol. "
        "Returns top N frameworks with scores and key metadata."
    )
)
def get_recommendation(
    category: str,
    top_n: int = 5,
    min_score: float = 0.0,
) -> dict:
    """
    Args:
        category: Framework category to query.
        top_n:    Max number of results (1-10).
        min_score: Minimum overall score filter (0-100).
    """
    # Normalize category aliases
    _aliases = {
        "vector_db": "vector-db", "vectordb": "vector-db",
        "vector db": "vector-db", "api_layer": "api", "api-layer": "api",
        "guardrails": "safety", "db": "database", "memory": "database",
    }
    normalized = _aliases.get(category.lower().replace("-", "_"), category.lower())

    candidates = [
        fw for fw in _frameworks.values()
        if (fw.category.lower() == normalized
            or fw.category.lower() == category.lower())
        and (fw.computed_scores.overall or 0) >= min_score
    ]

    if not candidates:
        available_cats = sorted(set(fw.category for fw in _frameworks.values()))
        return {
            "error": f"No frameworks found in category '{category}'.",
            "available_categories": available_cats,
        }

    candidates.sort(key=lambda f: f.computed_scores.overall or 0, reverse=True)
    top = candidates[: min(top_n, 10)]

    return {
        "category": category,
        "total_in_category": len(candidates),
        "results": [
            {
                "rank": idx + 1,
                "framework_id": fw.id,
                "framework_name": fw.name,
                "version": fw.latest_stable_version,
                "overall_score": fw.computed_scores.overall,
                "score_band": fw.computed_scores.score_band,
                "confidence": fw.computed_scores.confidence,
                "genome_code": fw.genome_dimension.value,
            }
            for idx, fw in enumerate(top)
        ],
    }


# ── Tool 5: latest_stable_versions ───────────────────────────────────────────

@mcp.tool(
    description=(
        "Get the latest verified stable version for one or more frameworks. "
        "All versions are validated against CURATION_POLICY — never inferred. "
        "Use when you need to pin exact dependency versions in requirements.txt, "
        "package.json, or any lockfile."
    )
)
def latest_stable_versions(framework_ids: list[str]) -> dict:
    """
    Args:
        framework_ids: List of framework IDs to get versions for.
    """
    results = {}
    unknown = []
    for fid in framework_ids:
        fw = _frameworks.get(fid)
        if fw:
            scores = fw.computed_scores
            results[fid] = {
                "name": fw.name,
                "version": fw.latest_stable_version,
                "released": fw.latest_stable_released,
                "score_band": scores.score_band,
                "overall_score": scores.overall,
                "curation_status": fw.curation.status,
                "last_validated": fw.curation.last_validated.isoformat(),
            }
        else:
            unknown.append(fid)

    response: dict = {"versions": results}
    if unknown:
        response["unknown_frameworks"] = unknown
        response["available_frameworks"] = _FRAMEWORK_IDS

    return response


# ── Tool 6: architecture_tradeoffs ───────────────────────────────────────────

@mcp.tool(
    description=(
        "Get the key architectural tradeoffs, known production issues, and 'when to use' "
        "guidance for a specific framework. Returns curated known issues (severity-ranked), "
        "compatibility notes with other frameworks, and migration paths. "
        "Use when you've chosen a framework and want to understand its risks before committing."
    )
)
def architecture_tradeoffs(framework_id: str) -> dict:
    """
    Args:
        framework_id: The framework ID to get tradeoff analysis for.
    """
    if framework_id not in _frameworks:
        return {
            "error": f"Unknown framework: '{framework_id}'.",
            "available_frameworks": _FRAMEWORK_IDS,
        }

    fw = _frameworks[framework_id]
    scores = fw.computed_scores

    return {
        "framework_id": fw.id,
        "framework_name": fw.name,
        "version": fw.latest_stable_version,
        "overall_score": scores.overall,
        "score_band": scores.score_band,
        "known_issues": [
            {
                "id": issue.id,
                "severity": issue.severity,
                "description": issue.description,
                "affected_versions": issue.affected_versions,
                "resolved": issue.resolved,
                "workaround": issue.workaround,
                "source": issue.source,
            }
            for issue in sorted(fw.known_issues, key=lambda i: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(i.severity, 4))
        ],
        "compatible_with": [
            {
                "framework": c.framework,
                "strength": c.strength,
                "notes": c.notes,
            }
            for c in sorted(fw.compatible_with, key=lambda c: c.strength, reverse=True)
        ],
        "conflicts_with": [
            {"framework": c.framework, "severity": c.severity, "notes": c.notes}
            for c in fw.conflicts_with
        ],
        "supersedes": [
            {"framework": s.framework, "confidence": s.confidence, "notes": s.notes}
            for s in fw.supersedes
        ],
        "migration_paths": [
            {"to_framework": m.framework, "effort_0_to_1": m.effort, "notes": m.notes}
            for m in fw.migrates_to
        ],
        "curator_notes": fw.curation.notes,
        "last_validated": fw.curation.last_validated.isoformat(),
    }

# ── Entry Point ───────────────────────────────────────────────────────────────

_START_TIME = date.today().isoformat()
_VERSION = "1.0.0"


def _build_http_app() -> FastAPI:
    """
    Wrap the FastMCP ASGI app inside a FastAPI application for HTTP mode.
    Adds /health and /version endpoints required by Fly.io health checks
    and MCP client discovery.
    """
    http_app = FastAPI(
        title="TrueArch MCP",
        description="Architecture intelligence layer for AI-native engineering.",
        version=_VERSION,
        docs_url=None,   # No Swagger UI on the MCP server
        redoc_url=None,
    )

    # CORS — allow MCP clients from any origin (Cursor, Claude Code, Codex, etc.)
    http_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @http_app.get("/health", tags=["system"])
    async def health():
        return JSONResponse({
            "status": "ok",
            "version": _VERSION,
            "frameworks_loaded": _FRAMEWORK_COUNT,
            "date": _START_TIME,
        })

    @http_app.get("/version", tags=["system"])
    async def version():
        return JSONResponse({
            "service": "truearch-mcp",
            "version": _VERSION,
            "frameworks": _FRAMEWORK_COUNT,
            "framework_ids": _FRAMEWORK_IDS,
            "mcp_tools": [
                "recommend_ai_stack",
                "compare_frameworks",
                "get_framework_score",
                "get_recommendation",
                "latest_stable_versions",
                "architecture_tradeoffs",
            ],
        })

    # Mount the MCP server at /mcp — this is where all MCP traffic goes
    http_app.mount("/mcp", mcp.streamable_http_app())

    return http_app


def run() -> None:
    """Run the TrueArch MCP server."""
    use_http = "--http" in sys.argv
    port = int(os.environ.get("PORT", 8001))

    if use_http:
        print(
            f"[TrueArch MCP] Starting streamable-HTTP server on port {port} "
            f"(loaded {_FRAMEWORK_COUNT} frameworks)",
            file=sys.stderr,
        )
        app = _build_http_app()
        host = os.environ.get("HOST", "127.0.0.1")  # Fly.io sets HOST=0.0.0.0
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
        )
    else:
        print(
            f"[TrueArch MCP] Starting stdio server "
            f"(loaded {_FRAMEWORK_COUNT} frameworks)",
            file=sys.stderr,
        )
        mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
