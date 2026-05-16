"""
Standalone validation script — no external dependencies (only stdlib + pydantic).
Runs against the pydantic models to validate scoring logic using synthetic data.

Usage:
    python3 tests/run_validation.py

This is a fallback for environments where PyYAML/fastapi are not yet installed.
Once `pip install -r requirements.txt` succeeds, use `pytest` instead.
"""
import sys
import json
from datetime import date, timedelta
from pathlib import Path

# ── Ensure src/ is importable ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.data.models import (
        FrameworkSchema, GenomeDimension, Signals,
        ProductionStabilitySignals, EcosystemMomentumSignals,
        MigrationRiskSignals, GovernanceReadinessSignals,
        AgentCompatibilitySignals, ComputedScores, CurationMetadata
    )
    from src.scoring.engine import ScoringEngine
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    print("Ensure you are running from the project root.")
    sys.exit(1)

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))

def make_framework(
    *,
    breaking_changes=0,
    resolution_ratio=0.9,
    open_cves=0,
    incident_rate=0.02,
    incident_source="curated",
    stars=10000,
    star_growth=2.0,
    commits_90=200,
    commits_prev=180,
    merged_prs=20,
    avg_merge=3.0,
    jobs=1000,
    so_now=100,
    so_prev=90,
    alternatives=3,
    api_methods=50,
    migration_guides=3,
    community_migs=10,
    unpatched_cves=0,
    patch_days=2,
    doc_rating=90,
    hipaa=5, soc2=10, gdpr=10, other_c=2,
    audit="native",
    mcp="native",
    is_async=True,
    is_threadsafe=True,
    has_benchmarks=True,
    state_rating=80,
    multiagent="native",
    known_issues=None,
    category="orchestration",
    fw_id="test_fw",
) -> FrameworkSchema:
    today = date(2026, 5, 16)
    return FrameworkSchema(
        schema_version="1.0",
        id=fw_id,
        name="Test Framework",
        category=category,
        subcategory="test",
        url="https://example.com",
        docs_url="https://example.com/docs",
        license="MIT",
        primary_language="Python",
        latest_stable_version="1.0.0",
        latest_stable_released="2026-01-01",
        genome_dimension=GenomeDimension(key="D8_orchestrator", value="TEST"),
        signals=Signals(
            production_stability=ProductionStabilitySignals(
                breaking_changes_per_90d=breaking_changes,
                issue_resolution_ratio=resolution_ratio,
                open_security_advisories=open_cves,
                incident_rate=incident_rate,
                incident_rate_source=incident_source,
                signals_date=today,
            ),
            ecosystem_momentum=EcosystemMomentumSignals(
                github_stars=stars,
                star_growth_30d_pct=star_growth,
                commits_last_90d=commits_90,
                commits_prev_90d=commits_prev,
                merged_prs_per_30d=merged_prs,
                avg_days_to_merge=avg_merge,
                job_postings_30d=jobs,
                so_questions_30d=so_now,
                so_questions_prev_30d=so_prev,
                signals_date=today,
            ),
            migration_risk=MigrationRiskSignals(
                viable_alternatives=alternatives,
                public_api_methods=api_methods,
                migration_guide_count=migration_guides,
                community_migrations=community_migs,
                signals_date=today,
            ),
            governance_readiness=GovernanceReadinessSignals(
                unpatched_cves=unpatched_cves,
                avg_days_to_patch=patch_days,
                doc_completeness_rating=doc_rating,
                hipaa_deployments=hipaa,
                soc2_deployments=soc2,
                gdpr_deployments=gdpr,
                other_compliance_deployments=other_c,
                audit_support=audit,
                signals_date=today,
            ),
            agent_compatibility=AgentCompatibilitySignals(
                mcp_support=mcp,
                is_async_native=is_async,
                is_thread_safe=is_threadsafe,
                has_concurrency_benchmarks=has_benchmarks,
                state_management_rating=state_rating,
                multiagent_support=multiagent,
                signals_date=today,
            ),
        ),
        computed_scores=ComputedScores(),
        known_issues=known_issues or [],
        curation=CurationMetadata(
            status="curated",
            last_validated=today,
            validated_by="founder",
            next_validation_due=today + timedelta(days=30),
            sources=["https://example.com"],
            notes="Test framework",
        ),
    )


def run_tests():
    print("\n" + "═" * 60)
    print("  TrueArch — Validation Suite (no-dependency mode)")
    print("═" * 60 + "\n")

    engine = ScoringEngine(today=date(2026, 5, 16))

    # ── 1. Basic score computation ─────────────────────────────────────────────
    print("[ Group 1: Basic score computation ]")
    fw = make_framework()
    scores = engine.compute_scores(fw)

    check("All dimension scores are populated",
          all(x is not None for x in [
              scores.production_stability, scores.ecosystem_momentum,
              scores.migration_risk, scores.governance_readiness,
              scores.agent_compatibility, scores.overall
          ]))
    check("Overall score in [0, 100]", 0 <= scores.overall <= 100,
          f"got {scores.overall}")
    check("Confidence in [10, 99]", 10 <= scores.confidence <= 99,
          f"got {scores.confidence}")
    check("Score band is valid",
          scores.score_band in {"Excellent", "Strong", "Good", "Fair", "Weak", "Poor"},
          f"got '{scores.score_band}'")
    check("valid_until is 30 days after last_computed",
          scores.valid_until == scores.last_computed + timedelta(days=30))

    # ── 2. Score band boundaries ───────────────────────────────────────────────
    print("\n[ Group 2: Score band boundaries ]")
    for score_val, expected_band in [
        (95, "Excellent"), (75, "Strong"), (60, "Good"),
        (45, "Fair"), (30, "Weak"), (29, "Poor"),
    ]:
        band = engine._determine_score_band(score_val)
        check(f"Score {score_val} → '{expected_band}'", band == expected_band,
              f"got '{band}'")

    # ── 3. Maintenance mode override ──────────────────────────────────────────
    print("\n[ Group 3: Maintenance mode override ]")
    from src.data.models import KnownIssue
    maintenance_issue = KnownIssue(
        id="TEST-001",
        severity="high",
        description="MAINTENANCE MODE: No active development.",
        affected_versions="all",
        resolved=False,
        source="https://example.com",
    )
    fw_maint = make_framework(known_issues=[maintenance_issue])
    s = engine.compute_scores(fw_maint)
    check("Maintenance mode caps production_stability at 5.0",
          s.production_stability == 5.0, f"got {s.production_stability}")
    check("Maintenance mode reduces confidence",
          s.confidence < 80, f"got {s.confidence}")

    # ── 4. CVE penalty ────────────────────────────────────────────────────────
    print("\n[ Group 4: CVE penalty ]")
    fw_cve = make_framework(unpatched_cves=5)
    s_cve = engine.compute_scores(fw_cve)
    fw_clean = make_framework(unpatched_cves=0)
    s_clean = engine.compute_scores(fw_clean)
    check("5 unpatched CVEs lowers governance vs 0 CVEs",
          s_cve.governance_readiness < s_clean.governance_readiness,
          f"{s_cve.governance_readiness} < {s_clean.governance_readiness}")

    # ── 5. Native MCP boosts agent compatibility ──────────────────────────────
    print("\n[ Group 5: Agent compatibility ]")
    fw_native = make_framework(mcp="native")
    fw_none = make_framework(mcp="none")
    s_native = engine.compute_scores(fw_native)
    s_none = engine.compute_scores(fw_none)
    check("native MCP > no MCP for agent compatibility",
          s_native.agent_compatibility > s_none.agent_compatibility,
          f"{s_native.agent_compatibility} vs {s_none.agent_compatibility}")

    # ── 6. Migration risk is reverse-scored ───────────────────────────────────
    print("\n[ Group 6: Migration risk (reverse-scored) ]")
    fw_easy = make_framework(alternatives=4, migration_guides=5, community_migs=15)
    fw_locked = make_framework(alternatives=0, migration_guides=0, community_migs=0,
                               api_methods=500)
    s_easy = engine.compute_scores(fw_easy)
    s_locked = engine.compute_scores(fw_locked)
    check("Easily migratable framework scores higher migration risk",
          s_easy.migration_risk > s_locked.migration_risk,
          f"{s_easy.migration_risk} > {s_locked.migration_risk}")

    # ── 7. Default incident source penalty ───────────────────────────────────
    print("\n[ Group 7: Default incident source penalty ]")
    fw_default = make_framework(incident_source="default")
    fw_curated = make_framework(incident_source="curated")
    s_def = engine.compute_scores(fw_default)
    s_cur = engine.compute_scores(fw_curated)
    check("'default' incident source lowers confidence vs 'curated'",
          s_def.confidence < s_cur.confidence,
          f"{s_def.confidence} < {s_cur.confidence}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    print(f"  Results: {passed} passed, {failed} failed ({len(results)} total)")

    if failed:
        print("\nFailed tests:")
        for status, name, detail in results:
            if status == FAIL:
                print(f"  {FAIL}  {name}  {detail}")
        sys.exit(1)
    else:
        print("\n  All validations passed. ✅")
        print("─" * 60 + "\n")


if __name__ == "__main__":
    run_tests()
