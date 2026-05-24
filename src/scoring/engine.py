from datetime import date, timedelta
from typing import Optional

from src.data.models import FrameworkSchema, ComputedScores

class ScoringEngine:
    def __init__(self, today: Optional[date] = None):
        # Allow injecting a specific date for testing, default to today
        self.today = today or date.today()

    def compute_scores(self, framework: FrameworkSchema) -> ComputedScores:
        """
        Computes all dimension scores and the overall TrueArch score
        for a given framework.
        """
        scores = ComputedScores()
        
        # 1. Production Stability (30%)
        scores.production_stability = self._compute_production_stability(framework)
        
        # 2. Ecosystem Momentum (25%)
        scores.ecosystem_momentum = self._compute_ecosystem_momentum(framework)
        
        # 3. Migration Risk (15%) - Reverse scored (higher = lower lock-in)
        scores.migration_risk = self._compute_migration_risk(framework)
        
        # 4. Governance Readiness (15%)
        scores.governance_readiness = self._compute_governance_readiness(framework)
        
        # 5. Agent Compatibility (15%)
        scores.agent_compatibility = self._compute_agent_compatibility(framework)
        
        # Calculate Overall Score (Weighted Average) — clamped to [0, 100]
        raw_overall = (
            (scores.production_stability * 0.30) +
            (scores.ecosystem_momentum * 0.25) +
            (scores.migration_risk * 0.15) +
            (scores.governance_readiness * 0.15) +
            (scores.agent_compatibility * 0.15)
        )
        scores.overall = float(max(0, min(100, round(raw_overall))))
        
        # Calculate Confidence Score
        scores.confidence = self._compute_confidence(framework)
        
        # Determine if it's a proxy confidence (based on community migrations rather than true lineage)
        outcomes = framework.signals.migration_risk.community_migrations
        scores.is_proxy_confidence = bool(outcomes > 0)
        
        # Determine Score Band
        scores.score_band = self._determine_score_band(scores.overall)
        
        # Set Validity
        scores.last_computed = self.today
        scores.valid_until = self.today + timedelta(days=30)

        # Staleness status
        staleness_status, staleness_warning = self._determine_staleness(scores)
        scores.staleness_status = staleness_status
        scores.staleness_warning = staleness_warning

        return scores

    def _compute_production_stability(self, fw: FrameworkSchema) -> float:
        sig = fw.signals.production_stability
        
        # Override for archived/unmaintained (using a known issue flag or simply by a property,
        # but for now, we'll check if it's explicitly marked. If momentum commits are 0, it might be unmaintained,
        # but let's stick strictly to the formula and known issues if possible)
        # Actually, formula says: Archived/unmaintained -> Production Stability = 5
        # We can check curation notes or known issues for "MAINTENANCE MODE" or "archived"
        is_maintenance = any(
            "maintenance mode" in issue.description.lower() or "abandoned" in issue.description.lower()
            for issue in fw.known_issues
        )
        if is_maintenance:
            return 5.0

        # Breaking change rate
        breaking_score = max(0.0, 100.0 - (sig.breaking_changes_per_90d * 20.0))
        
        # Issue resolution rate
        resolution_score = min(100.0, sig.issue_resolution_ratio * 100.0)
        
        # Security advisory score
        security_score = max(0.0, 100.0 - (sig.open_security_advisories * 15.0))
        
        # Production incident score
        # Edge case: no data -> default to 0.10
        incident_rate = sig.incident_rate if sig.incident_rate_source != "default" else 0.10
        incident_score = max(0.0, 100.0 - (incident_rate * 333.0))
        
        # New framework cap is applied if released < 6 months ago
        # We can approximate by checking latest_stable_released if it's a date string
        # For simplicity in this engine version, we skip the exact 6 month check unless strictly parsed.
        
        stability = (
            breaking_score * 0.30 +
            resolution_score * 0.25 +
            security_score * 0.25 +
            incident_score * 0.20
        )
        return round(stability, 2)

    def _compute_ecosystem_momentum(self, fw: FrameworkSchema) -> float:
        sig = fw.signals.ecosystem_momentum
        
        # Commit velocity trend
        commits_90d = sig.commits_last_90d
        commits_prev_90d = max(1, sig.commits_prev_90d)
        commit_trend = commits_90d / commits_prev_90d
        commit_score = min(100.0, max(0.0, (commit_trend - 0.5) * 100.0))
        
        # Star growth
        # Approx 30d ago stars = stars - (stars * star_growth_pct / 100)
        # Actually star_growth_30d_pct is given directly
        star_growth_pct = sig.star_growth_30d_pct
        star_score = min(100.0, max(0.0, 50.0 + star_growth_pct * 10.0))
        if sig.github_stars == 0:
            star_score = 50.0 # Proprietary
            commit_score = 50.0
            
        # PR activity
        pr_volume_score = min(100.0, sig.merged_prs_per_30d * 5.0)
        pr_speed_score = max(0.0, 100.0 - (sig.avg_days_to_merge * 10.0))
        pr_score = (pr_volume_score + pr_speed_score) / 2.0
        
        # Job demand (Normalize against ecosystem_max_jobs, say 6000 for MongoDB)
        ecosystem_max_jobs = 6000
        job_score = min(100.0, (sig.job_postings_30d / ecosystem_max_jobs) * 100.0)
        if sig.job_postings_30d == 0:
            job_score = 50.0 # Edge case handling
            
        # Community Q&A
        questions_30d = sig.so_questions_30d
        questions_prev_30d = max(1, sig.so_questions_prev_30d)
        qa_trend = questions_30d / questions_prev_30d
        qa_score = min(100.0, max(0.0, qa_trend * 50.0))
        if questions_30d == 0 and questions_prev_30d == 1:
            qa_score = 50.0

        momentum = (
            commit_score * 0.25 +
            star_score * 0.15 +
            pr_score * 0.20 +
            job_score * 0.25 +
            qa_score * 0.15
        )
        return round(momentum, 2)

    def _compute_migration_risk(self, fw: FrameworkSchema) -> float:
        sig = fw.signals.migration_risk
        
        alt_score = min(100.0, sig.viable_alternatives * 33.33)
        api_score = max(0.0, 100.0 - (sig.public_api_methods / 5.0))
        migration_doc_score = min(100.0, sig.migration_guide_count * 33.33)
        migration_report_score = min(100.0, sig.community_migrations * 10.0)
        
        risk = (
            alt_score * 0.30 +
            api_score * 0.25 +
            migration_doc_score * 0.25 +
            migration_report_score * 0.20
        )
        return round(risk, 2)

    def _compute_governance_readiness(self, fw: FrameworkSchema) -> float:
        sig = fw.signals.governance_readiness
        
        cve_penalty = sig.unpatched_cves * 20.0
        patch_speed_score = max(0.0, 100.0 - (sig.avg_days_to_patch * 2.0))
        security_score = max(0.0, ((100.0 - cve_penalty) + patch_speed_score) / 2.0)
        
        doc_score = float(sig.doc_completeness_rating)
        
        compliance_score = min(100.0,
            (sig.hipaa_deployments > 0) * 30.0 +
            (sig.soc2_deployments > 0) * 25.0 +
            (sig.gdpr_deployments > 0) * 25.0 +
            (sig.other_compliance_deployments > 0) * 20.0
        )
        
        audit_mapping = {'native': 100.0, 'plugin': 60.0, 'none': 0.0}
        audit_score = audit_mapping.get(sig.audit_support, 0.0)
        
        gov = (
            security_score * 0.30 +
            doc_score * 0.25 +
            compliance_score * 0.25 +
            audit_score * 0.20
        )
        return round(gov, 2)

    def _compute_agent_compatibility(self, fw: FrameworkSchema) -> float:
        sig = fw.signals.agent_compatibility
        
        mcp_mapping = {'native': 100.0, 'community_plugin': 70.0, 'wrapper_available': 40.0, 'none': 0.0}
        mcp_score = mcp_mapping.get(sig.mcp_support, 0.0)
        
        async_score = (
            (sig.is_async_native * 40.0) +
            (sig.is_thread_safe * 35.0) +
            (sig.has_concurrency_benchmarks * 25.0)
        )
        
        state_score = float(sig.state_management_rating)
        
        multi_mapping = {'native': 100.0, 'possible': 60.0, 'limited': 30.0, 'none': 0.0}
        multiagent_score = multi_mapping.get(sig.multiagent_support, 0.0)
        
        compat = (
            mcp_score * 0.30 +
            async_score * 0.25 +
            state_score * 0.25 +
            multiagent_score * 0.20
        )
        return round(compat, 2)

    def _compute_confidence(self, fw: FrameworkSchema) -> float:
        base_confidence = 70.0
        adjustments = 0.0
        
        # Outcome records in lineage (Proxy: community_migrations from migration_risk)
        # Assuming TrueArch lineage has `community_migrations` as proxy for outcomes
        outcomes = fw.signals.migration_risk.community_migrations
        if outcomes >= 200:
            adjustments += 20.0
        elif outcomes >= 51:
            adjustments += 15.0
        elif outcomes >= 11:
            adjustments += 10.0
        elif outcomes >= 1:
            adjustments += 5.0
            
        # Age of signals (comparing signals_date with today)
        signal_dates = [
            fw.signals.production_stability.signals_date,
            fw.signals.ecosystem_momentum.signals_date,
            fw.signals.migration_risk.signals_date,
            fw.signals.governance_readiness.signals_date,
            fw.signals.agent_compatibility.signals_date
        ]
        
        max_age_days = max((self.today - d).days for d in signal_dates)
        if max_age_days < 7:
            adjustments += 5.0
        elif max_age_days < 30:
            adjustments += 0.0
        elif max_age_days > 90:
            adjustments -= 20.0
        elif max_age_days >= 31:
            adjustments -= 8.0
            
        # Production incident data points
        if fw.signals.production_stability.incident_rate_source == "default":
            adjustments -= 15.0
            
        # Maintenance mode
        is_maintenance = any(
            "maintenance mode" in issue.description.lower()
            for issue in fw.known_issues
        )
        if is_maintenance:
            adjustments -= 10.0
            
        confidence = min(99.0, max(10.0, base_confidence + adjustments))
        return round(confidence, 1)

    def _determine_score_band(self, score: float) -> str:
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Strong"
        elif score >= 60:
            return "Good"
        elif score >= 45:
            return "Fair"
        elif score >= 30:
            return "Weak"
        else:
            return "Poor"

    def _determine_staleness(
        self,
        scores: "ComputedScores",
    ) -> tuple:
        """
        Compute staleness status from last_computed date.
        Per SCORING_FORMULA.md DL-019:
          fresh      → last_computed < 7 days ago
          acceptable → 7-30 days
          stale      → 31-60 days (confidence penalty applied)
          expired    → >60 days (recommendation blocked)
        """
        if not scores.last_computed:
            return ("expired", "No computation date recorded — signals may be very stale.")

        days_old = (self.today - scores.last_computed).days

        if days_old < 0:
            return ("expired", "Computation date is in the future. Check system clock.")
        elif days_old <= 7:
            return ("fresh", None)
        elif days_old <= 30:
            return ("acceptable", None)
        elif days_old <= 60:
            return (
                "stale",
                f"Signals are {days_old} days old. Confidence reduced. "
                "Re-validate before using in production decisions.",
            )
        else:
            return (
                "expired",
                f"Signals are {days_old} days old (>60 days). "
                "This score is expired and should not be used for architectural decisions. "
                "Re-curate framework data immediately.",
            )

if __name__ == "__main__":
    from src.data.loader import FrameworkLoader
    import os
    
    base_dir = "." if os.path.exists("data/frameworks") else "../.."
    data_dir = os.path.join(base_dir, "data/frameworks")
    
    try:
        loader = FrameworkLoader(data_dir=data_dir)
        frameworks = loader.load_all()
        
        engine = ScoringEngine()
        
        for fw_id, fw in frameworks.items():
            scores = engine.compute_scores(fw)
            print(f"\n[{fw.name}] Overall Score: {scores.overall} ({scores.score_band}) | Confidence: {scores.confidence}%")
            print(f"  - Production Stability: {scores.production_stability}")
            print(f"  - Ecosystem Momentum:   {scores.ecosystem_momentum}")
            print(f"  - Migration Risk:       {scores.migration_risk}")
            print(f"  - Governance Readiness: {scores.governance_readiness}")
            print(f"  - Agent Compatibility:  {scores.agent_compatibility}")
            
    except Exception as e:
        print(f"Error testing scoring engine: {e}")
