# Working in this repo

## Use TrueArch to avoid shipping stale framework code

TrueArch is wired in as an MCP server (see `.mcp.json`). Its whole job is to catch
deprecated / hallucinated framework APIs — the kind a model trained on older code
emits by default.

**When you write or edit code that uses an AI framework** — Pinecone, LangGraph,
LangChain, LlamaIndex, Qdrant, Weaviate, Chroma, the OpenAI or Anthropic SDK,
AutoGen, CrewAI, PydanticAI, FastAPI, Supabase, or Ollama:

1. Before finalizing it, call **`mcp__truearch__validate_code`** with the snippet and
   the `framework_id`. If it reports violations, apply the `correct_example` fix and
   re-check until the verdict is `clean`.
2. When pinning dependency versions, call **`mcp__truearch__latest_stable_versions`**
   instead of guessing — hallucinated versions are a top failure mode.
3. When starting a new system from scratch, call **`mcp__truearch__quick_context`**
   for a token-cheap, grounded brief before choosing a stack.

Do not silently trust your training-data memory of these frameworks' APIs — that
memory is what TrueArch exists to correct.
