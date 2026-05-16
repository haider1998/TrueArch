# TrueArch — Architecture & Integration Design

> Technical architecture and integration philosophy for the TrueArch intelligence infrastructure.

---

## System Architecture

```
             ┌─────────────────────────────────────────────┐
             │           Ecosystem Crawlers                │
             │  GitHub / Docs / arXiv / Releases / Issues  │
             └─────────────────────┬───────────────────────┘
                                   │
             ┌─────────────────────▼───────────────────────┐
             │        Knowledge Normalization Layer         │
             │   (deduplicate, score, version-tag, index)   │
             └─────────────────────┬───────────────────────┘
                                   │
             ┌─────────────────────▼───────────────────────┐
             │      Architecture Intelligence Graph         │
             │  (ArchGraph — frameworks, versions,          │
             │   patterns, compatibility, outcomes)         │
             └──────┬──────────────┬──────────────┬────────┘
                    │              │              │
           ┌────────▼───┐  ┌───────▼────┐  ┌─────▼────────┐
           │  Outcome   │  │   Risk     │  │   Trend      │
           │  Engine    │  │   Engine   │  │   Engine     │
           └────────┬───┘  └───────┬────┘  └─────┬────────┘
                    └──────────────┼──────────────┘
                                   │
             ┌─────────────────────▼───────────────────────┐
             │           Recommendation Engine              │
             │   (tradeoffs, maturity scores, warnings)     │
             └─────────────────────┬───────────────────────┘
                                   │
             ┌─────────────────────▼───────────────────────┐
             │         Context Compression Layer            │
             │   (TrueContext — inject only what matters)   │
             └──────┬──────────┬────────────┬──────────────┘
                    │          │            │
             ┌──────▼──┐  ┌───▼───┐  ┌────▼────┐
             │   MCP   │  │  API  │  │   SDK   │
             │ Server  │  │ (REST)│  │ Py / TS │
             └──────┬──┘  └───┬───┘  └────┬────┘
                    │          │            │
         ┌──────────▼──────────▼────────────▼──────────┐
         │  Cursor / Claude Code / VS Code / Agents /   │
         │         CLI / Web UI / Reports               │
         └──────────────────────────────────────────────┘
```

---

## Core Components

### 1. Architecture Intelligence Graph (ArchGraph)

The central data structure of TrueArch.

**Nodes:**
- Frameworks (LangGraph, CrewAI, LangChain, ADK, MCP, etc.)
- Patterns (RAG, multi-agent, hierarchical, event-driven, etc.)
- Deployment models (serverless, containerized, edge, etc.)
- Compliance requirements (HIPAA, SOC2, GDPR, etc.)

**Edges (relationships):**
- `compatible_with` — frameworks that work well together
- `conflicts_with` — known incompatibilities
- `supersedes` — newer alternatives
- `recommended_for` — problem type mappings
- `production_risk` — risk score based on real-world data

**Evolution:**
- Continuously updated from crawlers, telemetry, and evaluations
- Versioned — historical snapshots preserved for trend analysis

---

### 2. Recommendation Engine

**Input schema:**
```json
{
  "problem_type": "multi-agent | rag | single-agent | data-pipeline | ...",
  "scale": "small | medium | large | enterprise",
  "cloud": "aws | gcp | azure | multi-cloud | on-prem",
  "language": "python | typescript | ...",
  "compliance": ["hipaa", "soc2", "gdpr"],
  "priority": ["latency", "cost", "reliability", "developer_experience"],
  "existing_stack": ["postgresql", "kubernetes"]
}
```

**Output schema:**
```json
{
  "recommended_stack": [...],
  "maturity_scores": {...},
  "tradeoffs": [...],
  "warnings": [...],
  "latest_versions": {...},
  "migration_notes": [...],
  "production_reliability": {...}
}
```

---

### 3. MCP Server (TrueArch MCP)

**Tool definitions:**

```typescript
tools: [
  {
    name: "recommend_ai_stack",
    description: "Get validated AI architecture recommendations for your use case",
    inputSchema: { /* problem description schema */ }
  },
  {
    name: "compare_frameworks",
    description: "Side-by-side comparison of AI frameworks with tradeoffs",
    inputSchema: { frameworks: string[], context: string }
  },
  {
    name: "latest_stable_versions",
    description: "Get current stable versions for AI/ML frameworks",
    inputSchema: { frameworks: string[] }
  },
  {
    name: "architecture_tradeoffs",
    description: "Analyze tradeoffs between architectural options for a specific problem",
    inputSchema: { options: string[], constraints: object }
  },
  {
    name: "validate_agent_architecture",
    description: "Check if a proposed architecture is production-ready",
    inputSchema: { architecture: object }
  },
  {
    name: "ecosystem_pulse",
    description: "Get latest ecosystem signals: adoption trends, deprecations, security issues",
    inputSchema: { frameworks: string[] }
  }
]
```

**Transport:** stdio (Phase 1), HTTP/SSE (Phase 2)  
**Hosting:** Initially lightweight, serverless-friendly  
**Model-agnostic:** Works with Claude, GPT-4o, Gemini, local models

---

### 4. REST API

**Base URL:** `https://api.truearch.ai/v1`

**Core endpoints:**

```
POST /recommend-stack          → Stack recommendation
POST /compare-frameworks       → Framework comparison
POST /validate-architecture    → Architecture validation
GET  /frameworks/{id}          → Framework detail + maturity
GET  /frameworks/{id}/versions → Version history
POST /tradeoffs                → Tradeoff analysis
GET  /ecosystem-pulse          → Latest ecosystem signals
GET  /benchmarks               → Public benchmark data
```

**Authentication:** API key (Phase 1), OAuth (Phase 2)  
**Rate limiting:** Free tier + paid tiers  
**Response format:** Structured JSON, always versioned

---

### 5. Context Compression Layer (TrueContext)

**Purpose:** Do NOT inject 50,000 tokens of framework documentation into an agent's context. Inject only what's architecturally critical for the current decision.

**How it works:**
1. Analyzes the agent's current task context
2. Identifies the architecture decision points
3. Extracts *only* the relevant intelligence
4. Compresses into minimal, structured context

**Why this matters:**
- Reduces token cost dramatically
- Improves reasoning quality (less noise)
- Enables faster agent cycles

---

## Integration Architecture

### Integration Priority

| Priority | Integration | Value | Effort |
|---|---|---|---|
| P0 | MCP Server | Universal agent protocol | Medium |
| P0 | REST API | Core intelligence access | Low |
| P1 | Cursor | Highest developer density | Medium |
| P1 | Claude Code | Anthropic ecosystem | Medium |
| P2 | VS Code Extension | Long-tail reach | Medium |
| P2 | Python SDK | Data/ML engineer reach | Low |
| P2 | TypeScript SDK | JS/TS developer reach | Low |
| P3 | GitHub Copilot | Enterprise developer reach | High |
| P3 | CLI | Terminal-native developers | Low |

### MCP Integration Architecture

```
Developer in Cursor
        ↓
Cursor MCP client
        ↓
TrueArch MCP Server (stdio / HTTP)
        ↓
Context Compression Layer
        ↓
Recommendation Engine
        ↓
Structured response injected back into Cursor
```

**No context switching. No new dashboard. No friction.**

---

## Cost Architecture

### Phase 1 Cost Strategy

| Layer | Strategy | Cost Impact |
|---|---|---|
| **Framework database** | Manual curation (top 20–30 frameworks) | ~$0 |
| **Recommendation engine** | Small model (GPT-4o-mini, Claude Haiku) for most queries | Very low |
| **Complex tradeoffs** | Frontier model only for ambiguous reasoning | Controlled |
| **Caching** | 24-48h cache on framework comparisons, stack recs | -80% compute |
| **Hosting** | Serverless (Vercel/Railway/Fly.io) | ~$20-100/month |
| **Crawlers** | Not yet — manual updates Phase 1 | $0 |

### Phase 1 Target: <$200/month operational cost

---

## Data Architecture

### What We Store

**Phase 1 (Manual):**
- Framework metadata (name, version, maturity, license)
- Architecture patterns (multi-agent, RAG, orchestration, etc.)
- Known incompatibilities and warnings
- Production reliability notes (curated from community)

**Phase 2 (Semi-automated):**
- GitHub metrics (stars, issues, PR velocity)
- Release history
- Security advisory tracking
- Community adoption signals

**Phase 3 (Automated + Telemetry):**
- Anonymized architecture outcomes
- Benchmark results
- Migration success rates
- Production failure patterns

### Storage Stack (Phase 1)

```
PostgreSQL          → Structured framework data, recommendations
Redis               → Caching layer (24-48h TTL)
Vector DB           → Semantic search over architecture patterns (Pgvector or Qdrant)
Object Storage      → Benchmark reports, research artifacts
```

---

## Technical Principles

1. **API-first** — Design API before UI
2. **Model-agnostic** — Never hardcode a provider
3. **Cache everything** — Recommendations don't change hourly
4. **Structured outputs** — JSON/YAML, not prose
5. **Fail safely** — Degrade gracefully if unavailable
6. **Small models first** — Scale up model size only when needed
7. **Privacy-first telemetry** — Opt-in only, anonymized always

---

*Last updated: 2026-05-16*
