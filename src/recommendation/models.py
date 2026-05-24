"""
Pydantic models for the TrueArch Recommendation and Tradeoff subsystems.

These models define the input/output contracts for:
  - StackQuery / StackRecommendation  (Stack Recommendation Engine)
  - ComparisonRequest / FrameworkComparison  (Architecture Tradeoff Reasoner)
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class ComplianceFlag(str, Enum):
    HIPAA    = "hipaa"
    SOC2     = "soc2"
    GDPR     = "gdpr"
    NONE     = "none"


class ScaleTier(str, Enum):
    PROTOTYPE   = "prototype"   # < 1K users, speed to build matters most
    GROWTH      = "growth"      # 1K–100K users, reliability starts mattering
    SCALE       = "scale"       # 100K–10M users, performance-critical
    ENTERPRISE  = "enterprise"  # 10M+ users, cost + reliability dominant


class PriorityAxis(str, Enum):
    LOW_LATENCY      = "low_latency"
    PERFORMANCE      = "performance"     # alias for low_latency — accepted from user input
    COST_EFFICIENCY  = "cost_efficiency"
    RELIABILITY      = "reliability"
    DEVELOPER_SPEED  = "developer_speed"
    GOVERNANCE       = "governance"


class ArchLayer(str, Enum):
    """The standard architectural layers TrueArch recommends for."""
    ORCHESTRATION   = "orchestration"
    VECTOR_DB       = "vector_db"
    OBSERVABILITY   = "observability"
    SAFETY          = "safety"
    API_LAYER       = "api_layer"
    DATABASE        = "database"
    DEPLOYMENT      = "deployment"
    PROTOCOL        = "protocol"


# ── Stack Recommendation ───────────────────────────────────────────────────────

class StackQuery(BaseModel):
    """Input contract for the Stack Recommendation Engine."""
    problem: str = Field(
        ...,
        description="Short description of the system to build (e.g. 'multi-agent customer support platform')",
        min_length=10,
        max_length=500,
    )
    compliance: List[ComplianceFlag] = Field(
        default=[ComplianceFlag.NONE],
        description="Required compliance regimes",
    )
    language: str = Field(
        default="python",
        description="Primary programming language",
    )
    scale: ScaleTier = Field(
        default=ScaleTier.GROWTH,
        description="Expected scale of the system",
    )
    priority: PriorityAxis = Field(
        default=PriorityAxis.RELIABILITY,
        description="The primary optimization axis",
    )
    cloud: Optional[str] = Field(
        default=None,
        description="Cloud provider if relevant (aws, gcp, azure)",
    )
    layers: Optional[List[ArchLayer]] = Field(
        default=None,
        description="Specific layers to recommend for. Defaults to all layers.",
    )


class FrameworkChoice(BaseModel):
    """A single layer recommendation within a stack."""
    layer: ArchLayer
    framework_id: str
    framework_name: str
    score: float
    confidence: float
    reason: str
    version: str
    alternatives: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class StackRecommendation(BaseModel):
    """Full stack recommendation output."""
    query_summary: str
    layers: Dict[str, FrameworkChoice]
    global_warnings: List[str] = Field(default_factory=list)
    tradeoff_notes: List[str] = Field(default_factory=list)
    confidence: float = Field(description="Overall recommendation confidence 0–100")
    score_band: str
    context_brief: Optional[str] = Field(
        default=None,
        description="A compressed 150-200 token brief intended for agent system prompts.",
    )
    # Architecture Genome™ — the fingerprint of this architectural decision
    genome_short: Optional[str] = Field(
        default=None,
        description="Short 7-dimension Genome (e.g. MA-STAT-HOR-HIPAA-PY-MCP-REDIS)",
    )
    genome_full: Optional[str] = Field(
        default=None,
        description="Full 10-dimension Genome with orchestrator, observability, deployment",
    )
    # ADR metadata
    review_by: Optional[str] = Field(
        default=None,
        description="ISO date — re-evaluate this recommendation if Mortality Score drops below 60",
    )
    generated_at: str


# ── Tradeoff Comparator ────────────────────────────────────────────────────────

class DimensionComparison(BaseModel):
    """Score comparison for a single scoring dimension."""
    dimension: str
    framework_a_score: float
    framework_b_score: float
    winner: str   # framework_id of the winner, or "tie"
    delta: float  # absolute difference
    insight: str  # human-readable explanation


class FrameworkComparison(BaseModel):
    """Full tradeoff comparison between two frameworks."""
    framework_a_id: str
    framework_a_name: str
    framework_b_id: str
    framework_b_name: str
    use_case: Optional[str]

    dimensions: List[DimensionComparison]
    overall_winner: str        # framework_id or "tie"
    overall_winner_name: str
    overall_score_a: float
    overall_score_b: float
    confidence_a: float
    confidence_b: float

    context_brief: Optional[str] = Field(
        default=None,
        description="A compressed 150-200 token brief intended for agent system prompts.",
    )
    recommendation: str        # 1–2 sentence narrative
    when_to_pick_a: List[str]  # concrete scenarios favouring A
    when_to_pick_b: List[str]  # concrete scenarios favouring B
    migration_note: Optional[str] = None
    generated_at: str
