# TrueArch — Metrics & OKR Framework

> How we measure success, trust, and strategic progress.
> Every phase has a North Star, leading indicators, lagging indicators, and anti-metrics.

---

## North Star Metric

> **"Architectural Clarity Events per Week"**

An "Architectural Clarity Event" = a developer or agent session where TrueArch output directly influenced an architectural decision (tracked via explicit confirmation, ADR generation, or stack adoption signal).

**Why this metric:**
- It measures *actual value delivered*, not vanity (API calls, page views)
- It's leading, not lagging — it happens before the architecture is built
- It's hard to game — it requires genuine decision influence
- It aligns perfectly with the magic moment: "I now know exactly what to build"

**Secondary North Star (Phase 2+):**
> **"Architecture Decisions Made with TrueArch Intelligence (Weekly)"**

---

## Phase 1 OKRs — Architecture Advisor (Months 0–6)

### Objective 1: Establish Genuine Technical Trust

| Key Result | Target | Measurement |
|---|---|---|
| KR1.1 | 100 developers who made an architecture decision using TrueArch | Usage tracking + survey |
| KR1.2 | Average "decision confidence score" of ≥4.2/5 post-recommendation | In-product survey |
| KR1.3 | ≥3 public testimonials from credible AI engineers | Qualitative |
| KR1.4 | First public architecture report with ≥500 shares | Social tracking |
| KR1.5 | Zero documented cases where TrueArch gave a provably wrong recommendation | Review process |

### Objective 2: Achieve Workflow Presence

| Key Result | Target | Measurement |
|---|---|---|
| KR2.1 | Cursor MCP extension published and ≥50 installs | Extension marketplace |
| KR2.2 | REST API live with ≥10 external integrations | API key tracking |
| KR2.3 | MCP server listed in official MCP directory | Published |
| KR2.4 | Claude Code integration published | Published |

### Objective 3: Build the Intelligence Foundation

| Key Result | Target | Measurement |
|---|---|---|
| KR3.1 | ≥30 AI frameworks in the intelligence database with full metadata | Internal count |
| KR3.2 | ≥5 architecture patterns documented with production outcome data | Internal count |
| KR3.3 | Recommendation latency ≤3 seconds (p95) | Infra monitoring |
| KR3.4 | Zero hallucinated framework version recommendations | Audit process |

---

## Phase 2 OKRs — AI Engineering Copilot (Months 6–18)

### Objective 1: Become Workflow-Embedded

| Key Result | Target | Measurement |
|---|---|---|
| KR1.1 | 1,000 weekly active developers | Usage analytics |
| KR1.2 | ≥3 enterprise pilot customers (10+ seats) | CRM |
| KR1.3 | VS Code extension published with ≥500 installs | Marketplace |
| KR1.4 | ≥50% of users return within 7 days of first use | Retention analytics |

### Objective 2: Build the Data Flywheel

| Key Result | Target | Measurement |
|---|---|---|
| KR2.1 | ≥1,000 ADRs generated via TrueArch | ADR tracking |
| KR2.2 | ≥500 opted-in telemetry users | Consent database |
| KR2.3 | First public TrueBench report published | Published |
| KR2.4 | ≥3 framework teams engaged as supply-side partners | CRM |

### Objective 3: Prove Authority

| Key Result | Target | Measurement |
|---|---|---|
| KR3.1 | "AI Framework Stability Index" cited by ≥10 external publications | Media tracking |
| KR3.2 | ≥2,000 GitHub stars across TrueArch open repositories | GitHub |
| KR3.3 | ≥5 YouTube/podcast mentions by credible AI engineers | Media tracking |

---

## Phase 3 OKRs — Continuous Intelligence Platform (Months 18–36)

### Objective 1: Scale Intelligence

| Key Result | Target | Measurement |
|---|---|---|
| KR1.1 | 10,000 weekly active developers | Usage analytics |
| KR1.2 | ≥100 AI frameworks in ArchGraph with full relationship mapping | Internal |
| KR1.3 | First paying enterprise contract (≥$50K ARR) | Revenue |
| KR1.4 | Architecture Debt Score product launched | Product shipped |

---

## Metric Definitions

### "Architectural Clarity Event" (ACE)
A session where:
1. A developer queried TrueArch with a specific architecture problem, AND
2. Followed up with one of: generating an ADR, copying the recommendation, rating it ≥4/5, or returning to TrueArch within the same project session

### "Decision Confidence Score"
Post-recommendation survey: "How confident are you in the architectural direction after using TrueArch?" (1–5 scale)

### "Recommendation Accuracy"
Measured retrospectively: when we have telemetry, what % of TrueArch recommendations led to successful deployments vs. architectural regret events?

### "Framework Mortality Score" (see INNOVATION.md)
0–100 score for each framework in the database, updated weekly.

---

## Anti-Metrics (What We Must NOT Optimize For)

| Anti-Metric | Why It's Dangerous |
|---|---|
| **Raw API calls** | A confused developer hammering the API looks like growth |
| **Page views on reports** | Reads ≠ trust; trust = citations and decisions influenced |
| **Total frameworks indexed** | More is not better if quality degrades |
| **Response speed at cost of accuracy** | Speed with wrong answers destroys trust |
| **Framework partners (supply side)** | Too many supply partners → appearance of bias |
| **Revenue before trust** | Monetizing before trust = killing the product |

---

## Trust Score (Internal)

Track this internally quarterly:

| Signal | Weight | How Measured |
|---|---|---|
| Decision confidence score | 30% | In-product survey |
| Recommendation re-use rate | 25% | ADR generation, copy events |
| 30-day retention | 20% | Usage analytics |
| External citations | 15% | Media monitoring |
| Zero-hallucination rate | 10% | Audit process |

**Trust Score = weighted average. Target: ≥75/100 before Phase 2 launch.**

---

## Vanity vs. Signal Metrics

```
VANITY                          SIGNAL
─────────────────────────────────────────
Total signups          vs.      Weekly active decision makers
API calls              vs.      Architectural Clarity Events
Page views             vs.      Content citations
Frameworks indexed     vs.      Frameworks with outcome data
MCP server installs    vs.      MCP server queries per ADR generated
```

---

*Last updated: 2026-05-16*
