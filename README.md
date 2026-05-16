# TrueArch

> **Architecture intelligence layer for AI-native engineering.**  
> Deterministic. Scored. Auditable. Shared across every AI agent that uses it.

---

## The Problem TrueArch Solves

Every time a developer asks Claude Code, Cursor, or Codex to architect an AI system, the AI:
- Re-derives framework knowledge from scratch (wastes 500–2000 tokens)
- Hallucinates version numbers
- Gives a different answer than the colleague who asked 5 minutes ago

TrueArch is the **shared pre-computation layer** — architectural intelligence computed once, curated by humans, and served deterministically to every AI agent that asks.

---

## Connect in 30 Seconds

### Cursor
Add to `.cursor/mcp.json` in your project:
```json
{
  "mcpServers": {
    "truearch": {
      "url": "https://smhrizvi281-truearch-mcp.hf.space/mcp"
    }
  }
}
```

### Claude Code
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "truearch": {
      "type": "http",
      "url": "https://smhrizvi281-truearch-mcp.hf.space/mcp"
    }
  }
}
```

Then ask your AI agent:
> *"Use TrueArch to recommend a stack for a multi-agent HIPAA patient support platform in Python"*

---

## What You Get Back

```yaml
# Example output from recommend_ai_stack()

orchestration:
  framework: LangGraph
  version: "0.4.1"
  score: 84/100
  confidence: 81%
  reason: "Stateful graph-based orchestration with native HIPAA-compatible patterns"

vector_db:
  framework: Qdrant
  score: 87/100
  reason: "Production-stable, self-hostable (HIPAA data residency)"

observability:
  framework: OpenTelemetry
  reason: "Vendor-neutral audit trail — required for HIPAA compliance"

genome: "MA-STAT-HOR-HIPAA-PY-MCP-REDIS"
confidence: 81%
score_band: "Strong"
review_by: "2027-05-17"
adr: "[committable Markdown ADR included]"

warnings:
  - "CrewAI not recommended for HIPAA: unresolved memory persistence issues"
  - "AutoGen adds latency overhead — evaluate carefully for real-time use cases"
```

---

## MCP Tools Available

| Tool | Purpose |
|---|---|
| `recommend_ai_stack` | Full multi-layer recommendation + Genome + ADR |
| `compare_frameworks` | Head-to-head across 5 scoring dimensions |
| `get_framework_score` | Single framework TrueArch score + staleness |
| `get_recommendation` | Top-N frameworks in a category |
| `latest_stable_versions` | Pinned, verified versions for lockfiles |
| `architecture_tradeoffs` | Known issues, compatibility, migration paths |

---

## REST API

The REST API runs separately for direct HTTP access:

```bash
# Start the REST API
uvicorn src.api.main:app --reload

# Example: Stack recommendation
curl -X POST http://localhost:8000/api/v1/recommend/stack \
  -H "Content-Type: application/json" \
  -d '{"problem": "HIPAA multi-agent patient platform", "compliance": ["hipaa"]}'

# Example: Generate an ADR
curl -X POST http://localhost:8000/api/v1/recommend/stack/adr \
  -d '{"query": {"problem": "Multi-agent support platform"}, "adr_number": 1}'

# Example: Compare two frameworks
curl http://localhost:8000/api/v1/compare/langgraph/crewai

# Swagger UI
open http://localhost:8000/docs
```

---

## Run Locally

```bash
# 1. Clone and install
git clone https://github.com/TrueArchAI/TrueArch.git
cd TrueArch
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Run test suite
pytest tests/ -v
# Expected: 126 passed

# 3a. Run the MCP server (stdio — for IDE integration)
python -m src.mcp.server

# 3b. Run the MCP server (HTTP — for testing the deployed mode)
PORT=7860 python -m src.mcp.server --http
# → http://localhost:7860/health
# → http://localhost:7860/mcp  (MCP endpoint)

# 4. Run the REST API
uvicorn src.api.main:app --reload
# → http://localhost:8000/docs
```

---

## Architecture Genome™

Every recommendation includes a Genome — the architectural DNA of the decision:

```
MA  - STAT - HOR  - HIPAA - PY  - MCP  - REDIS + LGR + OTEL + CONT
D1    D2     D3     D4      D5    D6     D7      D8    D9     D10
│     │      │      │       │     │      │       │     │      │
│     │      │      │       │     │      │       │     │      └─ Deployment
│     │      │      │       │     │      │       │     └─ Observability
│     │      │      │       │     │      │       └─ Orchestrator
│     │      │      │       │     │      └─ Primary Store
│     │      │      │       │     └─ Agent Protocol
│     │      │      │       └─ Language
│     │      │      └─ Compliance
│     │      └─ Scaling Strategy
│     └─ Memory Strategy
└─ Architectural Pattern
```

Genomes are searchable, comparable, and shareable. Teams with matching Genomes can reuse each other's ADRs.

---

## Framework Coverage

28 curated frameworks across 8 categories:

| Category | Examples |
|---|---|
| Orchestration | LangGraph, CrewAI, Google ADK, AutoGen, Pydantic AI, SmolAgents, DSPy |
| Vector DB | Qdrant, Pinecone, Weaviate, Chroma, pgvector |
| Observability | OpenTelemetry, LangSmith, Helicone, Arize AI |
| API Layer | FastAPI |
| Database | PostgreSQL, Redis, MongoDB, Supabase |
| Safety | Guardrails AI, LlamaGuard |
| Protocol | MCP SDK, Google A2A |
| Deployment | Fly.io, Modal |

All frameworks scored on: Production Stability · Ecosystem Momentum · Migration Risk · Governance Readiness · Agent Compatibility

---

## Deploying Your Own Instance

Hugging Face Spaces provides **100% free** Docker hosting specifically designed for AI projects, with no credit card required.

```bash
# 1. Create a new Space on Hugging Face (https://huggingface.co/spaces)
#    Choose: Docker > Blank

# 2. Add Hugging Face as a git remote
git remote add hf https://huggingface.co/spaces/smhrizvi281/truearch-mcp

# 3. Push the code
git push hf main
```

The deployed server will be available at `https://smhrizvi281-truearch-mcp.hf.space/mcp`.

---

## Core Documents

| Document | Purpose |
|---|---|
| [FOUNDATION.md](./FOUNDATION.md) | Vision, strategy, AI-readable context |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Technical architecture and API design |
| [GENOME_TAXONOMY.md](./GENOME_TAXONOMY.md) | Architecture Genome™ dimension definitions |
| [SCORING_FORMULA.md](./SCORING_FORMULA.md) | How TrueArch scores are calculated |
| [ROADMAP.md](./ROADMAP.md) | Phase-by-phase product roadmap |
| [mcp-configs/README.md](./mcp-configs/README.md) | MCP client setup guide |

---

> *"Every AI coding agent should query TrueArch before generating production architecture."*

---

*TrueArch — Decision Infrastructure for AI-Native Engineering*