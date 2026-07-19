"""
TrueArch MCP Server — FastMCP v1.27.1

Provides the following tools to AI agents and IDEs:
  1.  quick_context              → Compressed 150-200 token context brief
  2.  recommend_ai_stack         → Full multi-layer stack recommendation with Genome
  3.  compare_frameworks         → Dimension-by-dimension tradeoff comparison
  4.  get_framework_score        → TrueArch score for a single framework
  5.  get_recommendation         → Best frameworks in a specific category
  6.  latest_stable_versions     → Latest verified stable versions
  7.  architecture_tradeoffs     → Key tradeoffs for a chosen framework
  8.  get_code_patterns          → Version-pinned correct API patterns
  9.  generate_adr               → Architecture Decision Record in Markdown
  10. explain_score              → Why a framework received its TrueArch score
  11. genome_compare             → Similarity between two Architecture Genomes
  12. validate_code              → Detect deprecated APIs in LLM-generated code
  13. get_telemetry_insights     → Query patterns and framework demand signals

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
from src.telemetry.storage import log_recommendation, get_insights
from src.data.patterns import get_pattern, get_available_use_cases

# ── Bootstrap ────────────────────────────────────────────────────────────────

from src.data.paths import frameworks_dir as _frameworks_dir
_DATA_DIR = _frameworks_dir()

_loader = FrameworkLoader(data_dir=_DATA_DIR)
_frameworks = _loader.load_all()

# Score all frameworks at startup (deterministic, cached in memory)
_scoring_engine = ScoringEngine.from_frameworks(_frameworks)
for _fw in _frameworks.values():
    _fw.computed_scores = _scoring_engine.compute_scores(_fw)

_stack_engine = StackRecommendationEngine(_frameworks)
_comparator = TradeoffComparator(_frameworks)

# Share the loaded catalog with the code validator so its deprecated-API
# patterns come from the same YAML source (no second load).
from src.mcp.code_validator import set_frameworks as _set_validator_frameworks
_set_validator_frameworks(_frameworks)

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

def _clean_dict(d):
    """Recursively remove None values and empty collections to minimize token size."""
    if isinstance(d, dict):
        cleaned = {}
        for k, v in d.items():
            if v is None:
                continue
            cleaned_v = _clean_dict(v)
            if cleaned_v in ([], {}):
                continue
            cleaned[k] = cleaned_v
        return cleaned
    elif isinstance(d, list):
        return [_clean_dict(item) for item in d if item is not None]
    else:
        return d


# ── Tool 0.5: quick_context ───────────────────────────────────────────────

@mcp.tool(
    description=(
        "Get a token-budgeted, intent-aware architecture brief for a system you're building. "
        "Classifies your query intent, selects only the relevant TrueArch data, reorders known "
        "issues by relevance, tags data as verified/estimated, and stays within a token budget. "
        "Always call this first when starting a new AI system instead of recommend_ai_stack if you only need brief context."
    )
)
def quick_context(
    problem: str,
    compliance: list[str] | None = None,
    scale: str = "growth",
    priority: str = "reliability",
    language: str = "python",
    layers: list[str] | None = None,
    token_budget: int = 400,
) -> dict:
    """
    Args:
        problem:      Description of the system to build (min 10 chars).
        compliance:   List of compliance requirements: hipaa, soc2, gdpr, none.
        scale:        prototype | growth | scale | enterprise.
        priority:     low_latency | cost_efficiency | reliability | developer_speed | governance.
        language:     Primary programming language (default: python).
        layers:       Specific layers to recommend. Omit for all layers.
        token_budget: Target size of the optimized context payload (default 400).
    """
    from src.mcp.context_optimizer import compress_context

    full_result = recommend_ai_stack(problem, compliance, scale, priority, language, layers)
    if "error" in full_result:
        return full_result

    optimized_context, estimated_tokens, intent = compress_context(
        [{"tool": "recommend_ai_stack", "result": full_result}],
        query=problem,
        token_budget=token_budget,
    )

    return _clean_dict({
        "context_brief": full_result.get("context_brief"),
        "genome_short": full_result.get("genome_short"),
        "confidence": full_result.get("confidence"),
        "intent": intent.value,
        "optimized_context": optimized_context,
        "estimated_tokens": estimated_tokens,
        "staleness_warning": full_result.get("staleness_warning"),
    })

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
    token_budget: int | None = None,
) -> dict:
    """
    Args:
        problem:      Description of the system to build (min 10 chars).
        compliance:   List of compliance requirements: hipaa, soc2, gdpr, none.
        scale:        prototype | growth | scale | enterprise.
        priority:     low_latency | cost_efficiency | reliability | developer_speed | governance.
        language:     Primary programming language (default: python).
        layers:       Specific layers to recommend. Omit for all layers.
        token_budget: If set, also return an intent-compressed `optimized_context`
                      payload within this token budget (default: None = full result only).
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
                return {"error": f"Invalid layer: '{l}'. Valid layers are: {[e.value for e in ArchLayer]}"}

    from pydantic import ValidationError
    try:
        query = StackQuery(
            problem=problem,
            compliance=compliance_flags,
            scale=scale_enum,
            priority=priority_enum,
            language=language,
            layers=arch_layers,
        )
    except ValidationError as e:
        return {"error": f"Invalid query parameters: {str(e)}"}

    rec = _stack_engine.recommend(query)
    result = rec.model_dump(exclude_none=True, exclude={"query_summary"})


    # Log recommendation to telemetry
    framework_ids = [c.framework_id for c in rec.layers.values()]
    log_recommendation(
        query_problem=problem,
        genome_short=rec.genome_short,
        framework_ids=framework_ids,
        compliance=[c.value for c in compliance_flags],
        scale=scale_enum.value,
        priority=priority_enum.value
    )

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

    cleaned = _clean_dict(result)

    # Optional: intent-compressed payload for token-sensitive callers.
    if token_budget is not None:
        from src.mcp.context_optimizer import compress_context

        optimized_context, estimated_tokens, intent = compress_context(
            [{"tool": "recommend_ai_stack", "result": cleaned}],
            query=problem,
            token_budget=token_budget,
        )
        cleaned["optimized_context"] = optimized_context
        cleaned["estimated_tokens"] = estimated_tokens
        cleaned["intent"] = intent.value

    return cleaned


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
    return _clean_dict(comparison.model_dump(exclude_none=True))


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

    # Staleness status — single source of truth: computed from real data age
    # by the scoring engine (based on curation.last_validated + signal dates).
    staleness_status = scores.staleness_status or "fresh"

    return _clean_dict({
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
            "warning": scores.staleness_warning,
            "last_computed": scores.last_computed.isoformat() if scores.last_computed else None,
            "valid_until": scores.valid_until.isoformat() if scores.valid_until else None,
        },
        "known_issues_count": len(fw.known_issues),
        "critical_issues": [
            {"id": i.id, "severity": i.severity, "description": i.description[:120]}
            for i in fw.known_issues
            if i.severity in ("critical", "high")
        ],
        "curation": {
            "status": fw.curation.status if fw.curation else "curated",
            "notes": fw.curation.notes if fw.curation else None,
        } if fw.curation else None,
    })


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

    return _clean_dict({
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
    })


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
            data_age_days = (date.today() - fw.curation.last_validated).days
            results[fid] = {
                "name": fw.name,
                "version": fw.latest_stable_version,
                "released": fw.latest_stable_released,
                "score_band": scores.score_band,
                "overall_score": scores.overall,
                "curation_status": fw.curation.status,
                "last_validated": fw.curation.last_validated.isoformat(),
                "data_age_days": data_age_days,
            }
        else:
            unknown.append(fid)

    response: dict = {"versions": results}
    
    # Check for staleness warning
    stale_frameworks = [fid for fid, data in results.items() if data.get("data_age_days", 0) > 14]
    if stale_frameworks:
        response["staleness_warning"] = (
            f"The following frameworks have data older than 14 days: {', '.join(stale_frameworks)}. "
            "Versions may be outdated."
        )

    if unknown:
        response["unknown_frameworks"] = unknown
        response["available_frameworks"] = _FRAMEWORK_IDS

    return _clean_dict(response)


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

    return _clean_dict({
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
        ][:5],  # Limit to top 5 issues
        "compatible_with": [
            {
                "framework": c.framework,
                "strength": c.strength,
                "notes": c.notes,
            }
            for c in sorted(fw.compatible_with, key=lambda c: c.strength, reverse=True)
        ][:3],  # Limit to top 3
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
    })

# ── Tool 7: get_code_patterns ───────────────────────────────────────────────

@mcp.tool(
    description=(
        "Get the current correct way to write the most common patterns for a framework. "
        "Returns version-pinned snippets for the requested use case. "
        "Use this right before writing code for a specific framework to ensure you use the correct API."
    )
)
def get_code_patterns(framework_id: str, use_case: str) -> dict:
    """
    Args:
        framework_id: The framework ID (e.g., 'langgraph', 'fastapi').
        use_case: A keyword describing what you are trying to do (e.g., 'checkpoint', 'opentelemetry').
    """
    if framework_id not in _frameworks:
        return {
            "error": f"Unknown framework: '{framework_id}'.",
            "available_frameworks": _FRAMEWORK_IDS,
        }
        
    pattern = get_pattern(framework_id, use_case)
    if not pattern:
        available = get_available_use_cases(framework_id)
        return {
            "error": f"No pattern found for use case '{use_case}' in '{framework_id}'.",
            "available_use_cases": available
        }
        
    return _clean_dict(pattern.model_dump(exclude_none=True))


# ── Tool 8: generate_adr ─────────────────────────────────────────────────────

_adr_generator_mcp = None  # Lazy-init to avoid circular import at module load

def _get_adr_generator():
    global _adr_generator_mcp
    if _adr_generator_mcp is None:
        from src.recommendation.adr_generator import ADRGenerator
        _adr_generator_mcp = ADRGenerator()
    return _adr_generator_mcp


@mcp.tool(
    description=(
        "Generate a ready-to-commit Architecture Decision Record (ADR) in Markdown format. "
        "Runs a full stack recommendation then formats it as a standard ADR file with: "
        "Architecture Genome, per-layer rationale, alternatives rejected, risks documented, "
        "review schedule, and an Agent Context Brief for system prompt injection. "
        "Save the output as docs/adr/ADR-NNN.md in your project repository. "
        "Use after recommend_ai_stack when you want a human-readable, committable record of the decision."
    )
)
def generate_adr(
    problem: str,
    adr_number: int = 1,
    project_name: str | None = None,
    team: str | None = None,
    compliance: list[str] | None = None,
    scale: str = "growth",
    priority: str = "reliability",
    language: str = "python",
) -> dict:
    """
    Args:
        problem:      Description of the system to build (min 10 chars).
        adr_number:   Sequential ADR number for this project (default: 1).
        project_name: Optional project name to include in the ADR header.
        team:         Optional team name for attribution.
        compliance:   List of compliance requirements: hipaa, soc2, gdpr, none.
        scale:        prototype | growth | scale | enterprise.
        priority:     low_latency | cost_efficiency | reliability | developer_speed | governance.
        language:     Primary programming language (default: python).

    Returns:
        dict with keys:
          - markdown: str — the full ADR Markdown content ready to commit
          - filename: str — suggested filename (e.g. 'ADR-001.md')
          - genome_short: str — Architecture Genome fingerprint
          - adr_number: int — the ADR number used
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

    from pydantic import ValidationError
    try:
        query = StackQuery(
            problem=problem,
            compliance=compliance_flags,
            scale=scale_enum,
            priority=priority_enum,
            language=language,
        )
    except ValidationError as e:
        return {"error": f"Invalid query parameters: {str(e)}"}

    recommendation = _stack_engine.recommend(query)
    adr_gen = _get_adr_generator()
    markdown = adr_gen.generate(
        recommendation,
        adr_number=adr_number,
        project_name=project_name,
        team=team,
    )

    return _clean_dict({
        "markdown": markdown,
        "filename": f"ADR-{adr_number:03d}.md",
        "genome_short": recommendation.genome_short,
        "confidence": recommendation.confidence,
        "score_band": recommendation.score_band,
        "adr_number": adr_number,
    })


# ── Tool 9: explain_score ────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Explain WHY a framework received its TrueArch score. Returns a per-dimension "
        "breakdown with the raw signal values that drove each sub-score, plus the "
        "confidence calculation rationale. Use when an agent or developer asks "
        "'Why did X score Y?' or wants to challenge/validate a recommendation."
    )
)
def explain_score(framework_id: str) -> dict:
    """
    Args:
        framework_id: The framework ID to explain (e.g. 'langgraph', 'crewai').
    """
    if framework_id not in _frameworks:
        return {
            "error": f"Unknown framework: '{framework_id}'.",
            "available_frameworks": _FRAMEWORK_IDS,
        }

    fw = _frameworks[framework_id]
    scores = fw.computed_scores
    sigs = fw.signals

    def _band_label(score: float) -> str:
        if score >= 90: return "Excellent"
        if score >= 75: return "Strong"
        if score >= 60: return "Good"
        if score >= 45: return "Fair"
        if score >= 30: return "Weak"
        return "Poor"

    # 1. Compile migration_advisory
    migration_advisory = None
    if (scores.overall is not None and scores.overall < 70) or fw.curation.status == "deprecated" or any(issue.severity == "critical" or "MAINTENANCE" in issue.description.upper() for issue in fw.known_issues):
        reasons = []
        if scores.overall is not None and scores.overall < 70:
            reasons.append(f"overall score is low ({scores.overall}/100)")
        if fw.curation.status == "deprecated":
            reasons.append("curation status is deprecated")
        for issue in fw.known_issues:
            if "MAINTENANCE" in issue.description.upper():
                reasons.append("framework is in maintenance mode")
                break
        migration_advisory = f"Migration is recommended because {', and '.join(reasons)}."

    # 2. Compile superseded_by relationships
    superseded_by = []
    for other_fw in _frameworks.values():
        for s in getattr(other_fw, "supersedes", []):
            if s.framework == fw.id:
                superseded_by.append({
                    "framework_id": other_fw.id,
                    "framework_name": other_fw.name,
                    "confidence": s.confidence,
                    "notes": s.notes
                })
                
    # 3. Compile recommended_alternatives
    recommended_alternatives = []
    # Add from migrates_to
    for m in getattr(fw, "migrates_to", []):
        alt_fw = _frameworks.get(m.framework)
        alt_name = alt_fw.name if alt_fw else m.framework
        alt_score = alt_fw.computed_scores.overall if alt_fw else None
        recommended_alternatives.append({
            "framework_id": m.framework,
            "framework_name": alt_name,
            "overall_score": alt_score,
            "effort_estimate": m.effort,
            "notes": m.notes,
            "type": "direct_migration_target"
        })
    # If no migrates_to, fallback to category peers with higher score than this framework
    if not recommended_alternatives:
        category_peers = [other_fw for other_fw in _frameworks.values() 
                          if other_fw.category == fw.category and other_fw.id != fw.id]
        for peer in category_peers:
            if peer.computed_scores.overall is not None and (scores.overall is None or peer.computed_scores.overall > scores.overall):
                recommended_alternatives.append({
                    "framework_id": peer.id,
                    "framework_name": peer.name,
                    "overall_score": peer.computed_scores.overall,
                    "effort_estimate": 0.5, # default medium effort
                    "notes": f"Category peer with higher score ({peer.computed_scores.overall})",
                    "type": "category_peer"
                })
                
    recommended_alternatives = sorted(
        recommended_alternatives,
        key=lambda x: x.get("overall_score") or 0,
        reverse=True
    )

    return _clean_dict({
        "framework_id": fw.id,
        "framework_name": fw.name,
        "overall_score": scores.overall,
        "score_band": scores.score_band,
        "confidence": scores.confidence,
        "dimensions": {
            "production_stability": {
                "score": scores.production_stability,
                "weight": "30%",
                "band": _band_label(scores.production_stability or 0),
                "key_signals": {
                    "breaking_changes_per_90d": sigs.production_stability.breaking_changes_per_90d,
                    "issue_resolution_ratio": sigs.production_stability.issue_resolution_ratio,
                    "open_security_advisories": sigs.production_stability.open_security_advisories,
                    "incident_rate": sigs.production_stability.incident_rate,
                    "incident_rate_source": sigs.production_stability.incident_rate_source,
                },
            },
            "ecosystem_momentum": {
                "score": scores.ecosystem_momentum,
                "weight": "25%",
                "band": _band_label(scores.ecosystem_momentum or 0),
                "key_signals": {
                    "github_stars": sigs.ecosystem_momentum.github_stars,
                    "star_growth_30d_pct": sigs.ecosystem_momentum.star_growth_30d_pct,
                    "commits_last_90d": sigs.ecosystem_momentum.commits_last_90d,
                    "merged_prs_per_30d": sigs.ecosystem_momentum.merged_prs_per_30d,
                    "job_postings_30d": sigs.ecosystem_momentum.job_postings_30d,
                },
            },
            "migration_risk": {
                "score": scores.migration_risk,
                "weight": "15%",
                "band": _band_label(scores.migration_risk or 0),
                "note": "Higher = easier to migrate away (lower lock-in)",
                "key_signals": {
                    "viable_alternatives": sigs.migration_risk.viable_alternatives,
                    "public_api_methods": sigs.migration_risk.public_api_methods,
                    "migration_guide_count": sigs.migration_risk.migration_guide_count,
                    "community_migrations": sigs.migration_risk.community_migrations,
                },
            },
            "governance_readiness": {
                "score": scores.governance_readiness,
                "weight": "15%",
                "band": _band_label(scores.governance_readiness or 0),
                "key_signals": {
                    "unpatched_cves": sigs.governance_readiness.unpatched_cves,
                    "avg_days_to_patch": sigs.governance_readiness.avg_days_to_patch,
                    "hipaa_deployments": sigs.governance_readiness.hipaa_deployments,
                    "soc2_deployments": sigs.governance_readiness.soc2_deployments,
                    "audit_support": sigs.governance_readiness.audit_support,
                },
            },
            "agent_compatibility": {
                "score": scores.agent_compatibility,
                "weight": "15%",
                "band": _band_label(scores.agent_compatibility or 0),
                "key_signals": {
                    "mcp_support": sigs.agent_compatibility.mcp_support,
                    "is_async_native": sigs.agent_compatibility.is_async_native,
                    "multiagent_support": sigs.agent_compatibility.multiagent_support,
                    "state_management_rating": sigs.agent_compatibility.state_management_rating,
                },
            },
        },
        "confidence_rationale": {
            "base": 70.0,
            "is_proxy_confidence": scores.is_proxy_confidence,
            "incident_rate_source": sigs.production_stability.incident_rate_source,
            "signals_age_days": (date.today() - sigs.production_stability.signals_date).days,
        },
        "curation": {
            "status": fw.curation.status,
            "last_validated": fw.curation.last_validated.isoformat(),
            "curator_notes": fw.curation.notes[:200] if fw.curation.notes else None,
        },
        "migration_advisory": migration_advisory,
        "recommended_alternatives": recommended_alternatives,
        "superseded_by": superseded_by,
    })


# ── Tool 10: genome_compare ──────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Compare two Architecture Genome fingerprints for similarity. "
        "Returns a weighted similarity score (0-1), matching/mismatching dimensions, "
        "and a hard-filter flag if compliance profiles (D4) are incompatible. "
        "Use when comparing two architectural decisions or checking if a new system "
        "is compatible with an existing one."
    )
)
def genome_compare(genome_a: str, genome_b: str) -> dict:
    """
    Args:
        genome_a: First Architecture Genome string (e.g. 'MA-STAT-HOR-HIPAA-PY-MCP-REDIS').
        genome_b: Second Architecture Genome string to compare against.
    """
    from src.recommendation.genome import genome_similarity

    if not genome_a or not genome_b:
        return {"error": "Both genome_a and genome_b must be non-empty strings."}

    return genome_similarity(genome_a, genome_b)


# ── Tool 11: validate_code ──────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Validate LLM-generated code for deprecated API patterns — the fastest way to "
        "catch a hallucinated or stale API before it fails at runtime. "
        "Detects removed/renamed APIs, wrong import paths, and version-specific mismatches "
        "for 15 frameworks including Pinecone, LangChain, LangGraph, LlamaIndex, Qdrant, "
        "Weaviate, Chroma, OpenAI SDK, Anthropic SDK, AutoGen, CrewAI, PydanticAI, FastAPI, "
        "Supabase, and Ollama. Returns each violation with severity, the exact correction, "
        "and a docs link (advisory-severity notes are returned separately from hard violations). "
        "Pass the framework version to skip patterns not yet deprecated at that version. "
        "Call this right after generating code for any supported framework."
    )
)
def validate_code(
    code: str,
    framework_id: str,
    strict: bool = False,
    version: Optional[str] = None,
) -> dict:
    """
    Args:
        code:         The code snippet to validate (any length).
        framework_id: Framework to validate against (e.g., 'pinecone', 'langchain', 'langgraph',
                      'qdrant', 'openai_sdk', 'crewai', 'fastapi').
        strict:       If True, also checks patterns from all other frameworks present in the code.
        version:      Optional framework version the code targets (e.g. '2.1.0'). When set,
                      patterns for APIs not yet deprecated at that version are skipped.
    """
    from src.mcp.code_validator import validate_code_snippet, list_checked_frameworks

    # Check if we have patterns for this framework
    supported = [f["framework_id"] for f in list_checked_frameworks()]
    if framework_id not in supported and not strict:
        return {
            "warning": f"No deprecated API patterns available for '{framework_id}' yet.",
            "supported_frameworks": supported,
            "verdict": "unchecked",
            "summary": (
                f"TrueArch does not yet have a deprecated API pattern library for '{framework_id}'. "
                "Validation was skipped. Use strict=True to check against all known patterns."
            ),
        }

    result = validate_code_snippet(code, framework_id, strict=strict, version=version)
    return _clean_dict(result.model_dump())


# ── Tool 12: get_telemetry_insights ──────────────────────────────────────────

@mcp.tool(
    description=(
        "Get insights from TrueArch usage telemetry. Returns the most-queried frameworks, "
        "top comparison pairs, query volume trends, and compliance flag frequency. "
        "Use to understand what AI stack decisions developers are actually making in production "
        "and which frameworks have the highest real-world demand."
    )
)
def get_telemetry_insights(top_n: int = 10) -> dict:
    """
    Args:
        top_n: Number of top results to return per category (max 20).
    """
    try:
        return _clean_dict(get_insights(top_n=top_n))
    except Exception as e:
        return {"error": f"Failed to read telemetry: {str(e)}"}


# ── Entry Point ───────────────────────────────────────────────────────────────

_START_TIME = date.today().isoformat()
_VERSION = "2.0.0"


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
                "quick_context",
                "recommend_ai_stack",
                "compare_frameworks",
                "get_framework_score",
                "get_recommendation",
                "latest_stable_versions",
                "architecture_tradeoffs",
                "get_code_patterns",
                "generate_adr",
                "explain_score",
                "genome_compare",
                "validate_code",
                "get_telemetry_insights",
            ],
        })

    @http_app.get("/", tags=["system"])
    async def root():
        """Root route — returns service info so HF Spaces monitoring gets a 200."""
        return JSONResponse({
            "service": "truearch-mcp",
            "version": _VERSION,
            "status": "ok",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health",
                "version": "/version",
            },
            "frameworks_loaded": _FRAMEWORK_COUNT,
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
        host = os.environ.get("HOST", "127.0.0.1")  # HF Spaces / Docker sets HOST=0.0.0.0
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
