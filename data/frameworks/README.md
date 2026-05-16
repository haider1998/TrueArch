# Framework Database — Curation Guide

> These YAML files are the seed data for the TrueArch recommendation engine.
> Quality here directly determines recommendation quality at launch.
> **Never publish a recommendation based on unvalidated framework data.**

## Curation Status

| Framework | File | Category | Status | Last Validated |
|---|---|---|---|---|
| LangGraph | `langgraph.yaml` | Orchestration | ✅ Curated | 2026-05-16 |
| CrewAI | `crewai.yaml` | Orchestration | ✅ Curated | 2026-05-16 |
| LangChain | `langchain.yaml` | Orchestration | ✅ Curated | 2026-05-16 |
| AutoGen | `autogen.yaml` | Orchestration | ✅ Curated | 2026-05-16 |
| Google ADK | `google_adk.yaml` | Orchestration | ✅ Curated | 2026-05-16 |
| Pydantic AI | `pydantic_ai.yaml` | Orchestration | ✅ Curated | 2026-05-16 |
| LlamaIndex | `llamaindex.yaml` | RAG | ✅ Curated | 2026-05-16 |
| FastAPI | `fastapi.yaml` | API | ✅ Curated | 2026-05-16 |
| Qdrant | `qdrant.yaml` | Vector DB | ✅ Curated | 2026-05-16 |
| Redis | `redis.yaml` | Memory Layer | ✅ Curated | 2026-05-16 |
| OpenTelemetry | `opentelemetry.yaml` | Observability | ✅ Curated | 2026-05-16 |
| Pinecone | `pinecone.yaml` | Vector DB | ✅ Curated | 2026-05-16 |
| Chroma | `chroma.yaml` | Vector DB | ✅ Curated | 2026-05-16 |
| Weaviate | `weaviate.yaml` | Vector DB | ✅ Curated | 2026-05-16 |
| PostgreSQL+pgvector | `postgresql_pgvector.yaml` | DB+Vector | ✅ Curated | 2026-05-16 |
| Supabase | `supabase.yaml` | DB+Vector | ✅ Curated | 2026-05-16 |
| LangSmith | `langsmith.yaml` | Observability | ✅ Curated | 2026-05-16 |
| Helicone | `helicone.yaml` | Observability | ✅ Curated | 2026-05-16 |
| Guardrails AI | `guardrails_ai.yaml` | Safety | ✅ Curated | 2026-05-16 |
| NeMo Guardrails | `nemo_guardrails.yaml` | Safety | ✅ Curated | 2026-05-16 |
| Modal | `modal.yaml` | Deployment | ✅ Curated | 2026-05-16 |
| Fly.io | `flyio.yaml` | Deployment | ✅ Curated | 2026-05-16 |
| MongoDB | `mongodb.yaml` | DB | ✅ Curated | 2026-05-16 |
| MCP SDK (Python) | `mcp_sdk_python.yaml` | Protocol | ✅ Curated | 2026-05-16 |
| A2A Protocol | `a2a.yaml` | Protocol | ✅ Curated | 2026-05-16 |

## Schema Reference

See `schema.yaml` for the full field specification.

## Signal Sources

When curating, use these sources in priority order:
1. Official GitHub repo (stars, commits, issues, releases, security advisories)
2. Official documentation site (API surface, compliance guides)
3. Community Discord/Slack (known issues, workarounds)
4. Stack Overflow (Q&A velocity)
5. LinkedIn/Indeed (job demand — manual search, 30-day count)
6. Engineering blog post-mortems (production incident data)

## Quality Bar Before Launching

- All 25 frameworks must have `status: curated` before public launch
- Every `known_issues` entry must have a source link
- Every `compatible_with` entry must be validated (tested or community-confirmed)
- All signal data must be < 30 days old at launch
