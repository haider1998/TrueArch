# Using TrueArch with Claude Code

TrueArch is an MCP server that catches deprecated / hallucinated framework APIs in
generated code, and gives your agent real versions and grounded architecture
context. This guide gets it running in Claude Code and gives you a checklist to
*feel* the value in a real session.

---

## 1. Wire it in (60 seconds)

From a checkout (until `truearch-mcp` is on PyPI):

```bash
# Install the console script into a venv
python -m venv venv && source venv/bin/activate
pip install -e .

# Register it with Claude Code (project-scoped .mcp.json is already in this repo)
claude mcp list          # → truearch: ✓ Connected
```

Once on PyPI it's a one-liner, no clone:

```bash
claude mcp add truearch -- uvx truearch-mcp
```

Confirm inside a session: run `/mcp` — you should see the `truearch` server with
tools like `mcp__truearch__validate_code`, `mcp__truearch__latest_stable_versions`,
`mcp__truearch__quick_context`.

> **Note:** MCP servers load at session start. Start a *fresh* `claude` session in
> this repo after wiring it in — tools can't be hot-added to a running session.

---

## 2. The nudge (optional but recommended)

The repo [CLAUDE.md](../CLAUDE.md) tells the agent to call `validate_code` before
finalizing framework code. Without it, whether the agent calls the tool on its own
depends on the tool descriptions alone. The A/B eval (below) measures both.

---

## 3. Trap-prompt checklist (run these in a fresh session)

Each prompt is something a model trained on older code tends to get wrong. **What
good looks like:** the agent calls `mcp__truearch__validate_code`, the verdict comes
back `critical`/`errors`, and the final code uses the corrected API.

| # | Prompt to paste | The stale API it should avoid | The fix you want to see |
|---|---|---|---|
| 1 | "Write a Python script that connects to Pinecone and creates a serverless index, then upserts 100 vectors." | `pinecone.init(...)` | `from pinecone import Pinecone; pc = Pinecone(...)` + `ServerlessSpec` |
| 2 | "Set up a LangGraph agent with persistent memory across turns." | bare `builder.compile()` / `MemorySaver` | `compile(checkpointer=...)`, `InMemorySaver`/`AsyncRedisSaver` |
| 3 | "Call an OpenAI chat model and print the reply." | `openai.ChatCompletion.create(...)` | `from openai import OpenAI; client.chat.completions.create(...)` |
| 4 | "Use the Anthropic Python SDK to send a message to Claude." | `client.completions.create(...)` (Human:/Assistant:) | `client.messages.create(model=..., messages=[...])` |
| 5 | "Query a Weaviate collection for the 5 nearest objects." | `weaviate.Client(url)` / `client.query.get(...)` | `weaviate.connect_to_local()` + `collections.get(...).query.near_text(...)` |
| 6 | "Import a chat model from LangChain and invoke it." | `from langchain.chat_models import ChatOpenAI` / `.predict()` | `from langchain_openai import ChatOpenAI` + `.invoke()` |
| 7 | "Load documents and build a LlamaIndex vector index." | `from llama_index import ...` / `ServiceContext` | `from llama_index.core import ...` + `Settings` |
| 8 | "Create a persistent Chroma client and a collection." | `chromadb.Client(Settings(chroma_db_impl=...))` / `.persist()` | `chromadb.PersistentClient(path=...)` |
| 9 | "Set up two AutoGen agents that talk to each other." | `from autogen import AssistantAgent` / `initiate_chat` | `from autogen_agentchat.agents import AssistantAgent` + `run()` |
| 10 | "Connect to Qdrant and search a collection." | `QdrantClient(url=..., collection_name=...)` | collection name per-operation |
| 11 | "Build a CrewAI crew with a sequential process." | `from crewai import ... Process` | current `Crew(...)` process form |
| 12 | "Create a PydanticAI agent that returns a typed result and print it." | `result_type=` / `result.data` | `output_type=` / `result.output` |

**Quick manual check (no full session):** you can hit the tool directly through the
headless CLI:

```bash
claude -p "Use validate_code to check this Pinecone code: import pinecone; pinecone.init(api_key='x')" \
  --mcp-config .mcp.json --strict-mcp-config \
  --allowedTools mcp__truearch__validate_code \
  --permission-mode bypassPermissions \
  --max-budget-usd 0.50 --output-format stream-json --verbose
```

You should see a `mcp__truearch__validate_code` tool call and a `critical` verdict
naming `PCN-001`.

---

## 4. Measure it (automated A/B)

To prove the value reproducibly across all trap tasks — baseline vs TrueArch-organic
vs TrueArch-nudged, graded by `validate_code` — see
[`benchmark/daily_loop_eval.py`](../benchmark/daily_loop_eval.py):

```bash
# Pilot (3 tasks, cheap) then full run
python benchmark/daily_loop_eval.py --limit 3
python benchmark/daily_loop_eval.py
# → writes benchmark/daily_loop_results.md
```
