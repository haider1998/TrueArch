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
| Qdrant | `qdrant.yaml` | Vector DB | ✅ Curated | 2026-05-16 |
| Redis | `redis.yaml` | Memory Layer | ✅ Curated | 2026-05-16 |
| OpenTelemetry | `opentelemetry.yaml` | Observability | ✅ Curated | 2026-05-16 |
| AutoGen | `autogen.yaml` | Orchestration | ⬜ Pending | — |
| Google ADK | `google_adk.yaml` | Orchestration | ⬜ Pending | — |
| Pydantic AI | `pydantic_ai.yaml` | Orchestration | ⬜ Pending | — |
| LlamaIndex | `llamaindex.yaml` | RAG | ⬜ Pending | — |
| Pinecone | `pinecone.yaml` | Vector DB | ⬜ Pending | — |
| Chroma | `chroma.yaml` | Vector DB | ⬜ Pending | — |
| Weaviate | `weaviate.yaml` | Vector DB | ⬜ Pending | — |
| PostgreSQL+pgvector | `postgresql_pgvector.yaml` | DB+Vector | ⬜ Pending | — |
| Supabase | `supabase.yaml` | DB+Vector | ⬜ Pending | — |
| LangSmith | `langsmith.yaml` | Observability | ⬜ Pending | — |
| Helicone | `helicone.yaml` | Observability | ⬜ Pending | — |
| FastAPI | `fastapi.yaml` | API | ⬜ Pending | — |
| Guardrails AI | `guardrails_ai.yaml` | Safety | ⬜ Pending | — |
| NeMo Guardrails | `nemo_guardrails.yaml` | Safety | ⬜ Pending | — |
| Modal | `modal.yaml` | Deployment | ⬜ Pending | — |
| Fly.io | `flyio.yaml` | Deployment | ⬜ Pending | — |
| MongoDB | `mongodb.yaml` | DB | ⬜ Pending | — |
| MCP SDK (Python) | `mcp_sdk_python.yaml` | Protocol | ⬜ Pending | — |
| A2A Protocol | `a2a.yaml` | Protocol | ⬜ Pending | — |

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
