from datetime import date
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class GenomeDimension(BaseModel):
    key: str
    value: str

class ProductionStabilitySignals(BaseModel):
    breaking_changes_per_90d: int
    issue_resolution_ratio: float
    open_security_advisories: int
    incident_rate: float
    incident_rate_source: Literal["telemetry", "curated", "default"]
    signals_date: date

class EcosystemMomentumSignals(BaseModel):
    github_stars: int
    star_growth_30d_pct: float
    commits_last_90d: int
    commits_prev_90d: int
    merged_prs_per_30d: int
    avg_days_to_merge: float
    job_postings_30d: int
    so_questions_30d: int
    so_questions_prev_30d: int
    signals_date: date

class MigrationRiskSignals(BaseModel):
    viable_alternatives: int
    public_api_methods: int
    migration_guide_count: int
    community_migrations: int
    signals_date: date

class GovernanceReadinessSignals(BaseModel):
    unpatched_cves: int
    avg_days_to_patch: int
    doc_completeness_rating: int
    hipaa_deployments: int
    soc2_deployments: int
    gdpr_deployments: int
    other_compliance_deployments: int
    audit_support: Literal["native", "plugin", "none"]
    signals_date: date

class AgentCompatibilitySignals(BaseModel):
    mcp_support: Literal["native", "community_plugin", "wrapper_available", "none"]
    is_async_native: bool
    is_thread_safe: bool
    has_concurrency_benchmarks: bool
    state_management_rating: int
    multiagent_support: Literal["native", "possible", "limited", "none"]
    signals_date: date

class Signals(BaseModel):
    production_stability: ProductionStabilitySignals
    ecosystem_momentum: EcosystemMomentumSignals
    migration_risk: MigrationRiskSignals
    governance_readiness: GovernanceReadinessSignals
    agent_compatibility: AgentCompatibilitySignals

class ComputedScores(BaseModel):
    production_stability: Optional[float] = None
    ecosystem_momentum: Optional[float] = None
    migration_risk: Optional[float] = None
    governance_readiness: Optional[float] = None
    agent_compatibility: Optional[float] = None
    overall: Optional[float] = None
    confidence: Optional[float] = None
    is_proxy_confidence: Optional[bool] = None
    score_band: Optional[Literal["Excellent", "Strong", "Good", "Fair", "Weak", "Poor"]] = None
    last_computed: Optional[date] = None
    valid_until: Optional[date] = None
    # Staleness
    staleness_status: Optional[Literal["fresh", "acceptable", "stale", "expired"]] = None
    staleness_warning: Optional[str] = None

class KnownIssue(BaseModel):
    id: str
    severity: Literal["critical", "high", "medium", "low"]
    description: str
    affected_versions: str
    resolved: bool
    resolved_in: Optional[str] = None
    workaround: Optional[str] = None
    source: str

class Compatibility(BaseModel):
    framework: str
    strength: float
    notes: str

class Conflict(BaseModel):
    framework: str
    severity: Literal["high", "medium", "low"]
    notes: str

class Supersedes(BaseModel):
    framework: str
    confidence: float
    notes: str

class MigratesTo(BaseModel):
    framework: str
    effort: float
    notes: str

class CurationMetadata(BaseModel):
    status: Literal["curated", "pending", "deprecated"]
    last_validated: date
    validated_by: str
    next_validation_due: date
    confidence_override: Optional[float] = None
    sources: List[str]
    notes: str

class FrameworkSchema(BaseModel):
    schema_version: str
    id: str
    name: str
    category: str
    subcategory: Optional[str] = None
    url: str
    docs_url: str
    license: str
    primary_language: str
    latest_stable_version: str
    latest_stable_released: str # string because sometimes it's '2026-Q1' or 'managed'

    genome_dimension: GenomeDimension
    signals: Signals
    computed_scores: ComputedScores
    
    known_issues: List[KnownIssue] = Field(default_factory=list)
    compatible_with: List[Compatibility] = Field(default_factory=list)
    conflicts_with: List[Conflict] = Field(default_factory=list)
    supersedes: List[Supersedes] = Field(default_factory=list)
    migrates_to: List[MigratesTo] = Field(default_factory=list)
    
    curation: CurationMetadata
