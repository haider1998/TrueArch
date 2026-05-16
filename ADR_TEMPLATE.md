# TrueArch ADR Template

> Copy this file to `docs/adr/ADR-NNN-short-title.md` in your project repository.
> Replace every `[PLACEHOLDER]` with your actual content.
> The TrueArch MCP server fills most fields automatically — this template is for manual use.

---

```markdown
# ADR-[NNN]: [Short Decision Title]

**Status:** [Proposed | Accepted | Deprecated | Superseded by ADR-NNN]
**Date:** [YYYY-MM-DD]
**Deciders:** [Names or roles of people involved in decision]

---

## TrueArch Intelligence

**Genome:** [e.g. MA-STAT-HOR-HIPAA-PY-MCP-REDIS+LGR+OTEL+CONT]
**Confidence Score:** [e.g. 92%]
**TrueArch Score (primary framework):** [e.g. LangGraph: 84/100]
**Recommendation Source:** truearch.ai/adr/[lineage-id]
**Generated:** [YYYY-MM-DD] | **Review By:** [YYYY-MM-DD]

---

## Context

[Describe the situation and the problem that requires a decision.
Include: what you are building, at what scale, with what team, under what constraints.]

**Key constraints:**
- Scale: [e.g. 5M users, 10K daily requests]
- Compliance: [e.g. HIPAA, SOC2, GDPR, None]
- Cloud: [e.g. AWS, GCP, Azure, multi-cloud]
- Language: [e.g. Python, TypeScript]
- Team size/maturity: [e.g. 3 engineers, strong Python, limited LLM ops experience]
- Budget: [e.g. $2K/month infrastructure budget]

---

## Decision

We will use **[PRIMARY STACK: Framework A + Framework B + ...]**.

[One paragraph explaining the core of the decision.]

---

## Rationale

[Why this stack was selected. Be specific. Reference TrueArch data where possible.]

**Primary reasons:**
- [Framework A] selected because: [specific reason with data if available]
- [Framework B] selected because: [specific reason with data if available]

**Tradeoffs accepted:**
- [Tradeoff 1]: [why this is acceptable given the context]
- [Tradeoff 2]: [why this is acceptable given the context]

---

## Alternatives Rejected

| Alternative | TrueArch Score | Reason Rejected |
|---|---|---|
| [Framework X] | [score]/100 | [specific reason] |
| [Framework Y] | [score]/100 | [specific reason] |
| [Approach Z] | N/A | [specific reason] |

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| [Risk 1] | [Low/Medium/High] | [How it's mitigated] |
| [Risk 2] | [Low/Medium/High] | [How it's mitigated] |

**TrueArch-flagged risks:**
- [Any risks surfaced by TrueArch Future Risk Prediction or Mortality Score]

---

## Architecture Genome

```
[Full genome string, e.g.:]
MA-STAT-HOR-HIPAA-PY-MCP-REDIS+LGR+OTEL+CONT
```

**Genome breakdown:**

| Dimension | Value | Meaning |
|---|---|---|
| D1 Pattern | MA | Multi-agent |
| D2 Memory | STAT | Stateful (persistent) |
| D3 Scaling | HOR | Horizontal |
| D4 Compliance | HIPAA | Healthcare compliance |
| D5 Language | PY | Python |
| D6 Protocol | MCP | Model Context Protocol |
| D7 Store | REDIS | Redis memory layer |
| D8 Orchestrator | LGR | LangGraph |
| D9 Observability | OTEL | OpenTelemetry |
| D10 Deployment | CONT | Containerized |

---

## Outcome Tracking

> Fill this section 3–6 months after implementation.

**Outcome recorded:** [YYYY-MM-DD]

- [ ] Architecture scaled as expected
- [ ] Production incidents: [count]
- [ ] What broke (if anything): [description]
- [ ] Technical debt introduced: [description or "none"]
- [ ] Would choose this stack again: [Yes/No/Partially]
- [ ] Regret score: [0–10, where 0 = no regret, 10 = complete regret]

[Submit outcome to TrueArch: truearch.ai/lineage/[lineage-id]/outcome]

---

## References

- TrueArch Lineage Record: [truearch.ai/lineage/lineage-id]
- TrueArch Genome Spec: [github.com/TrueArchAI/genome-spec]
- [Link to relevant benchmark or post-mortem that informed this decision]
- [Link to framework documentation]

---

*Generated with TrueArch MCP — truearch.ai*
```

---

## Notes for Manual Use

**When filling this out without TrueArch MCP:**

1. Generate the Genome manually using [GENOME_TAXONOMY.md](./GENOME_TAXONOMY.md)
2. Look up framework scores at `truearch.ai/score/{framework-name}`
3. Leave `Recommendation Source` as `manual` if not using MCP
4. Set `Review By` date = today + 12 months
5. Submit the ADR URL to `truearch.ai/adr/submit` to link it to the ecosystem database

**ADR Numbering:**
- Start at ADR-001
- Increment sequentially — never reuse numbers
- Include a short kebab-case title: `ADR-001-orchestration-framework-selection.md`

**Storage location in your repo:**
```
your-project/
  docs/
    adr/
      README.md          ← Index of all ADRs
      ADR-001-*.md
      ADR-002-*.md
```
