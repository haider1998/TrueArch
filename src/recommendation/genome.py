"""
TrueArch Architecture Genome™ Generator

Assigns a structured Genome fingerprint to every stack recommendation.
The Genome encodes the architectural DNA across 10 dimensions from GENOME_TAXONOMY.md.

Short Genome (7 dimensions — shareable, human-readable):
    MA-STAT-HOR-HIPAA-PY-MCP-REDIS

Full Genome (10 dimensions — for ArchGraph indexing):
    MA-STAT-HOR-HIPAA-PY-MCP-REDIS+LGR+OTEL+CONT

Design:
  - Deterministic: same inputs always produce same Genome
  - Legible: each segment is a 2–8 character uppercase code
  - Searchable: supports wildcard matching via genome_matches()
  - Standard: open taxonomy defined in GENOME_TAXONOMY.md
"""
from __future__ import annotations

import re
from typing import Dict, Optional, List, Tuple

from src.recommendation.models import StackQuery, FrameworkChoice, ComplianceFlag, ScaleTier, ArchLayer


# ── Dimension Codes ───────────────────────────────────────────────────────────

# D1: Architectural Pattern
_PATTERN_KEYWORDS: Dict[str, str] = {
    "multi.agent":          "MA",
    "multi agent":          "MA",
    "multiagent":           "MA",
    "rag":                  "RAG",
    "retrieval":            "RAG",
    "retrieval augmented":  "RAG",
    "pipeline":             "PIPE",
    "workflow":             "WF",
    "batch":                "WF",
    "single.agent":         "SA",
    "chatbot":              "SA",
    "assistant":            "SA",
    "hybrid":               "HYB",
}
_PATTERN_DEFAULT = "SA"

# D2: Memory Strategy (inferred from layer choices)
_STORE_TO_MEMORY: Dict[str, str] = {
    "redis":        "STAT",   # Stateful session memory
    "postgresql":   "STAT",
    "postgresql_pgvector": "STAT",
    "supabase":     "STAT",
    "mongodb":      "STAT",
    "qdrant":       "VECT",   # Vector-stateless
    "pinecone":     "VECT",
    "chroma":       "VECT",
    "weaviate":     "VECT",
}
_MEMORY_DEFAULT = "SESS"

# D3: Scaling Strategy (from ScaleTier)
_SCALE_TO_D3: Dict[str, str] = {
    "prototype":  "VER",    # Vertical scaling sufficient
    "growth":     "HOR",    # Horizontal is implied
    "scale":      "HOR",
    "enterprise": "HOR",
}

# D4: Compliance
_COMPLIANCE_CODES: Dict[str, str] = {
    "hipaa":  "HIPAA",
    "soc2":   "SOC2",
    "gdpr":   "GDPR",
    "none":   "OPEN",
}

# D5: Language — max 4 chars uppercase
_LANG_ALIASES: Dict[str, str] = {
    "python": "PY",
    "typescript": "TS",
    "javascript": "JS",
    "go": "GO",
    "rust": "RUST",
    "java": "JAVA",
}

# D6: Protocol (inferred from frameworks in stack)
_FRAMEWORK_TO_PROTOCOL: Dict[str, str] = {
    "mcp_sdk_python": "MCP",
    "a2a":            "A2A",
    "fastapi":        "REST",
    "langgraph":      "MCP",   # LangGraph natively adopts MCP in recent releases
    "google_adk":     "MCP",
}
_PROTOCOL_DEFAULT = "REST"

# D7: Store (primary memory/vector store)
_STORE_PRIORITY = [
    "redis", "postgresql_pgvector", "postgresql", "qdrant",
    "pinecone", "weaviate", "chroma", "mongodb", "supabase",
]
_STORE_CODES: Dict[str, str] = {
    "redis":                "REDIS",
    "postgresql_pgvector":  "PGVEC",
    "postgresql":           "PG",
    "qdrant":               "QDRANT",
    "pinecone":             "PINE",
    "weaviate":             "WEAV",
    "chroma":               "CHROMA",
    "mongodb":              "MONGO",
    "supabase":             "SUPA",
}
_STORE_DEFAULT = "MEM"

# D8: Orchestrator
_ORCHESTRATOR_CODES: Dict[str, str] = {
    "langgraph":    "LGR",
    "crewai":       "CREW",
    "autogen":      "AUTOG",
    "google_adk":   "ADK",
    "pydantic_ai":  "PDT",
    "llamaindex":   "LLMI",
    "langchain":    "LC",
    "dspy":         "DSPY",
    "smolagents":   "SMOL",
}
_ORCHESTRATOR_DEFAULT = "NONE"

# D9: Observability
_OBSERVABILITY_CODES: Dict[str, str] = {
    "opentelemetry": "OTEL",
    "langsmith":     "LSMITH",
    "helicone":      "HELIC",
    "arize":         "ARIZE",
    "traceloop":     "TRACE",
}
_OBSERVABILITY_DEFAULT = "NONE"

# D10: Deployment
_DEPLOYMENT_CODES: Dict[str, str] = {
    "flyio":  "FLY",
    "modal":  "MODAL",
}
_DEPLOYMENT_MAP_CLOUD: Dict[str, str] = {
    "aws":   "AWS",
    "gcp":   "GCP",
    "azure": "AZ",
}
_DEPLOYMENT_DEFAULT = "CONT"   # Container-based (default assumption)


class GenomeGenerator:
    """
    Assigns a structured Architecture Genome fingerprint to a stack recommendation.

    Usage:
        generator = GenomeGenerator()
        short, full = generator.generate(layers, query)
        # short → "MA-STAT-HOR-HIPAA-PY-MCP-REDIS"
        # full  → "MA-STAT-HOR-HIPAA-PY-MCP-REDIS+LGR+OTEL+CONT"
    """

    def generate(
        self,
        layers: Dict[str, FrameworkChoice],
        query: StackQuery,
    ) -> Tuple[str, str]:
        """
        Generate short (7-dim) and full (10-dim) Genome strings.

        Returns:
            (short_genome, full_genome) — both are uppercase hyphen-separated strings.
        """
        chosen_ids = {choice.framework_id for choice in layers.values()}

        d1 = self._d1_pattern(query.problem)
        d2 = self._d2_memory(chosen_ids)
        d3 = self._d3_scaling(query.scale)
        d4 = self._d4_compliance(query.compliance)
        d5 = self._d5_language(query.language)
        d6 = self._d6_protocol(chosen_ids)
        d7 = self._d7_store(layers)

        # Full Genome dims
        d8 = self._d8_orchestrator(layers)
        d9 = self._d9_observability(layers)
        d10 = self._d10_deployment(layers, query)

        short = f"{d1}-{d2}-{d3}-{d4}-{d5}-{d6}-{d7}"
        full  = f"{short}+{d8}+{d9}+{d10}"

        return short, full

    # ── D1: Pattern ──────────────────────────────────────────────────────────

    def _d1_pattern(self, problem: str) -> str:
        text = problem.lower()
        for kw, code in _PATTERN_KEYWORDS.items():
            if re.search(kw, text):
                return code
        return _PATTERN_DEFAULT

    # ── D2: Memory Strategy ──────────────────────────────────────────────────

    def _d2_memory(self, chosen_ids: set) -> str:
        # If vector store detected → memory is vector-based
        vector_stores = {"qdrant", "pinecone", "weaviate", "chroma"}
        stateful_stores = {"redis", "postgresql_pgvector", "postgresql", "mongodb", "supabase"}

        has_vector = bool(chosen_ids & vector_stores)
        has_stateful = bool(chosen_ids & stateful_stores)

        if has_stateful and has_vector:
            return "HYB"    # Hybrid: stateful + vector
        if has_stateful:
            return "STAT"
        if has_vector:
            return "VECT"
        return _MEMORY_DEFAULT

    # ── D3: Scaling ──────────────────────────────────────────────────────────

    def _d3_scaling(self, scale: ScaleTier) -> str:
        return _SCALE_TO_D3.get(scale.value, "HOR")

    # ── D4: Compliance ───────────────────────────────────────────────────────

    def _d4_compliance(self, compliance: List[ComplianceFlag]) -> str:
        codes = []
        for flag in compliance:
            code = _COMPLIANCE_CODES.get(flag.value)
            if code and code != "OPEN":
                codes.append(code)
        if not codes:
            return "OPEN"
        if len(codes) == 1:
            return codes[0]
        return "+".join(sorted(codes))   # e.g. "GDPR+HIPAA"

    # ── D5: Language ─────────────────────────────────────────────────────────

    def _d5_language(self, language: str) -> str:
        lang = language.lower().strip()
        return _LANG_ALIASES.get(lang, lang.upper()[:4])

    # ── D6: Protocol ─────────────────────────────────────────────────────────

    def _d6_protocol(self, chosen_ids: set) -> str:
        # Priority: MCP > A2A > REST > GRPC
        for fid, code in _FRAMEWORK_TO_PROTOCOL.items():
            if fid in chosen_ids:
                return code
        return _PROTOCOL_DEFAULT

    # ── D7: Store ────────────────────────────────────────────────────────────

    def _d7_store(self, layers: Dict[str, FrameworkChoice]) -> str:
        # Look in database and vector_db layers first
        priority_layers = ["database", "vector_db"]
        for layer in priority_layers:
            choice = layers.get(layer)
            if choice and choice.framework_id in _STORE_CODES:
                return _STORE_CODES[choice.framework_id]

        # Fallback: scan all layers
        for priority_fid in _STORE_PRIORITY:
            for choice in layers.values():
                if choice.framework_id == priority_fid:
                    return _STORE_CODES.get(priority_fid, _STORE_DEFAULT)

        return _STORE_DEFAULT

    # ── D8: Orchestrator ─────────────────────────────────────────────────────

    def _d8_orchestrator(self, layers: Dict[str, FrameworkChoice]) -> str:
        orch = layers.get("orchestration")
        if orch and orch.framework_id in _ORCHESTRATOR_CODES:
            return _ORCHESTRATOR_CODES[orch.framework_id]
        return _ORCHESTRATOR_DEFAULT

    # ── D9: Observability ────────────────────────────────────────────────────

    def _d9_observability(self, layers: Dict[str, FrameworkChoice]) -> str:
        obs = layers.get("observability")
        if obs and obs.framework_id in _OBSERVABILITY_CODES:
            return _OBSERVABILITY_CODES[obs.framework_id]
        return _OBSERVABILITY_DEFAULT

    # ── D10: Deployment ──────────────────────────────────────────────────────

    def _d10_deployment(
        self,
        layers: Dict[str, FrameworkChoice],
        query: StackQuery,
    ) -> str:
        dep = layers.get("deployment")
        if dep and dep.framework_id in _DEPLOYMENT_CODES:
            return _DEPLOYMENT_CODES[dep.framework_id]

        if query.cloud:
            return _DEPLOYMENT_MAP_CLOUD.get(query.cloud.lower(), _DEPLOYMENT_DEFAULT)

        return _DEPLOYMENT_DEFAULT


# ── Genome Comparison ─────────────────────────────────────────────────────────

def genome_similarity(genome_a: str, genome_b: str) -> dict:
    """
    Compute similarity between two short Genome strings (7 dimensions).

    The short Genome format: D1-D2-D3-D4-D5-D6-D7
    Wildcards (*) in either genome match any value in that dimension.

    Returns:
        {
          "similarity_score": float (0.0–1.0),
          "matching_dimensions": [...],
          "mismatching_dimensions": [...],
          "hard_filter_mismatch": bool,
          "genome_a": str,
          "genome_b": str,
        }
    """
    _DIMENSION_NAMES = [
        "D1_pattern", "D2_memory", "D3_scaling", "D4_compliance",
        "D5_language", "D6_protocol", "D7_store",
    ]
    # Weights from GENOME_TAXONOMY.md comparison algorithm
    _WEIGHTS = [0.20, 0.15, 0.10, 0.25, 0.10, 0.15, 0.05]

    parts_a = genome_a.split("-")
    parts_b = genome_b.split("-")

    # Pad to 7 if shorter
    while len(parts_a) < 7:
        parts_a.append("*")
    while len(parts_b) < 7:
        parts_b.append("*")

    matching = []
    mismatching = []
    weighted_score = 0.0
    hard_filter_mismatch = False

    for idx, (a, b, name, weight) in enumerate(zip(parts_a, parts_b, _DIMENSION_NAMES, _WEIGHTS)):
        if a == "*" or b == "*" or a == b:
            matching.append(name)
            weighted_score += weight
        else:
            mismatching.append(name)
            # D4 (compliance) mismatch is a hard filter
            if idx == 3:
                hard_filter_mismatch = True

    return {
        "similarity_score": round(weighted_score, 4),
        "matching_dimensions": matching,
        "mismatching_dimensions": mismatching,
        "hard_filter_mismatch": hard_filter_mismatch,
        "genome_a": genome_a,
        "genome_b": genome_b,
    }


def genome_matches(genome: str, pattern: str) -> bool:
    """
    Check if a Genome string matches a wildcard pattern.
    '*' in the pattern matches any value in that dimension.

    Example:
        genome_matches("MA-STAT-HOR-HIPAA-PY-MCP-REDIS", "MA-*-*-HIPAA-*-*-*")
        → True
    """
    g_parts = genome.split("-")
    p_parts = pattern.split("-")

    for g, p in zip(g_parts, p_parts):
        if p != "*" and g != p:
            return False
    return True
