# TrueArch — Architecture Genome Taxonomy

> **Status:** v1.0 — Finalized design. Do not change dimensions without a Decision Log entry.
>
> **What this is:** The complete specification for the Architecture Genome — the structured
> fingerprint assigned to every AI system. Every recommendation, ADR, ArchGraph node, and
> benchmark is keyed to a Genome. Getting this right unblocks everything.
>
> **Decision log reference:** DL-010 (Genome dimensions), DL-011 (encoding format)

---

## Overview

The Architecture Genome is a compact, structured code that **fully describes the architectural
DNA** of an AI system in a machine-readable and human-readable format.

### Two Forms

**Short Genome (7 core dimensions — always present):**
```
MA-STAT-HOR-HIPAA-PY-MCP-REDIS
```

**Full Genome (all 10 dimensions — used in detailed analysis):**
```
MA-STAT-HOR-HIPAA-PY-MCP-REDIS+LGR+OTEL+CONT
```

The `+` separator marks the extended dimensions (8–10), which are optional at query time
but always populated in stored lineage records.

---

## Encoding Format

```
[D1]-[D2]-[D3]-[D4]-[D5]-[D6]-[D7]+[D8]+[D9]+[D10]
  │    │    │    │    │    │    │     │    │    │
  │    │    │    │    │    │    │     │    │    └── D10: Deployment Model
  │    │    │    │    │    │    │     │    └─────── D9:  Observability
  │    │    │    │    │    │    │     └──────────── D8:  Orchestrator
  │    │    │    │    │    │    └────────────────── D7:  Memory Layer
  │    │    │    │    │    └─────────────────────── D6:  Agent Protocol
  │    │    │    │    └──────────────────────────── D5:  Primary Language
  │    │    │    └───────────────────────────────── D4:  Compliance
  │    │    └────────────────────────────────────── D3:  Scaling Model
  │    └─────────────────────────────────────────── D2:  Memory Strategy
  └──────────────────────────────────────────────── D1:  Architectural Pattern
```

### Wildcard for Search
Use `*` in any dimension to match all values:
```
MA-*-*-HIPAA-PY-*-*    →  all multi-agent Python HIPAA architectures
*-STAT-*-*-*-MCP-*     →  all stateful MCP-based architectures
```

---

## Dimension 1 — Architectural Pattern (D1)

> The primary design pattern of the system.

| Code | Pattern | Description |
|---|---|---|
| `MA` | Multi-Agent | Multiple specialized agents collaborating on tasks |
| `SA` | Single-Agent | One agent with tool use (LLM + tools) |
| `RAG` | Retrieval-Augmented Generation | Query → retrieve docs → generate answer |
| `PIPE` | AI Pipeline | Sequential data processing with AI steps |
| `WF` | Workflow Automation | Deterministic workflows with AI decision nodes |
| `HYB` | Hybrid | Combination of 2+ patterns (specify in lineage notes) |
| `SIM` | Simulation/Evaluation | AI systems designed to simulate or evaluate other AI |

**Examples:**
- Customer support bot with multiple specialized sub-agents → `MA`
- Document Q&A system → `RAG`
- ETL pipeline with AI enrichment steps → `PIPE`
- Business process automation with occasional LLM decision gates → `WF`

---

## Dimension 2 — Memory Strategy (D2)

> How the system stores and accesses state across interactions.

| Code | Strategy | Description |
|---|---|---|
| `STAT` | Stateful | Persistent state maintained across sessions (long-term memory) |
| `SESS` | Session-Stateful | State maintained within a session, cleared after |
| `SLESS` | Stateless | No state persistence; each call is independent |
| `HYB` | Hybrid | Mix of stateful and stateless components |

**Guidance:**
- Production enterprise systems: usually `STAT` or `SESS`
- Simple Q&A, batch jobs: `SLESS`
- Conversational + background jobs: `HYB`

---

## Dimension 3 — Scaling Model (D3)

> The primary mechanism by which the system scales under load.

| Code | Model | Description |
|---|---|---|
| `HOR` | Horizontal | Scale by adding more instances (k8s, container replicas) |
| `VER` | Vertical | Scale by increasing instance size (bigger machines) |
| `SLS` | Serverless | Auto-scaling via function invocations (Lambda, Cloud Run) |
| `EDG` | Edge | Deployed at edge nodes (Cloudflare Workers, Fly.io regions) |
| `HYB` | Hybrid | Multiple scaling strategies for different components |

**Guidance:**
- Most production AI systems: `HOR`
- Low-traffic internal tools: `VER` or `SLS`
- Latency-critical global APIs: `EDG`

---

## Dimension 4 — Compliance Requirements (D4)

> Regulatory or compliance constraints the system must satisfy.

| Code | Standard | Domain |
|---|---|---|
| `NONE` | No compliance | General/unrestricted |
| `HIPAA` | HIPAA | US Healthcare |
| `SOC2` | SOC 2 Type II | SaaS/enterprise security |
| `GDPR` | GDPR | European personal data |
| `FIN` | FINRA / SOX / PCI | Financial services |
| `FEDRAMP` | FedRAMP | US Federal government |
| `MULT` | Multiple | Two or more of the above (specify in lineage notes) |

**Important:** Compliance is a hard constraint — it eliminates entire framework options.
A `HIPAA` system cannot use a memory store with unencrypted persistence, for example.
TrueArch uses D4 as the first filter in the recommendation pipeline.

---

## Dimension 5 — Primary Language (D5)

> The primary programming language of the system.

| Code | Language |
|---|---|
| `PY` | Python |
| `TS` | TypeScript / JavaScript |
| `GO` | Go |
| `JAVA` | Java / Kotlin |
| `RS` | Rust |
| `MULTI` | Polyglot (2+ languages, specify primary in notes) |

**Guidance:**
- AI/ML workloads: almost always `PY`
- High-performance APIs, edge: often `TS` or `GO`
- Enterprise Java shops adopting AI: `JAVA`

---

## Dimension 6 — Agent Communication Protocol (D6)

> The protocol used for agent-to-tool or agent-to-agent communication.

| Code | Protocol | Description |
|---|---|---|
| `MCP` | Model Context Protocol | Anthropic/OpenAI standard for agent-tool communication |
| `A2A` | Agent-to-Agent (Google) | Google's A2A protocol for inter-agent communication |
| `REST` | REST API | Standard HTTP/REST for tool integration |
| `GRPC` | gRPC | High-performance RPC for agent communication |
| `WS` | WebSocket | Real-time bidirectional agent communication |
| `CUST` | Custom | Proprietary or framework-specific protocol |
| `NONE` | None | No formal protocol; direct function calls |

**Guidance:**
- New AI projects in 2026+: prefer `MCP` (rapidly becoming standard)
- Enterprise with existing API infrastructure: `REST`
- High-throughput real-time: `WS` or `GRPC`
- Pure LangGraph/CrewAI internal: `NONE` (internal graph communication)

---

## Dimension 7 — Primary Memory/Storage Layer (D7)

> The primary data store used for agent memory, session state, or vector retrieval.

| Code | Technology | Type |
|---|---|---|
| `REDIS` | Redis | In-memory key-value + sessions |
| `PG` | PostgreSQL | Relational + pgvector extension |
| `MONGO` | MongoDB | Document store |
| `PIN` | Pinecone | Managed vector database |
| `QDRANT` | Qdrant | Open-source vector database |
| `CHROMA` | Chroma | Lightweight embedded vector store |
| `WEAVIATE` | Weaviate | Graph + vector database |
| `SUPABASE` | Supabase | PostgreSQL + vector + realtime |
| `MEM` | In-memory | No persistence (ephemeral runtime only) |
| `NONE` | None | Stateless — no memory layer |

**Guidance:**
- Sub-millisecond session access: `REDIS`
- Semantic search + SQL hybrid: `PG` with pgvector
- Pure vector search at scale: `PIN` or `QDRANT`
- Prototyping / small teams: `CHROMA`
- HIPAA compliance with managed service: `PG` (RDS) or `SUPABASE`

---

## Dimension 8 — Orchestration Framework (D8) `[Extended]`

> The primary framework managing agent orchestration and workflow.

| Code | Framework | Notes |
|---|---|---|
| `LGR` | LangGraph | Graph-based stateful agent orchestration (Recommended 2026) |
| `CREW` | CrewAI | Role-based multi-agent collaboration |
| `AUTOG` | AutoGen | Microsoft's conversational agent framework |
| `ADK` | Google ADK | Google's Agent Development Kit |
| `PYDAI` | Pydantic AI | Type-safe agent framework |
| `LANG` | LangChain | Original LangChain (without LangGraph) |
| `LLMIND` | LlamaIndex | Data-centric agent/RAG framework |
| `CUST` | Custom | Hand-rolled orchestration |
| `NONE` | None | Direct LLM API calls, no orchestration framework |

---

## Dimension 9 — Observability (D9) `[Extended]`

> The observability and monitoring approach.

| Code | Approach | Description |
|---|---|---|
| `OTEL` | OpenTelemetry | Full distributed tracing (recommended) |
| `LSMITH` | LangSmith | LangChain-native tracing and evaluation |
| `HELIC` | Helicone | LLM-specific observability |
| `PROM` | Prometheus + Grafana | Metrics-focused monitoring |
| `DD` | Datadog | Full-stack observability (enterprise) |
| `BASIC` | Basic logging | stdout/stderr logs only |
| `NONE` | None | No observability (flagged as risk in TrueArch) |

**Risk flag:** `NONE` always triggers a governance warning in TrueArch recommendations.
Production systems without observability are flagged as high architectural debt.

---

## Dimension 10 — Deployment Model (D10) `[Extended]`

> Where and how the system is deployed.

| Code | Model | Examples |
|---|---|---|
| `CONT` | Containerized | Docker + Kubernetes, ECS, Cloud Run |
| `SLS` | Serverless | AWS Lambda, Google Cloud Functions, Modal |
| `MANAGED` | Managed PaaS | Railway, Render, Heroku, App Engine |
| `EDGE` | Edge | Cloudflare Workers, Fly.io, Vercel Edge |
| `ON_PREM` | On-premises | Self-hosted, air-gapped environments |
| `HYB` | Hybrid | Mix of cloud + on-prem |

---

## Genome Examples

### Example 1 — Enterprise Multi-Agent Support Platform
```
System: Healthcare customer support, 5M users, AWS, Python, HIPAA
Genome: MA-STAT-HOR-HIPAA-PY-MCP-REDIS+LGR+OTEL+CONT

Reading:
  MA      → Multi-agent pattern
  STAT    → Stateful (session memory persisted)
  HOR     → Horizontal scaling (K8s on EKS)
  HIPAA   → Healthcare compliance required
  PY      → Python
  MCP     → Model Context Protocol for tool integration
  REDIS   → Redis for session/agent memory
  +LGR    → LangGraph orchestration
  +OTEL   → OpenTelemetry observability
  +CONT   → Containerized deployment
```

### Example 2 — Lightweight RAG Chatbot
```
System: Internal company knowledge base Q&A, startup, 50 users
Genome: RAG-SLESS-SLS-NONE-PY-REST-CHROMA+LANG+BASIC+SLS

Reading:
  RAG     → Retrieval-Augmented Generation
  SLESS   → Stateless (no cross-session memory)
  SLS     → Serverless scaling
  NONE    → No compliance requirements
  PY      → Python
  REST    → REST API for tool calls
  CHROMA  → Chroma vector store (local)
  +LANG   → LangChain (basic RAG chain)
  +BASIC  → Basic logging
  +SLS    → Serverless deployment (Modal)
```

### Example 3 — Financial Workflow Automation
```
System: Automated loan processing pipeline, bank, Python, SOC2+PCI
Genome: WF-STAT-HOR-FIN-PY-REST-PG+LGR+OTEL+ON_PREM

Reading:
  WF      → Workflow automation (deterministic steps + AI gates)
  STAT    → Stateful (loan application state persisted)
  HOR     → Horizontal scaling
  FIN     → Financial compliance (FINRA/SOX/PCI)
  PY      → Python
  REST    → REST API integration
  PG      → PostgreSQL (audit trail, compliance-ready)
  +LGR    → LangGraph for workflow orchestration
  +OTEL   → Full distributed tracing
  +ON_PREM→ On-premises (data sovereignty requirement)
```

### Example 4 — Agentic Code Assistant
```
System: AI pair programmer, SaaS product, TypeScript, SOC2
Genome: SA-SESS-SLS-SOC2-TS-MCP-REDIS+CUST+LSMITH+CONT

Reading:
  SA      → Single-agent (one primary assistant agent)
  SESS    → Session-stateful (clears after conversation ends)
  SLS     → Serverless
  SOC2    → SOC2 compliance
  TS      → TypeScript
  MCP     → MCP for IDE tool integration (Cursor/VS Code)
  REDIS   → Redis for session state
  +CUST   → Custom orchestration (no framework)
  +LSMITH → LangSmith for tracing
  +CONT   → Containerized
```

---

## Genome Operations

### Genome Comparison (Similarity Score)
Two Genomes are compared dimension by dimension:

```python
# Pseudocode — exact implementation in ARCHITECTURE.md
def genome_similarity(g1: str, g2: str) -> float:
    dims1 = parse_genome(g1)  # returns dict of {dimension: value}
    dims2 = parse_genome(g2)

    # Core dimensions (D1-D7) weighted higher than extended
    weights = {
        'D1': 0.25,  # Pattern — most important
        'D2': 0.15,  # Memory Strategy
        'D3': 0.10,  # Scaling
        'D4': 0.20,  # Compliance — hard constraint, mismatch = 0
        'D5': 0.10,  # Language
        'D6': 0.10,  # Protocol
        'D7': 0.10,  # Memory Layer
    }

    score = 0.0
    for dim, weight in weights.items():
        if dims1[dim] == dims2[dim]:
            score += weight
        elif dims1[dim] == '*' or dims2[dim] == '*':
            score += weight  # wildcard matches all
        # Compliance mismatch = hard 0 for that dimension

    return score  # 0.0 to 1.0
```

### Genome Search (ArchGraph Query)
```
Query: "Find all successful deployments similar to MA-*-HOR-HIPAA-PY-*-*"
→ Returns: all lineage records where D1=MA AND D3=HOR AND D4=HIPAA AND D5=PY
→ Ranked by: outcome success_rate × confidence × recency
```

### Genome Evolution (Drift Detection)
```
Original Genome: MA-STAT-HOR-HIPAA-PY-MCP-REDIS
Current Genome:  MA-STAT-HOR-HIPAA-PY-MCP-PG
Drift detected:  D7 changed (REDIS → PG)
Severity:        MEDIUM (latency regression risk)
```

---

## Genome Schema (Storage)

```yaml
genome:
  short: "MA-STAT-HOR-HIPAA-PY-MCP-REDIS"
  full:  "MA-STAT-HOR-HIPAA-PY-MCP-REDIS+LGR+OTEL+CONT"
  dimensions:
    D1_pattern:     "MA"
    D2_memory:      "STAT"
    D3_scaling:     "HOR"
    D4_compliance:  "HIPAA"
    D5_language:    "PY"
    D6_protocol:    "MCP"
    D7_store:       "REDIS"
    D8_orchestrator: "LGR"
    D9_observability: "OTEL"
    D10_deployment: "CONT"
  version: "1.0"
  generated_at: "2026-05-16"
  notes: "MULT compliance: also SOC2 — see lineage notes"
```

---

## Genome Version Policy

When a new framework, protocol, or pattern becomes significant enough to warrant a new code
value, a new Genome version is issued:

- **Patch (1.0.x):** Adding new `Code` values to existing dimensions
- **Minor (1.x.0):** Adding a new dimension
- **Major (x.0.0):** Restructuring existing dimensions (rare — avoid; breaks search)

All stored Genomes are stamped with the taxonomy version they were generated under.
The ArchGraph handles cross-version Genome comparison with a compatibility matrix.

---

## Open Source Release Plan

The Genome taxonomy schema will be open-sourced as a standalone spec:
- **Repository:** `github.com/TrueArchAI/genome-spec`
- **License:** Apache 2.0
- **Format:** YAML schema + JSON Schema for validation
- **Goal:** Become the industry-standard vocabulary for AI architecture description

This is how TrueArch owns the vocabulary before owning the intelligence.

---

## Decision Logs

### DL-010 — GitHub Organization Name
- **Decision:** `TrueArchAI` (github.com/TrueArchAI)
- **Context:** `TrueArch` was not available
- **Rationale:** `TrueArchAI` clearly signals the AI-native category; acceptable alternative
- **Impact:** All open-source repos, SDK package names, npm/PyPI namespaces use `truearchai`
- **Date:** 2026-05-16

### DL-011 — Genome Dimensions (10 total, 7 core + 3 extended)
- **Decision:** 10 dimensions; D1–D7 always required; D8–D10 extended (optional in queries, required in storage)
- **Rationale:** 7 core dimensions capture the vast majority of architectural differentiation. Extended dimensions add precision without requiring them at query time. `+` separator keeps encoding readable.
- **Alternatives Rejected:**
  - 5 dimensions: Too coarse — loses compliance and protocol specificity
  - 12+ dimensions: Too many to be human-readable or quickly comprehensible
  - Flat tag system (no positional encoding): Loses comparability and search efficiency
- **Date:** 2026-05-16

### DL-012 — Wildcard Pattern (`*`) for Genome Search
- **Decision:** Use `*` for any unspecified dimension in search queries
- **Rationale:** Enables fuzzy matching without requiring full specification. Compliance dimension (`D4`) is never wildcarded in production searches — it's a hard filter.
- **Date:** 2026-05-16

### DL-013 — Open Source Genome Spec Repository
- **Decision:** Open source the Genome schema at `github.com/TrueArchAI/genome-spec` under Apache 2.0
- **Rationale:** Vocabulary ownership > feature ownership. If TrueArch defines the standard language for describing AI architectures, every tool that adopts it drives adoption back to TrueArch.
- **Date:** 2026-05-16

---

*Last updated: 2026-05-16 v1.0 | Taxonomy version must be updated for any dimension changes.*
