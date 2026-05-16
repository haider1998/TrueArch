"""
TrueArch Architecture Tradeoff Reasoner.

Given two framework IDs + optional use-case context, produces a structured
dimension-by-dimension comparison with an explainable recommendation.

Design principles:
  - Every winner claim is backed by a numerical delta from the scoring engine
  - Insights are generated from signal data, not hard-coded strings
  - Honest about ties (delta < 5 is a tie, not a winner)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, List

from src.data.models import FrameworkSchema, ComputedScores
from src.recommendation.models import DimensionComparison, FrameworkComparison


# Minimum delta to declare a winner (below this = tie)
_TIE_THRESHOLD = 5.0

# Dimension display names and weights from SCORING_FORMULA.md
_DIMENSIONS = [
    ("production_stability",  "Production Stability",  0.30),
    ("ecosystem_momentum",    "Ecosystem Momentum",    0.25),
    ("migration_risk",        "Migration Risk",        0.15),
    ("governance_readiness",  "Governance Readiness",  0.15),
    ("agent_compatibility",   "Agent Compatibility",   0.15),
]

# Migration risk note: higher = EASIER to migrate. Explain this in output.
_MIGRATION_RISK_NOTE = (
    "Note: Migration Risk is reverse-scored — a higher score means it is "
    "EASIER to migrate away from this framework (more alternatives, guides, community migrations)."
)


def _get_score(scores: ComputedScores, attr: str) -> float:
    return getattr(scores, attr, None) or 0.0


def _insight_for_dimension(
    dimension: str,
    fw_a: FrameworkSchema,
    fw_b: FrameworkSchema,
    score_a: float,
    score_b: float,
    winner_id: str,
) -> str:
    """Generate a data-driven insight string for a single dimension comparison."""
    delta = abs(score_a - score_b)
    winner = fw_a if winner_id == fw_a.id else fw_b
    loser  = fw_b if winner_id == fw_a.id else fw_a

    if winner_id == "tie":
        return f"Near-equal scores (delta {delta:.1f}). Both are comparable on this axis."

    if dimension == "production_stability":
        w_breaks = winner.signals.production_stability.breaking_changes_per_90d
        l_breaks = loser.signals.production_stability.breaking_changes_per_90d
        return (
            f"{winner.name} leads by {delta:.1f} points. "
            f"Breaking changes per 90d: {winner.name}={w_breaks}, {loser.name}={l_breaks}."
        )
    elif dimension == "ecosystem_momentum":
        w_stars  = winner.signals.ecosystem_momentum.github_stars
        l_stars  = loser.signals.ecosystem_momentum.github_stars
        w_growth = winner.signals.ecosystem_momentum.star_growth_30d_pct
        l_growth = loser.signals.ecosystem_momentum.star_growth_30d_pct
        return (
            f"{winner.name} leads by {delta:.1f} points. "
            f"Stars: {winner.name}={w_stars:,} (+{w_growth:.1f}%/mo), "
            f"{loser.name}={l_stars:,} (+{l_growth:.1f}%/mo)."
        )
    elif dimension == "migration_risk":
        w_alts = winner.signals.migration_risk.viable_alternatives
        l_alts = loser.signals.migration_risk.viable_alternatives
        return (
            f"{winner.name} scores higher (easier to migrate away from). "
            f"Viable alternatives: {winner.name}={w_alts}, {loser.name}={l_alts}. "
            + _MIGRATION_RISK_NOTE
        )
    elif dimension == "governance_readiness":
        w_cves = winner.signals.governance_readiness.unpatched_cves
        l_cves = loser.signals.governance_readiness.unpatched_cves
        w_audit = winner.signals.governance_readiness.audit_support
        return (
            f"{winner.name} leads by {delta:.1f} points. "
            f"Unpatched CVEs: {winner.name}={w_cves}, {loser.name}={l_cves}. "
            f"{winner.name} audit support: {w_audit}."
        )
    elif dimension == "agent_compatibility":
        w_mcp = winner.signals.agent_compatibility.mcp_support
        l_mcp = loser.signals.agent_compatibility.mcp_support
        w_multi = winner.signals.agent_compatibility.multiagent_support
        return (
            f"{winner.name} leads by {delta:.1f} points. "
            f"MCP support: {winner.name}={w_mcp}, {loser.name}={l_mcp}. "
            f"{winner.name} multiagent: {w_multi}."
        )

    return f"{winner.name} leads by {delta:.1f} points on {dimension}."


def _when_to_pick(
    fw: FrameworkSchema,
    dimension_wins: List[str],
    is_overall_winner: bool,
) -> List[str]:
    """Generate 3–5 concrete 'When to pick X' bullet points."""
    reasons = []
    sigs = fw.signals

    # Governance / compliance
    gov = sigs.governance_readiness
    if gov.hipaa_deployments >= 3:
        reasons.append(f"Your project requires HIPAA compliance")
    if gov.soc2_deployments >= 3:
        reasons.append(f"You need SOC 2 audit trails")
    if gov.gdpr_deployments >= 3:
        reasons.append(f"GDPR data residency is a requirement")

    # Agent / MCP
    agt = sigs.agent_compatibility
    if agt.mcp_support == "native":
        reasons.append("You are building MCP-native agentic workflows")
    if agt.multiagent_support == "native":
        reasons.append("Your system requires true multi-agent orchestration")
    if agt.is_async_native:
        reasons.append("High concurrency or streaming responses are required")

    # Stability
    stab = sigs.production_stability
    if stab.breaking_changes_per_90d == 0:
        reasons.append("API stability is critical — zero breaking changes in 6 months")

    # Migration
    mig = sigs.migration_risk
    if mig.viable_alternatives >= 4:
        reasons.append("You want to avoid framework lock-in (many alternatives available)")
    elif mig.viable_alternatives <= 1:
        reasons.append("You are comfortable with framework commitment in exchange for deep ecosystem integration")

    # Ecosystem
    eco = sigs.ecosystem_momentum
    if eco.github_stars >= 20_000:
        reasons.append("Hiring is a concern — large community means easier team onboarding")
    if eco.job_postings_30d >= 2000:
        reasons.append("Growing job market for this framework makes hiring easier")

    # Fallback
    if not reasons:
        if is_overall_winner:
            reasons.append(f"{fw.name} is the recommended choice for general-purpose use cases")
        else:
            reasons.append(f"{fw.name} is appropriate when the above considerations do not apply")

    return reasons[:5]  # max 5 bullets


def _narrative_recommendation(
    fw_a: FrameworkSchema,
    fw_b: FrameworkSchema,
    winner_id: str,
    score_a: float,
    score_b: float,
    use_case: Optional[str],
) -> str:
    delta = abs(score_a - score_b)
    ctx = f" for {use_case}" if use_case else ""

    if winner_id == "tie":
        return (
            f"{fw_a.name} and {fw_b.name} are closely matched{ctx} "
            f"(scores {score_a:.0f} vs {score_b:.0f}). "
            "Choose based on your compliance requirements and team familiarity."
        )

    winner = fw_a if winner_id == fw_a.id else fw_b
    loser  = fw_b if winner_id == fw_a.id else fw_a
    margin = "decisively" if delta >= 15 else "narrowly" if delta < 8 else "clearly"

    return (
        f"TrueArch recommends **{winner.name}** {margin} over {loser.name}{ctx} "
        f"(overall scores: {score_a:.0f} vs {score_b:.0f}). "
        f"{winner.name} scores {delta:.0f} points higher overall, "
        f"driven primarily by its stronger {_top_dimension(winner_id, fw_a, fw_b)} profile."
    )


def _top_dimension(
    winner_id: str,
    fw_a: FrameworkSchema,
    fw_b: FrameworkSchema,
) -> str:
    """Return the dimension name where the winner has the largest advantage."""
    winner = fw_a if winner_id == fw_a.id else fw_b
    loser  = fw_b if winner_id == fw_a.id else fw_a

    best_dim, best_delta = "production_stability", 0.0
    for attr, name, _ in _DIMENSIONS:
        delta = _get_score(winner.computed_scores, attr) - _get_score(loser.computed_scores, attr)
        if delta > best_delta:
            best_delta = delta
            best_dim = name.lower()
    return best_dim


# ── Main Comparator ───────────────────────────────────────────────────────────

class TradeoffComparator:
    """
    Produces structured dimension-by-dimension comparisons between two frameworks.
    """

    def __init__(self, frameworks: Dict[str, FrameworkSchema]):
        self.frameworks = frameworks

    def compare(
        self,
        framework_a_id: str,
        framework_b_id: str,
        use_case: Optional[str] = None,
    ) -> FrameworkComparison:
        fw_a = self.frameworks[framework_a_id]
        fw_b = self.frameworks[framework_b_id]
        scores_a = fw_a.computed_scores
        scores_b = fw_b.computed_scores

        # Build dimension comparisons
        dimensions: List[DimensionComparison] = []
        for attr, name, weight in _DIMENSIONS:
            sa = _get_score(scores_a, attr)
            sb = _get_score(scores_b, attr)
            delta = sa - sb
            abs_delta = abs(delta)

            if abs_delta < _TIE_THRESHOLD:
                winner_id = "tie"
                winner_label = "tie"
            elif delta > 0:
                winner_id = fw_a.id
                winner_label = fw_a.id
            else:
                winner_id = fw_b.id
                winner_label = fw_b.id

            dimensions.append(DimensionComparison(
                dimension=name,
                framework_a_score=round(sa, 1),
                framework_b_score=round(sb, 1),
                winner=winner_label,
                delta=round(abs_delta, 1),
                insight=_insight_for_dimension(attr, fw_a, fw_b, sa, sb, winner_id),
            ))

        # Overall winner
        oa = scores_a.overall or 0.0
        ob = scores_b.overall or 0.0
        delta_overall = oa - ob

        if abs(delta_overall) < _TIE_THRESHOLD:
            overall_winner_id = "tie"
            overall_winner_name = "tie"
        elif delta_overall > 0:
            overall_winner_id = fw_a.id
            overall_winner_name = fw_a.name
        else:
            overall_winner_id = fw_b.id
            overall_winner_name = fw_b.name

        # Migration note if frameworks are in the same category
        migration_note: Optional[str] = None
        if fw_a.category == fw_b.category:
            guides_a = fw_a.signals.migration_risk.migration_guide_count
            guides_b = fw_b.signals.migration_risk.migration_guide_count
            migration_note = (
                f"Both frameworks are in the same category ({fw_a.category}), "
                f"so migration between them is feasible. "
                f"Migration guides: {fw_a.name}→elsewhere: {guides_a}, "
                f"{fw_b.name}→elsewhere: {guides_b}."
            )

        return FrameworkComparison(
            framework_a_id=fw_a.id,
            framework_a_name=fw_a.name,
            framework_b_id=fw_b.id,
            framework_b_name=fw_b.name,
            use_case=use_case,
            dimensions=dimensions,
            overall_winner=overall_winner_id,
            overall_winner_name=overall_winner_name,
            overall_score_a=round(oa, 1),
            overall_score_b=round(ob, 1),
            confidence_a=scores_a.confidence or 0.0,
            confidence_b=scores_b.confidence or 0.0,
            recommendation=_narrative_recommendation(
                fw_a, fw_b, overall_winner_id, oa, ob, use_case
            ),
            when_to_pick_a=_when_to_pick(fw_a, [], overall_winner_id == fw_a.id),
            when_to_pick_b=_when_to_pick(fw_b, [], overall_winner_id == fw_b.id),
            migration_note=migration_note,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
