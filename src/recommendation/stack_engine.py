"""
TrueArch Stack Recommendation Engine.

Given a StackQuery (problem description + constraints), recommends the optimal
framework for each architectural layer — purely from scored intelligence data.

Design principles:
  - Deterministic: same query → same result (no LLM calls)
  - Explainable: every recommendation includes a reason string
  - Constraint-aware: compliance, scale, and priority modifiers adjust scores
  - Honest: confidence reflects data quality, not marketing
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta, date
from typing import Dict, List, Optional

from src.data.models import FrameworkSchema, ComputedScores
from src.scoring.engine import ScoringEngine
from src.recommendation.genome import GenomeGenerator
from src.recommendation.models import (
    ArchLayer, ComplianceFlag, PriorityAxis, ScaleTier,
    FrameworkChoice, StackQuery, StackRecommendation,
)

_genome_generator = GenomeGenerator()


# ── Category → ArchLayer mapping ─────────────────────────────────────────────
# Maps our YAML `category` field to canonical ArchLayer values.

_CATEGORY_TO_LAYER: Dict[str, ArchLayer] = {
    "orchestration":   ArchLayer.ORCHESTRATION,
    "vector-db":       ArchLayer.VECTOR_DB,
    "observability":   ArchLayer.OBSERVABILITY,
    "safety":          ArchLayer.SAFETY,
    "api-layer":       ArchLayer.API_LAYER,
    "api":             ArchLayer.API_LAYER,      # FastAPI uses category: "api"
    "db":              ArchLayer.DATABASE,
    "db+vector":       ArchLayer.DATABASE,
    "deployment":      ArchLayer.DEPLOYMENT,
    "protocol":        ArchLayer.PROTOCOL,
}

# Default layers recommended for every query
_DEFAULT_LAYERS = [
    ArchLayer.ORCHESTRATION,
    ArchLayer.VECTOR_DB,
    ArchLayer.OBSERVABILITY,
    ArchLayer.SAFETY,
    ArchLayer.API_LAYER,
    ArchLayer.DATABASE,
]


# ── Constraint-based score modifiers ─────────────────────────────────────────

def _compliance_modifier(
    fw: FrameworkSchema,
    compliance: List[ComplianceFlag],
    base_score: float,
) -> tuple[float, list[str]]:
    """
    Adjust score and build warnings based on compliance requirements.
    Returns (adjusted_score, list_of_warnings).
    """
    score = base_score
    warnings: List[str] = []
    gov = fw.signals.governance_readiness

    for flag in compliance:
        if flag == ComplianceFlag.HIPAA:
            if gov.hipaa_deployments == 0:
                score -= 20
                warnings.append(
                    f"{fw.name} has no documented HIPAA deployments — validate before use in healthcare."
                )
            elif gov.hipaa_deployments >= 5:
                score += 5  # verified hipaa track record
        elif flag == ComplianceFlag.SOC2:
            if gov.soc2_deployments == 0:
                score -= 10
                warnings.append(f"{fw.name} has no documented SOC2 deployments.")
            elif gov.soc2_deployments >= 5:
                score += 3
        elif flag == ComplianceFlag.GDPR:
            if gov.gdpr_deployments == 0:
                score -= 10
                warnings.append(f"{fw.name} has no documented GDPR deployments.")

    return min(100.0, max(0.0, score)), warnings


def _scale_modifier(fw: FrameworkSchema, scale: ScaleTier, base_score: float) -> float:
    """
    Boost/penalise based on scale requirements.
    High scale → production stability matters most.
    Prototype → momentum and developer experience matter most.
    """
    stability = fw.computed_scores.production_stability or 0
    momentum = fw.computed_scores.ecosystem_momentum or 0

    if scale == ScaleTier.ENTERPRISE:
        # Heavily weight stability; penalise low-stability frameworks
        if stability < 50:
            return base_score - 15
        elif stability >= 80:
            return base_score + 5
    elif scale == ScaleTier.PROTOTYPE:
        # Momentum matters — developers want active, well-supported tools
        if momentum >= 70:
            return base_score + 5
        elif momentum < 40:
            return base_score - 8
    return base_score


def _priority_modifier(fw: FrameworkSchema, priority: PriorityAxis, base_score: float) -> float:
    """Adjust score based on the developer's primary optimization axis."""
    scores = fw.computed_scores

    # Treat `performance` as an alias for `low_latency` (BUG-001 fix)
    if priority in (PriorityAxis.LOW_LATENCY, PriorityAxis.PERFORMANCE):
        # Low incident rate + high stability = low-latency friendly
        if (scores.production_stability or 0) >= 80:
            return base_score + 8
    elif priority == PriorityAxis.GOVERNANCE:
        # Governance readiness is the priority axis
        gov_score = scores.governance_readiness or 0
        boost = (gov_score - 60) / 10  # +N per 10 points above 60
        return base_score + boost
    elif priority == PriorityAxis.DEVELOPER_SPEED:
        # Momentum + strong ecosystem = fast developer ramp
        if (scores.ecosystem_momentum or 0) >= 70:
            return base_score + 6
    elif priority == PriorityAxis.COST_EFFICIENCY:
        # Prefer open-source with liberal licenses
        if fw.license and fw.license.upper() in {"MIT", "APACHE 2.0", "APACHE-2.0", "BSD"}:
            return base_score + 5

    return base_score


# ── Problem keyword heuristics ────────────────────────────────────────────────

_KEYWORD_BOOSTS: Dict[str, Dict[str, int]] = {
    # problem keyword → {framework_id: score_boost}
    "healthcare":      {"guardrails_ai": 10, "nemo_guardrails": 8, "postgresql_pgvector": 8},
    "hipaa":           {"guardrails_ai": 10, "postgresql_pgvector": 8},
    "real-time":       {"redis": 12, "fastapi": 8, "langgraph": 5},
    "low latency":     {"redis": 12, "fastapi": 8, "qdrant": 6},
    "customer support":{"langgraph": 8, "redis": 6, "guardrails_ai": 6},
    "multi-agent":     {"langgraph": 10, "google_adk": 8, "crewai": 6},
    "research":        {"llamaindex": 8, "langchain": 6, "chroma": 6},
    "production":      {"langgraph": 6, "fastapi": 6, "postgresql_pgvector": 6},
    "rag":             {"llamaindex": 10, "langchain": 6, "pinecone": 8, "qdrant": 6},
    "vector":          {"qdrant": 8, "pinecone": 6, "weaviate": 6, "chroma": 5},
    "search":          {"qdrant": 8, "weaviate": 8, "pinecone": 6},
    "cost":            {"chroma": 8, "supabase": 6, "fastapi": 4},
    "compliance":      {"nemo_guardrails": 8, "guardrails_ai": 8, "postgresql_pgvector": 5},
    "audit":           {"langsmith": 8, "opentelemetry": 8},
    "observability":   {"langsmith": 8, "helicone": 6, "opentelemetry": 8},
    "deploy":          {"modal": 8, "flyio": 6, "fastapi": 4},
    "serverless":      {"modal": 10, "flyio": 5},
}


def _keyword_boost(fw_id: str, problem: str) -> int:
    """Sum up all keyword-based score boosts for a framework given the problem."""
    problem_lower = problem.lower()
    total = 0
    for keyword, boosts in _KEYWORD_BOOSTS.items():
        if keyword in problem_lower and fw_id in boosts:
            total += boosts[fw_id]
    return total


# ── Reason generator ──────────────────────────────────────────────────────────

def _generate_reason(
    fw: FrameworkSchema,
    layer: ArchLayer,
    score: float,
    compliance: List[ComplianceFlag],
    priority: PriorityAxis,
    scale: ScaleTier,
) -> str:
    """Generate a concise, contextual reason string for a recommendation."""
    parts = []

    scores = fw.computed_scores
    gov = fw.signals.governance_readiness

    # Score band context
    band = scores.score_band or "Good"
    parts.append(f"{band} overall score ({score:.0f}/100)")

    # Layer-specific highlights
    if layer == ArchLayer.ORCHESTRATION:
        if (scores.agent_compatibility or 0) >= 80:
            parts.append("native multi-agent + MCP support")
        if (scores.production_stability or 0) >= 80:
            parts.append("battle-tested in production")
    elif layer == ArchLayer.VECTOR_DB:
        if (scores.production_stability or 0) >= 80:
            parts.append("production-grade reliability")
    elif layer == ArchLayer.OBSERVABILITY:
        if gov.audit_support == "native":
            parts.append("native audit trail support")
    elif layer == ArchLayer.SAFETY:
        parts.append(f"governance score {scores.governance_readiness:.0f}/100")
    elif layer == ArchLayer.API_LAYER:
        if (scores.ecosystem_momentum or 0) >= 75:
            parts.append("dominant ecosystem momentum")

    # Compliance
    active_flags = [f.value.upper() for f in compliance if f != ComplianceFlag.NONE]
    if active_flags and any([
        gov.hipaa_deployments > 0 and "HIPAA" in active_flags,
        gov.soc2_deployments > 0 and "SOC2" in active_flags,
        gov.gdpr_deployments > 0 and "GDPR" in active_flags,
    ]):
        parts.append(f"verified {'+'.join(active_flags)} deployments")

    # Priority
    if priority == PriorityAxis.LOW_LATENCY and (scores.production_stability or 0) >= 80:
        parts.append("low-latency profile")
    elif priority == PriorityAxis.GOVERNANCE and (scores.governance_readiness or 0) >= 75:
        parts.append("strong governance posture")

    return "; ".join(parts)


# ── Known-deprecated framework registry ──────────────────────────────────────
# Maps framework_id patterns → deprecation/caution message
_DEPRECATED_FRAMEWORKS: Dict[str, str] = {
    "autogen":     "AutoGen v0.2 is deprecated — migrate to AutoGen v0.4 (AgentChat API) or Microsoft's AG2 fork.",
    "langchain":   "LangChain has high breaking-change velocity — prefer LangGraph for stateful orchestration.",
    "chroma":      "Chroma is a prototype-only vector DB — use Qdrant or pgvector for production workloads.",
    "faiss":       "FAISS has no built-in production server or replication — use Qdrant for production.",
}

# Cloud regions that satisfy GDPR EU data residency requirements
_GDPR_SAFE_CLOUDS = {"aws": "eu-west-1, eu-central-1", "gcp": "europe-west1", "azure": "northeurope, westeurope"}


def _generate_global_warnings(query: StackQuery, frameworks: Dict[str, FrameworkSchema]) -> List[str]:
    """
    BUG-003 fix: Generate query-level warnings that are not framework-specific.
    Covers: cloud/compliance conflicts, deprecated framework mentions, known issues.
    """
    warnings: List[str] = []
    problem_lower = query.problem.lower()

    # 1. Cloud / GDPR conflict
    if ComplianceFlag.GDPR in query.compliance and query.cloud:
        cloud = query.cloud.lower()
        safe_regions = _GDPR_SAFE_CLOUDS.get(cloud)
        if safe_regions:
            warnings.append(
                f"⚠ GDPR + {cloud.upper()}: EU data residency required. "
                f"Use region(s): {safe_regions}. Avoid sending EU patient data to US-only APIs."
            )
        else:
            warnings.append(
                f"⚠ GDPR compliance: Verify that '{cloud}' region supports EU data residency."
            )

    # 2. HIPAA + hosted/US-SaaS cloud AI API mention
    if ComplianceFlag.HIPAA in query.compliance:
        for saas_term in ["openai api", "anthropic api", "pinecone", "hosted llm"]:
            if saas_term in problem_lower:
                warnings.append(
                    f"⚠ HIPAA: '{saas_term}' requires a signed BAA before PHI can flow through it. "
                    f"Verify BAA availability or use a self-hosted model."
                )

    # 3. Deprecated / cautioned framework mentions in the problem
    for fw_pattern, msg in _DEPRECATED_FRAMEWORKS.items():
        if fw_pattern in problem_lower:
            warnings.append(f"⚠ Framework Caution: {msg}")

    # 4. Hallucination guard: mention of unrecognized framework names
    known_ids = set(frameworks.keys())
    # Extract potential framework names (capitalized words adjacent to tech keywords)
    tech_keywords = ["framework", "library", "sdk", "db", "database", "agent", "memory", "platform"]
    words = re.findall(r'[A-Z][a-zA-Z0-9]+(?:[A-Z][a-zA-Z0-9]+)+', query.problem)
    for word in words:
        normalized = word.lower().replace(" ", "_")
        if normalized not in known_ids and any(kw in problem_lower for kw in tech_keywords):
            # Only warn if it looks like a product name (CamelCase, not a common English word)
            common_english = {"Python", "Ruby", "Java", "JavaScript", "TypeScript", "AWS", "GCP", "Azure",
                              "HIPAA", "GDPR", "SOC2", "Fortune", "GitHub", "Docker", "Kubernetes"}
            if word not in common_english:
                warnings.append(
                    f"⚠ Unrecognized framework '{word}': not found in TrueArch Genome taxonomy. "
                    f"Verify this framework exists before committing to it."
                )

    return list(dict.fromkeys(warnings))  # deduplicate preserving order


# ── Main Engine ───────────────────────────────────────────────────────────────

class StackRecommendationEngine:
    """
    Produces full multi-layer stack recommendations from scored framework intelligence.
    Pure deterministic scoring — no external API calls.
    """

    def __init__(self, frameworks: Dict[str, FrameworkSchema]):
        self.frameworks = frameworks

    def recommend(self, query: StackQuery) -> StackRecommendation:
        """Produce a full stack recommendation for the given query."""
        target_layers = query.layers or _DEFAULT_LAYERS
        layer_results: Dict[str, FrameworkChoice] = {}
        global_warnings: List[str] = []
        tradeoff_notes: List[str] = []

        # BUG-003 fix: query-level warnings (compliance/cloud conflicts, deprecated frameworks, hallucinations)
        global_warnings.extend(_generate_global_warnings(query, self.frameworks))

        for layer in target_layers:
            choice = self._recommend_layer(layer, query)
            if choice:
                layer_results[layer.value] = choice
                global_warnings.extend(choice.warnings)
                choice.warnings = []  # moved to global_warnings

        # Inter-layer tradeoff notes
        tradeoff_notes.extend(self._generate_tradeoff_notes(layer_results, query))

        # Overall confidence = average of chosen layer confidences
        if layer_results:
            avg_conf = sum(c.confidence for c in layer_results.values()) / len(layer_results)
        else:
            avg_conf = 0.0

        band = self._band(avg_conf)

        # Architecture Genome™ — fingerprint this architectural decision
        genome_short, genome_full = _genome_generator.generate(layer_results, query)

        # ADR review date: 12 months from today
        review_by = (date.today() + timedelta(days=365)).isoformat()

        return StackRecommendation(
            query_summary=self._summarise_query(query),
            layers=layer_results,
            global_warnings=list(dict.fromkeys(global_warnings)),  # deduplicate
            tradeoff_notes=tradeoff_notes,
            confidence=round(avg_conf, 1),
            score_band=band,
            genome_short=genome_short,
            genome_full=genome_full,
            review_by=review_by,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _recommend_layer(
        self, layer: ArchLayer, query: StackQuery
    ) -> Optional[FrameworkChoice]:
        """Score all candidates in a layer and return the best one."""
        candidates = [
            fw for fw in self.frameworks.values()
            if _CATEGORY_TO_LAYER.get(fw.category) == layer
            and fw.computed_scores is not None
        ]
        if not candidates:
            return None

        scored: List[tuple[float, FrameworkSchema]] = []
        for fw in candidates:
            base = fw.computed_scores.overall or 0.0

            # Apply modifiers
            base, warnings = _compliance_modifier(fw, query.compliance, base)
            base = _scale_modifier(fw, query.scale, base)
            base = _priority_modifier(fw, query.priority, base)
            base += _keyword_boost(fw.id, query.problem)
            base = min(100.0, max(0.0, base))

            scored.append((base, fw))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Re-compute warnings for top pick only
        top_score, top_fw = scored[0]
        _, top_warnings = _compliance_modifier(top_fw, query.compliance, top_score)

        alternatives = [fw.id for _, fw in scored[1:4]]  # up to 3 runners-up

        return FrameworkChoice(
            layer=layer,
            framework_id=top_fw.id,
            framework_name=top_fw.name,
            score=round(top_score, 1),
            confidence=top_fw.computed_scores.confidence or 0.0,
            reason=_generate_reason(
                top_fw, layer, top_score, query.compliance, query.priority, query.scale
            ),
            version=top_fw.latest_stable_version or "unknown",
            alternatives=alternatives,
            warnings=top_warnings,
        )

    def _generate_tradeoff_notes(
        self, choices: Dict[str, FrameworkChoice], query: StackQuery
    ) -> List[str]:
        """Generate cross-layer tradeoff observations."""
        notes: List[str] = []

        orch = choices.get(ArchLayer.ORCHESTRATION.value)
        vdb  = choices.get(ArchLayer.VECTOR_DB.value)
        obs  = choices.get(ArchLayer.OBSERVABILITY.value)

        if orch and orch.framework_id == "langgraph":
            notes.append(
                "LangGraph + LangSmith is a proven observability pair — LangSmith provides "
                "native LangGraph tracing with no extra instrumentation."
            )

        if orch and orch.framework_id in {"langgraph", "langchain"} and obs:
            if obs.framework_id == "opentelemetry":
                notes.append(
                    "OpenTelemetry is fully vendor-neutral but requires manual "
                    "LangGraph instrumentation. LangSmith offers zero-config LangGraph tracing."
                )

        if vdb and vdb.framework_id == "chroma" and query.scale in {ScaleTier.SCALE, ScaleTier.ENTERPRISE}:
            notes.append(
                "Chroma is ideal for prototyping and moderate scale but consider Qdrant or "
                "Pinecone for production workloads above 100K users."
            )

        if ComplianceFlag.HIPAA in query.compliance:
            notes.append(
                "For HIPAA compliance: ensure all data-at-rest is encrypted, "
                "audit logs are enabled in your observability layer, and "
                "PHI never flows through vector embeddings without de-identification."
            )

        return notes

    @staticmethod
    def _summarise_query(query: StackQuery) -> str:
        flags = [f.value for f in query.compliance if f != ComplianceFlag.NONE]
        compliance_str = f" with {'+'.join(flags).upper()} compliance" if flags else ""
        return (
            f"{query.problem.strip()}{compliance_str} "
            f"[{query.scale.value} scale, priority: {query.priority.value}, "
            f"lang: {query.language}]"
        )

    @staticmethod
    def _band(score: float) -> str:
        if score >= 85: return "Excellent"
        if score >= 70: return "Strong"
        if score >= 55: return "Good"
        if score >= 40: return "Fair"
        if score >= 25: return "Weak"
        return "Poor"
