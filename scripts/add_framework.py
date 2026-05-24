#!/usr/bin/env python3
"""
TrueArch Framework Scaffolder.

Generates a new framework YAML file pre-populated with the required schema fields,
sensible defaults, and inline comments explaining each section.

Usage:
    python scripts/add_framework.py langgraph_v2 "LangGraph v2" orchestration
    python scripts/add_framework.py my_db "My Database" db

The output file is written to data/frameworks/<framework_id>.yaml
You must then manually fill in the signal values and run the scoring engine.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

_DATA_DIR = Path("data/frameworks")

_TEMPLATE = '''\
schema_version: "1.0"

# ─────────────────────────────────────────────
# IDENTITY
# ─────────────────────────────────────────────
id: "{framework_id}"
name: "{framework_name}"
category: "{category}"
subcategory: null                        # e.g. "stateful-agent-orchestration"
url: "https://github.com/OWNER/{framework_id}"
docs_url: "https://docs.example.com"
license: "MIT"                           # MIT, Apache-2.0, BSD, proprietary, etc.
primary_language: "Python"
latest_stable_version: "0.1.0"           # Exact version from PyPI/npm/etc.
latest_stable_released: "{today}"

genome_dimension:
  key: "D8_orchestrator"                 # Which genome dimension this framework fills
  value: "{genome_code}"                 # 2-5 char uppercase code for the Genome

# ─────────────────────────────────────────────
# RAW SIGNALS — Fill in from real sources
# ─────────────────────────────────────────────
signals:
  production_stability:
    breaking_changes_per_90d: 0          # Count from changelog/releases
    issue_resolution_ratio: 0.50         # closed_issues / total_issues
    open_security_advisories: 0          # From GitHub Security Advisories
    incident_rate: 0.10                  # Default if no production telemetry
    incident_rate_source: "default"      # "telemetry", "curated", or "default"
    signals_date: "{today}"

  ecosystem_momentum:
    github_stars: 0                      # From GitHub (0 if proprietary)
    star_growth_30d_pct: 0.0             # (stars_now - stars_30d_ago) / stars_30d_ago * 100
    commits_last_90d: 0                  # From GitHub Insights
    commits_prev_90d: 1                  # Previous 90 days (min 1 to avoid div/0)
    merged_prs_per_30d: 0
    avg_days_to_merge: 5.0
    job_postings_30d: 0                  # From LinkedIn/Indeed/similar
    so_questions_30d: 0                  # Stack Overflow tag questions
    so_questions_prev_30d: 1             # Previous period (min 1)
    signals_date: "{today}"

  migration_risk:
    viable_alternatives: 0               # Count of comparable frameworks
    public_api_methods: 50               # From API docs / dir(module)
    migration_guide_count: 0             # Official + community guides
    community_migrations: 0              # Known migration case studies
    signals_date: "{today}"

  governance_readiness:
    unpatched_cves: 0
    avg_days_to_patch: 30
    doc_completeness_rating: 50          # 0-100, human-assessed
    hipaa_deployments: 0
    soc2_deployments: 0
    gdpr_deployments: 0
    other_compliance_deployments: 0
    audit_support: "none"                # "native", "plugin", or "none"
    signals_date: "{today}"

  agent_compatibility:
    mcp_support: "none"                  # "native", "community_plugin", "wrapper_available", "none"
    is_async_native: false
    is_thread_safe: false
    has_concurrency_benchmarks: false
    state_management_rating: 50          # 0-100, human-assessed
    multiagent_support: "none"           # "native", "possible", "limited", "none"
    signals_date: "{today}"

# ─────────────────────────────────────────────
# COMPUTED SCORES (engine-generated — leave null)
# ─────────────────────────────────────────────
computed_scores:
  production_stability: null
  ecosystem_momentum: null
  migration_risk: null
  governance_readiness: null
  agent_compatibility: null
  overall: null
  confidence: null
  score_band: null
  last_computed: null
  valid_until: null

# ─────────────────────────────────────────────
# KNOWN ISSUES — Add production-relevant issues
# ─────────────────────────────────────────────
known_issues: []
#  - id: "{framework_id_upper}-001"
#    severity: "medium"               # critical, high, medium, low
#    description: "Description of the issue"
#    affected_versions: "all"
#    resolved: false
#    resolved_in: null
#    workaround: "How to work around it"
#    source: "https://github.com/..."

# ─────────────────────────────────────────────
# COMPATIBILITY
# ─────────────────────────────────────────────
compatible_with: []
#  - framework: "redis"
#    strength: 0.80
#    notes: "Works well together for X use case"

conflicts_with: []
supersedes: []
migrates_to: []

# ─────────────────────────────────────────────
# CURATION METADATA
# ─────────────────────────────────────────────
curation:
  status: "pending"                      # "curated", "pending", "deprecated"
  last_validated: "{today}"
  validated_by: "auto-scaffold"
  next_validation_due: "{next_due}"
  confidence_override: null
  sources:
    - "https://github.com/OWNER/{framework_id}"
  notes: |
    Auto-scaffolded on {today}. All signal values are PLACEHOLDERS.
    Fill in real data from the sources above, then change status to "curated".
'''

# Genome dimension keys by category
_CATEGORY_TO_GENOME_KEY = {
    "orchestration": "D8_orchestrator",
    "vector-db": "D7_store",
    "observability": "D9_observability",
    "safety": "D4_compliance",
    "api": "D6_protocol",
    "api-layer": "D6_protocol",
    "db": "D7_store",
    "db+vector": "D7_store",
    "database": "D7_store",
    "deployment": "D10_deployment",
    "protocol": "D6_protocol",
}


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold a new TrueArch framework YAML file."
    )
    parser.add_argument("framework_id", help="Unique framework ID (e.g. 'my_framework')")
    parser.add_argument("framework_name", help="Human-readable name (e.g. 'My Framework')")
    parser.add_argument("category", help="Category (orchestration, vector-db, observability, safety, api, db, deployment, protocol)")
    parser.add_argument("--genome-code", default=None, help="Genome code (2-5 chars, auto-generated if omitted)")
    parser.add_argument("--data-dir", default=None, help=f"Output directory (default: {_DATA_DIR})")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else _DATA_DIR
    out_path = data_dir / f"{args.framework_id}.yaml"

    if out_path.exists():
        print(f"Error: {out_path} already exists. Delete it first or choose a different ID.", file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    next_due = (date.today() + timedelta(days=30)).isoformat()
    genome_code = args.genome_code or args.framework_id[:5].upper()
    genome_key = _CATEGORY_TO_GENOME_KEY.get(args.category.lower(), "D8_orchestrator")

    content = _TEMPLATE.format(
        framework_id=args.framework_id,
        framework_name=args.framework_name,
        category=args.category,
        today=today,
        next_due=next_due,
        genome_code=genome_code,
        genome_key=genome_key,
        framework_id_upper=args.framework_id.upper().replace("-", "_"),
    )

    out_path.write_text(content, encoding="utf-8")
    print(f"✓ Scaffolded: {out_path}")
    print(f"  ID:       {args.framework_id}")
    print(f"  Name:     {args.framework_name}")
    print(f"  Category: {args.category}")
    print(f"  Genome:   {genome_code}")
    print()
    print("Next steps:")
    print(f"  1. Edit {out_path} — fill in real signal values")
    print(f"  2. Change curation.status from 'pending' to 'curated'")
    print(f"  3. Run: python -c \"from src.data.loader import FrameworkLoader; FrameworkLoader().load_all()\"")
    print(f"     to validate the YAML parses correctly")


if __name__ == "__main__":
    main()
