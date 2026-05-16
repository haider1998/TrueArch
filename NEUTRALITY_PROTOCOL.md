# TrueArch — Open Neutrality Protocol

> **Version:** 1.0
> **Purpose:** Prove neutrality structurally, not just claim it. Neutrality without mechanism is a promise. Neutrality with mechanism is a moat.

---

## Why This Document Exists

Any tool that evaluates frameworks will be suspected of bias. Framework teams will accuse TrueArch of favoring competitors. Developers will ask who funds TrueArch. Investors in specific frameworks will question methodology.

This protocol makes neutrality **auditable and falsifiable** — so accusations can be answered with evidence, not reassurances.

---

## The 6 Neutrality Mechanisms

### Mechanism 1 — Open Scoring Methodology

**What:** Every formula used to compute TrueArch Scores is published publicly.

**Where:** `SCORING_FORMULA.md` in this repository (open source)

**What this proves:** Anyone can verify that LangGraph's 84/100 score is derived from the specific signals and weights documented — not editorial preference.

**Maintenance:** Every methodology change is git-committed with a rationale comment. Changes are listed in a public `METHODOLOGY_CHANGELOG.md`.

---

### Mechanism 2 — Open Raw Signal Data

**What:** The raw input signals used to compute scores are published publicly.

**Where:** `data/frameworks/*.yaml` in `github.com/TrueArchAI/genome-spec` (Apache 2.0)

**What this proves:** Anyone can re-run the scoring formula against the raw data and arrive at the same score. Scores are reproducible.

**Maintenance:** Raw signals refreshed on cadence documented per-framework in each YAML file.

---

### Mechanism 3 — Score Challenge Process

**What:** Any framework team or developer can formally challenge a score with evidence.

**Process:**
1. Submit challenge at `truearch.ai/score/{framework}/challenge`
2. Provide: specific signal values you dispute + evidence (links, benchmarks, data)
3. TrueArch responds within **10 business days**
4. If evidence is valid → score updated with public changelog entry
5. If evidence is insufficient → rejection documented with reasoning
6. **Challenge history is permanently public** — including rejected challenges with rationale

**What this proves:** TrueArch is willing to be wrong and correct itself. The process is transparent. Framework teams cannot buy better scores but can correct inaccurate data.

---

### Mechanism 4 — Conflict of Interest Register

**What:** A public register of all commercial relationships that could create scoring bias.

**Published at:** `truearch.ai/neutrality/conflicts`

**Format:**

| Entity | Relationship | Since | Potential Bias | Mitigation |
|---|---|---|---|---|
| [Framework Team X] | Verified Partner (metadata maintenance fee) | 2026-Q3 | Could favor their framework | Score computed independently; partner status disclosed on score page |
| [Investor Y] | Angel investment | 2026-Q2 | Investor may have framework interests | Scoring committee reviews any framework where investor has stake |

**Rule:** Any framework where a conflict exists must have its score reviewed by the Advisory Board before publication.

---

### Mechanism 5 — Independent Advisory Board

**What:** 5–7 respected, independent AI engineers who review TrueArch's evaluation methodology quarterly.

**Composition requirements:**
- No more than 1 person employed by any single AI lab
- No more than 1 person with financial stake in any single AI framework
- At least 2 practitioners (people actively building AI systems in production)
- At least 1 academic researcher in AI/ML systems
- All members are named publicly with their affiliations

**Responsibilities:**
- Quarterly methodology review
- Dispute arbitration (when score challenges are contested)
- Annual "Neutrality Report" published publicly

**What this proves:** Independent experts with no TrueArch financial interest verify that the methodology is fair. This is the equivalent of an independent audit.

---

### Mechanism 6 — Version-Controlled Intelligence

**What:** All score changes and methodology changes are tracked in git with timestamps and rationale.

**What this proves:** If a score changes, the exact reason is auditable. Nobody can secretly adjust a score in response to commercial pressure — all changes are public and dated.

**Implementation:**
- `data/frameworks/*.yaml` files are in a public git repo
- Every score-affecting change requires a commit message explaining the trigger
- Automated tests validate that score changes correlate to documented signal changes

---

## What Neutrality Does NOT Mean

| Misconception | Reality |
|---|---|
| "Neutral means no opinions" | We have strong opinions — they're based on evidence |
| "Neutral means all frameworks are equal" | Some frameworks are objectively better for specific contexts |
| "Neutral means no commercial relationships" | Partners can pay for metadata maintenance, NOT for better scores |
| "Neutral means never being wrong" | We will make mistakes; the protocol ensures they're corrected publicly |

---

## Neutrality Violations — What We Will Do

If TrueArch ever violates its own neutrality protocol:

1. **Disclose immediately** — public announcement on truearch.ai
2. **Correct the score** — with a detailed explanation of what went wrong
3. **Compensate affected parties** — refund any commercial relationships that created the conflict
4. **Publish a post-mortem** — how the violation occurred and how the protocol is being strengthened

**The moment TrueArch hides a neutrality violation, it is done.**

---

## Decision Log

### DL-020 — Neutrality Protocol is a public document
- **Decision:** The Open Neutrality Protocol is published in the open-source repo
- **Rationale:** A neutrality protocol that's private is worthless. The act of publishing it creates accountability.
- **Date:** 2026-05-16

---

*Last updated: 2026-05-16 v1.0*
