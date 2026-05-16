# TrueArch — Scoring Formula Specification

> **Status:** v1.0 — Design complete. Implement exactly as specified.
> **Decision log:** DL-014 through DL-019

---

## Philosophy

Every number must be:
- **Explainable** — traceable to specific data signals
- **Auditable** — source citations on every score
- **Challengeable** — framework teams can dispute with evidence
- **Time-bounded** — every score has a staleness date

---

## The TrueArch Score (0–100)

Five dimensions, each scored 0–100. Overall = weighted average.

```
Overall TrueArch Score = (
  Production Stability  × 0.30 +
  Ecosystem Momentum    × 0.25 +
  Migration Risk        × 0.15 +
  Governance Readiness  × 0.15 +
  Agent Compatibility   × 0.15
)
```

**Rounding:** Always round to nearest integer. Never display decimals.

---

## Dimension 1 — Production Stability (weight: 30%)

> Measures real-world reliability. Most important dimension.

### Signals & Weights

| Signal | Weight | Source | Metric |
|---|---|---|---|
| Breaking change rate | 30% | GitHub releases + CHANGELOG | breaking changes per 90-day period |
| Issue resolution rate | 25% | GitHub Issues API | `closed_90d / opened_90d` ratio |
| Open security advisories | 25% | GitHub Security + NVD | count of unresolved CVEs |
| Production incident rate | 20% | TrueArch lineage records | `incidents / total_deployments` |

### Formulas

```python
# Breaking change rate (0–100)
# 0 breaking changes = 100; 5+ breaking changes per 90d = 0
breaking_score = max(0, 100 - (breaking_changes_per_90d * 20))

# Issue resolution rate (0–100)
# 1.0 ratio (all issues resolved) = 100; 0.0 = 0
resolution_score = min(100, resolution_ratio * 100)

# Security advisory score (0–100)
# 0 advisories = 100; 7+ open advisories = 0
security_score = max(0, 100 - (open_advisories * 15))

# Production incident score (0–100)
# 0% incident rate = 100; 30%+ incident rate = 0
incident_score = max(0, 100 - (incident_rate * 333))

# Combined
production_stability = (
  breaking_score  * 0.30 +
  resolution_score * 0.25 +
  security_score  * 0.25 +
  incident_score  * 0.20
)
```

### Edge Cases
- **Incident rate: no data** → Use `0.10` as default (10% assumed) and flag confidence ↓15%
- **New framework (< 6 months old)** → Breaking score capped at 70 (insufficient history)
- **Archived/unmaintained** → Override: Production Stability = 5 regardless of metrics

---

## Dimension 2 — Ecosystem Momentum (weight: 25%)

> Measures growth trajectory. Today's momentum predicts tomorrow's ecosystem health.

### Signals & Weights

| Signal | Weight | Source | Metric |
|---|---|---|---|
| Commit velocity trend | 25% | GitHub Commits API | commits_last_90d vs commits_prev_90d |
| Star growth rate | 15% | GitHub Stars API | `(stars_now - stars_30d_ago) / stars_30d_ago` |
| PR merge activity | 20% | GitHub PRs API | merged PRs per 30 days + avg days to merge |
| Job market demand | 25% | LinkedIn / Indeed (scraped) | job postings mentioning framework, 30-day count |
| Community Q&A velocity | 15% | Stack Overflow API | new questions per 30 days (trend, not absolute) |

### Formulas

```python
# Commit velocity trend (0–100)
# +50%+ growth = 100; flat = 50; -50%+ decline = 0
commit_trend = (commits_90d / max(1, commits_prev_90d))
commit_score = min(100, max(0, (commit_trend - 0.5) * 100))

# Star growth (0–100)
# +5%/month = 100; flat = 50; declining = lower
star_growth_pct = (stars_now - stars_30d_ago) / max(1, stars_30d_ago) * 100
star_score = min(100, max(0, 50 + star_growth_pct * 10))

# PR activity (0–100)
# >20 merged PRs/month AND avg merge time <7d = 100
pr_volume_score = min(100, merged_prs_per_30d * 5)
pr_speed_score = max(0, 100 - (avg_days_to_merge * 10))
pr_score = (pr_volume_score + pr_speed_score) / 2

# Job demand (0–100) — relative to ecosystem baseline
# Normalize against top-10 AI framework job count
job_score = min(100, (job_postings_30d / ecosystem_max_jobs) * 100)

# Community Q&A velocity (0–100)
qa_trend = questions_30d / max(1, questions_prev_30d)
qa_score = min(100, max(0, qa_trend * 50))

# Combined
ecosystem_momentum = (
  commit_score * 0.25 +
  star_score   * 0.15 +
  pr_score     * 0.20 +
  job_score    * 0.25 +
  qa_score     * 0.15
)
```

### Edge Cases
- **New framework (< 6 months)** → Star/commit history insufficient; cap score at 80; flag confidence ↓10%
- **No job posting data** → Set `job_score = 50` (neutral) and flag
- **Viral spike detected** (>200% star growth in 7 days) → Flag as "viral event — momentum may not reflect sustained adoption"

---

## Dimension 3 — Migration Risk (weight: 15%)

> Lock-in score. **Lower score = harder to migrate away.** Higher score = lower lock-in.

Note: This is intentionally "reverse" from the others. A framework with 90/100 Migration Risk
is easy to leave. A framework with 20/100 is deeply entangled in your codebase.

### Signals & Weights

| Signal | Weight | Source | Metric |
|---|---|---|---|
| Alternative availability | 30% | ArchGraph edges | count of `supersedes`/`migrates_to` edges |
| API surface size | 25% | GitHub source analysis | public API method count (proxy for entanglement) |
| Documented migration paths | 25% | GitHub + community | count of migration guides to/from framework |
| Community migration reports | 20% | TrueArch lineage | successful migrations recorded in outcome data |

### Formulas

```python
# Alternative availability (0–100)
# 3+ viable alternatives = 100; 0 alternatives = 0
alt_score = min(100, viable_alternatives * 33)

# API surface (0–100)
# Small API surface = high score (less entanglement)
# <50 public methods = 100; 500+ = 0
api_score = max(0, 100 - (public_api_methods / 5))

# Documented migration paths (0–100)
# 3+ guides = 100; 0 = 0
migration_doc_score = min(100, migration_guide_count * 33)

# Community migration reports (0–100)
# 10+ recorded migrations in lineage = 100; 0 = 0
migration_report_score = min(100, community_migrations * 10)

# Combined
migration_risk = (
  alt_score            * 0.30 +
  api_score            * 0.25 +
  migration_doc_score  * 0.25 +
  migration_report_score * 0.20
)
```

### Display Rule
Always show migration risk with direction context:
```
Migration Risk: 34/100 (low lock-in — easy to migrate away if needed)
Migration Risk: 78/100 (high lock-in — significant refactoring required to migrate)
```

---

## Dimension 4 — Governance Readiness (weight: 15%)

> Enterprise suitability. Audit, compliance, security.

### Signals & Weights

| Signal | Weight | Source | Metric |
|---|---|---|---|
| Security posture | 30% | CVE history, security policy | open CVEs + time-to-patch history |
| Documentation completeness | 25% | Docs analysis | API coverage % + changelog quality |
| Compliance capability evidence | 25% | Community + telemetry | known HIPAA/SOC2/GDPR deployments |
| Audit logging support | 20% | Framework docs + source | native observability/audit hooks present |

### Formulas

```python
# Security posture (0–100)
# 0 unpatched CVEs + fast patch history = 100
cve_penalty = unpatched_cves * 20
patch_speed_score = max(0, 100 - (avg_days_to_patch * 2))
security_score = max(0, ((100 - cve_penalty) + patch_speed_score) / 2)

# Documentation completeness (0–100)
# Manually assessed quarterly: 0 / 25 / 50 / 75 / 100
doc_score = doc_completeness_rating  # human-assessed

# Compliance evidence (0–100)
# Known HIPAA deployments=30pts, SOC2=25pts, GDPR=25pts, others=20pts
compliance_score = min(100,
  (hipaa_deployments > 0) * 30 +
  (soc2_deployments > 0) * 25 +
  (gdpr_deployments > 0) * 25 +
  (other_compliance > 0) * 20
)

# Audit logging (0–100)
# Native support=100; community plugin=60; no support=0
audit_score = {'native': 100, 'plugin': 60, 'none': 0}[audit_support]

# Combined
governance_readiness = (
  security_score    * 0.30 +
  doc_score         * 0.25 +
  compliance_score  * 0.25 +
  audit_score       * 0.20
)
```

---

## Dimension 5 — Agent Compatibility (weight: 15%)

> How well the framework operates in agentic / autonomous contexts.

### Signals & Weights

| Signal | Weight | Source | Metric |
|---|---|---|---|
| MCP integration quality | 30% | MCP registry + docs | native / plugin / none |
| Async + concurrency support | 25% | Source analysis + benchmarks | async-native, thread-safe |
| State management quality | 25% | Framework docs + telemetry | stateful operation stability |
| Multi-agent coordination | 20% | Framework docs + lineage | multi-agent patterns supported |

### Formulas

```python
# MCP integration (0–100)
mcp_score = {'native': 100, 'community_plugin': 70,
             'wrapper_available': 40, 'none': 0}[mcp_support]

# Async + concurrency (0–100)
# Async-native + thread-safe + tested at load = 100
async_score = (
  is_async_native * 40 +
  is_thread_safe * 35 +
  has_concurrency_benchmarks * 25
)

# State management (0–100)
# Assessed from: API design quality + community reports
state_score = state_management_rating  # human-assessed (0/25/50/75/100)

# Multi-agent coordination (0–100)
# Native multi-agent support = 100; possible with work = 60; not supported = 0
multiagent_score = {'native': 100, 'possible': 60,
                    'limited': 30, 'none': 0}[multiagent_support]

# Combined
agent_compatibility = (
  mcp_score        * 0.30 +
  async_score      * 0.25 +
  state_score      * 0.25 +
  multiagent_score * 0.20
)
```

---

## Confidence Score (0–100%)

Attached to every recommendation and score. Not a dimension — a meta-signal.

### Base Confidence

```python
base_confidence = 70  # start at 70% for any framework with data
```

### Adjustments (additive)

| Condition | Adjustment |
|---|---|
| Outcome records in lineage: 1–10 | +5% |
| Outcome records in lineage: 11–50 | +10% |
| Outcome records in lineage: 51–200 | +15% |
| Outcome records in lineage: 200+ | +20% |
| All signal data < 7 days old | +5% |
| All signal data < 30 days old | +0% |
| Any signal data 31–90 days old | −8% |
| Any signal data > 90 days old | −20% |
| Framework version released < 14 days ago | −8% |
| Framework version released < 7 days ago | −15% |
| 0 production incident data points | −15% |
| Framework in "caution" territory (Mortality < 50) | −10% |
| Human validator reviewed this quarter | +5% |
| Score challenged + upheld by TrueArch | +5% |

```python
confidence = min(99, max(10, base_confidence + sum(adjustments)))
```

**Hard rules:**
- Confidence can never exceed 99% (intellectual honesty — we are never certain)
- Confidence below 50%: recommendation must include prominent "⚠ Limited Data" warning
- Confidence below 30%: recommendation must not be surfaced without explicit "experimental" label

---

## Overall TrueArch Score Bands

| Score | Band | Label | Display Color |
|---|---|---|---|
| 90–100 | Excellent | Highly Recommended | Green |
| 75–89 | Strong | Recommended | Teal |
| 60–74 | Good | Suitable | Blue |
| 45–59 | Fair | Use with Caution | Yellow |
| 30–44 | Weak | Not Recommended | Orange |
| 0–29 | Poor | Avoid | Red |

---

## Score Staleness Policy

| Time since last signal refresh | Status |
|---|---|
| < 7 days | Fresh ✅ |
| 7–30 days | Acceptable ⚡ |
| 31–90 days | Stale ⚠️ — show warning |
| > 90 days | Expired 🔴 — do not surface without prominent warning |

**Automated staleness detection:** Every score must carry a `valid_until` date = `last_updated + 30 days`. Anything past `valid_until` triggers a re-computation job.

---

## Human Override Protocol

Some signals cannot be automated (docs completeness, state management quality). These are:
- Assessed quarterly by a human reviewer
- Stored with `assessed_by`, `assessed_date`, `reviewer_notes`
- Weighted at 50% of the automated signal for the same sub-dimension if both exist

---

## Decision Logs

### DL-014 — Production Stability is highest-weighted dimension (30%)
- Users trust frameworks they don't have to babysit. Stability = retention.
- Date: 2026-05-16

### DL-015 — Ecosystem Momentum uses trend, not absolute numbers
- LangGraph at 15K stars growing 10%/month is healthier than LangChain at 90K stars declining.
- Absolute star count would favor incumbents. Trend favors ecosystem truth.
- Date: 2026-05-16

### DL-016 — Migration Risk is "reverse" scoring (higher = lower lock-in)
- Counterintuitive but more honest. A high Migration Risk score means you can leave easily.
- Always display with direction context to prevent misreading.
- Date: 2026-05-16

### DL-017 — Confidence hard cap at 99%
- Intellectual honesty is the product. TrueArch never claims certainty.
- Date: 2026-05-16

### DL-018 — Human-assessed signals included for doc/state quality
- Some signals resist automation. Excluding them would make scores less accurate.
- Human assessment is weighted lower and must be dated + attributed.
- Date: 2026-05-16

### DL-019 — 30-day staleness threshold for score validity
- AI ecosystem moves fast. 30 days is aggressive but appropriate.
- Enterprise databases (PostgreSQL) can be refreshed quarterly — use `slow_moving` flag.
- Date: 2026-05-16

---

*Last updated: 2026-05-16 v1.0*
