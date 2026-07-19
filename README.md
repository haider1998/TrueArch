---
title: TrueArch MCP
emoji: 🏛️
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
short_description: The hallucination killer for AI coding agents (MCP server)
---

# TrueArch

> **The hallucination killer for AI coding agents.**
> Real versions, real APIs, and validated code patterns for 38 AI frameworks — served over MCP to Claude Code, Cursor, Copilot, Antigravity, Windsurf, and Zed.

---

## Why

Your coding agent was trained on a snapshot of the world. So every day it:

- writes `pinecone.init(...)` — **removed in Pinecone v3**
- imports `from langchain.chat_models import ChatOpenAI` — **moved to `langchain_openai` in v0.2**
- pins `weaviate.Client(url)` — **the v4 client is a complete rewrite**
- recommends AutoGen with the `from autogen import AssistantAgent` API — **that flat API is v0.2; v0.4 is a different package**

These aren't reasoning failures — they're **stale-knowledge failures**, and a smarter model doesn't fix them. TrueArch does: it gives the agent a live, curated ground truth *at generation time*, then checks the code it produced.

TrueArch runs on the loop you hit every session:

1. **`quick_context`** — a token-cheap, intent-aware brief before the agent designs anything.
2. **`latest_stable_versions`** — real pinned versions for your lockfile, not hallucinated ones.
3. **`validate_code`** — scan the generated code for deprecated APIs and get the exact fix back.

Architecture recommendations, ADRs, and the Architecture Genome are still here — as the depth layer for when you're standing up a *new* system, not writing the next line.

---

## Install in 60 seconds

TrueArch ships as an MCP server. Two ways to connect:

### Option A — zero install (hosted)
Point your client at the hosted endpoint (no clone, no Python):

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

- **Claude Code:** add the block above to `claude_desktop_config.json`.
- **Cursor:** add it to `.cursor/mcp.json`.
- **VS Code / Windsurf / Zed / Antigravity / Continue:** ready-made configs in [`mcp-configs/`](./mcp-configs).

### Option B — run it locally (`uvx`, no clone)

```bash
# Claude Code, one line:
claude mcp add truearch -- uvx truearch-mcp
```

or, for any client, add a stdio server:

```json
{
  "mcpServers": {
    "truearch": { "command": "uvx", "args": ["truearch-mcp"] }
  }
}
```

Telemetry (if you enable it) stays **local-only** — raw queries are never stored, only a hash.

Then ask your agent:
> *"Before you write this, use TrueArch to pin the versions and validate the code."*

---

## The daily loop

**1. Catch the hallucination.** Your agent just wrote v2 Pinecone code:

```python
validate_code(
  code="import pinecone\npinecone.init(api_key='x')",
  framework_id="pinecone",
)
```
```json
{
  "verdict": "critical",
  "violations": [{
    "pattern_id": "PCN-001",
    "severity": "critical",
    "matched_text": "pinecone.init(",
    "correct_example": "from pinecone import Pinecone\npc = Pinecone(api_key='x')",
    "description": "pinecone.init() was removed in Pinecone v3. Use the Pinecone() class constructor.",
    "docs_url": "https://docs.pinecone.io/guides/getting-started/migration-guide"
  }]
}
```

Pass `version="2.2.4"` and TrueArch stays quiet — on that release `init()` is still valid. It's version-aware, not just pattern-matching.

**2. Pin the real versions.**

```python
latest_stable_versions(framework_ids=["langgraph", "anthropic_sdk"])
# → exact stable versions + data_age_days, with a staleness warning if the data is old
```

**3. Ground the design** with `quick_context` — a budgeted brief that classifies your intent, surfaces the relevant known-issues first, and tags every data point verified/estimated.

**Covered for code validation (15 frameworks, growing):** Pinecone, LangChain, LangGraph, LlamaIndex, Qdrant, Weaviate, Chroma, OpenAI SDK, Anthropic SDK, AutoGen, CrewAI, PydanticAI, FastAPI, Supabase, Ollama. Unsupported frameworks return an honest `"unchecked"` verdict rather than a false pass.

---

## Does it actually help? (honest numbers)

We ran 15 architecture scenarios through Gemini 2.5 Flash, with and without TrueArch context ([full results + methodology](./benchmark/evaluation_results.md)):

| Signal | Baseline | With TrueArch |
|---|---|---|
| **Deterministic fact-checks** (objective) | 24/30 | **30/30** |
| Judge quality score (subjective, avg/10) | 6.2 | 7.2 |
| Token overhead | — | +44% total tokens |

The load-bearing result is the deterministic one: **TrueArch eliminated all 6 factual misses** — deprecated APIs, stale versions, and maintenance-mode recommendations. The quality delta is a *same-model-judged, single-run, N=15* estimate — directional, not a benchmark score. We spell out every caveat in the results file rather than lead with the rosy number.

---

## Freshness is a feature, not a promise

Stale data is the failure mode TrueArch exists to prevent, so it never hides its own age:

- Every score's confidence **decays** with the age of its underlying signals.
- `latest_stable_versions` and `get_framework_score` return a **staleness warning** when data is old — computed from the real curation/signal dates, not reset on restart.
- A **nightly GitHub Action** crawls GitHub + PyPI/npm, applies only objective fields (versions, release dates, stars), and opens a **PR for human review** — subjective judgements are never auto-overwritten.

---

## Depth layer — for new systems

When you're architecting from scratch, not writing a line:

| Tool | Purpose |
|---|---|
| `recommend_ai_stack` | Full multi-layer recommendation + Architecture Genome + ADR |
| `compare_frameworks` | Head-to-head across 5 scoring dimensions |
| `get_framework_score` | Single-framework TrueArch score + staleness |
| `get_recommendation` | Top-N frameworks in a category |
| `architecture_tradeoffs` | Known issues, compatibility, migration paths |
| `get_code_patterns` | Version-pinned, validated code snippets |
| `generate_adr` | Committable Markdown Architecture Decision Record |
| `explain_score` | Per-dimension breakdown with raw signals |
| `genome_compare` | Similarity between two Architecture Genomes |
| `get_telemetry_insights` | Local, privacy-preserving usage insights |

Every framework is scored on: Production Stability · Ecosystem Momentum · Migration Risk · Governance Readiness · Agent Compatibility.

### Architecture Genome™

Each recommendation carries a Genome — the architectural DNA of the decision, e.g. `MA-STAT-HOR-HIPAA-PY-MCP-REDIS+LGR+OTEL+CONT`. Genomes are searchable, comparable, and shareable, so teams with matching Genomes can reuse each other's ADRs. See [GENOME_TAXONOMY.md](./GENOME_TAXONOMY.md).

---

## Framework coverage

**38 curated frameworks** across orchestration, vector DBs, observability, API, database, safety, protocol, and deployment — including LangGraph, CrewAI, AutoGen, PydanticAI, Google ADK, Qdrant, Pinecone, Weaviate, Chroma, Milvus, OpenAI SDK, Anthropic SDK, Ollama, FastAPI, Supabase, and the Vercel AI SDK.

---

## Run from a checkout

```bash
git clone https://github.com/TrueArchAI/TrueArch.git
cd TrueArch
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

pytest tests/            # 535 passing
python -m src.mcp.server            # stdio (IDE integration)
PORT=7860 python -m src.mcp.server --http   # HTTP: /health and /mcp
uvicorn src.api.main:app --reload   # optional REST API at /docs
```

To refresh the catalog: `python -m scripts.signal_pipeline.pipeline` then `python -m scripts.signal_pipeline.apply_patch` (see [Freshness](#freshness-is-a-feature-not-a-promise)).

---

## Core documents

| Document | Purpose |
|---|---|
| [benchmark/evaluation_results.md](./benchmark/evaluation_results.md) | A/B evaluation + methodology & limitations |
| [FOUNDATION.md](./FOUNDATION.md) | Vision and strategy |
| [SCORING_FORMULA.md](./SCORING_FORMULA.md) | How scores are calculated |
| [GENOME_TAXONOMY.md](./GENOME_TAXONOMY.md) | Architecture Genome™ dimensions |
| [mcp-configs/README.md](./mcp-configs/README.md) | Per-client MCP setup |

---

*TrueArch — real versions, real APIs, validated code. So your agent stops shipping 2023.*
