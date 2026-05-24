"""
Code Pattern Library for TrueArch.

Provides version-pinned, validated snippets for the most critical AI framework patterns.
All snippets are curated to reflect the *current* stable API — not training-data-era patterns.

This is the primary mechanism by which TrueArch prevents LLM hallucination of deprecated APIs.
When an agent calls get_code_patterns(), it gets the exact API shape for the installed version,
not a potentially stale pattern from a training dataset that may be 12–18 months old.

Curation policy:
  - Every snippet is pinned to a version_range using PEP 440 specifiers
  - Snippets are verified against the version in data/frameworks/<framework>.yaml
  - Each snippet includes inline comments explaining the key API contracts
"""
from typing import Dict, List, Optional
from pydantic import BaseModel


class CodePattern(BaseModel):
    framework_id: str
    use_case: str
    version_range: str
    description: str
    snippet: str


# ── Pattern Library ───────────────────────────────────────────────────────────
# Organized by framework, then use case.
# The get_pattern() function uses substring matching on use_case (case-insensitive).

_PATTERNS: List[CodePattern] = [

    # ── LangGraph ─────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="langgraph",
        use_case="checkpoint_sqlite",
        version_range=">=1.2.0",
        description=(
            "Initialize an in-memory SQLite checkpointer in LangGraph v1.2+. "
            "Use for local development and testing. For production, prefer the Redis or Postgres checkpointer."
        ),
        snippet='''\
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from typing import TypedDict

class State(TypedDict):
    messages: list

# LangGraph v1.2+ pattern — SqliteSaver replaces MemorySaver for persistence
memory = SqliteSaver.from_conn_string(":memory:")
graph = StateGraph(State)
# ... add nodes and edges ...
app = graph.compile(checkpointer=memory)

# Always provide thread_id in config — required for checkpointing
config = {"configurable": {"thread_id": "user_session_123"}}
result = app.invoke({"messages": []}, config=config)
''',
    ),

    CodePattern(
        framework_id="langgraph",
        use_case="checkpoint_redis",
        version_range=">=1.2.0",
        description=(
            "Production-grade Redis checkpointer for LangGraph v1.2+. "
            "Use AsyncRedisSaver for async graphs. Requires langgraph-checkpoint-redis>=0.0.6."
        ),
        snippet='''\
# pip install langgraph-checkpoint-redis>=0.0.6
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.graph import StateGraph
from typing import TypedDict

class State(TypedDict):
    messages: list

async def build_graph():
    # Use async context manager — required for proper connection lifecycle
    async with AsyncRedisSaver.from_conn_string("redis://localhost:6379") as checkpointer:
        graph = StateGraph(State)
        # ... add nodes and edges ...
        app = graph.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": "user_session_123"}}
        result = await app.ainvoke({"messages": []}, config=config)
        return result
''',
    ),

    CodePattern(
        framework_id="langgraph",
        use_case="streaming",
        version_range=">=1.2.0",
        description=(
            "Stream graph outputs token-by-token using astream_events API v2 (LangGraph v1.2+). "
            "The v2 API is the current stable interface. Do NOT use the deprecated astream() without version=."
        ),
        snippet='''\
from langgraph.graph import StateGraph
from typing import TypedDict

class State(TypedDict):
    messages: list

# ... build app ...

config = {"configurable": {"thread_id": "user_123"}}
input_state = {"messages": [{"role": "user", "content": "Hello"}]}

# astream_events v2 — the stable streaming API in LangGraph v1.2+
async def stream_response():
    async for event in app.astream_events(input_state, config=config, version="v2"):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            # Token-level streaming
            chunk = event["data"]["chunk"]
            print(chunk.content, end="", flush=True)
        elif kind == "on_chain_end":
            # Graph node completed
            print(f"\\nNode completed: {event['name']}")
''',
    ),

    CodePattern(
        framework_id="langgraph",
        use_case="step_budget",
        version_range=">=1.2.0",
        description=(
            "Prevent agent infinite looping (known issue LGR-002) using explicit step budgets "
            "in LangGraph v1.2+. Always implement this in production — do NOT rely on prompt-only stop conditions."
        ),
        snippet='''\
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class State(TypedDict):
    messages: list
    steps_taken: Annotated[int, operator.add]  # Accumulate step count

def agent_node(state: State) -> dict:
    # ... agent logic ...
    return {"steps_taken": 1}  # Increment counter

def should_continue(state: State) -> str:
    """Route: continue or stop. Enforces step budget."""
    MAX_STEPS = 10  # Hard limit — tune per use case
    if state["steps_taken"] >= MAX_STEPS:
        return "stop"  # → END to prevent infinite loop (LGR-002 workaround)
    # ... other stop conditions ...
    return "continue"

graph = StateGraph(State)
graph.add_node("agent", agent_node)
graph.add_conditional_edges(
    "agent",
    should_continue,
    {"continue": "agent", "stop": END},
)
graph.set_entry_point("agent")

# Also set recursion_limit as a second safety net
config = {
    "configurable": {"thread_id": "user_123"},
    "recursion_limit": 15,  # Graph-level hard ceiling
}
app = graph.compile()
''',
    ),

    # ── Qdrant ────────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="qdrant",
        use_case="init",
        version_range=">=1.9.0",
        description=(
            "Production Qdrant client initialization with async support (qdrant-client>=1.9.0). "
            "Includes collection creation with the correct vector params for production use."
        ),
        snippet='''\
# pip install qdrant-client>=1.9.0
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import Distance, VectorParams

# Async client — preferred for FastAPI and async frameworks
async_client = AsyncQdrantClient(
    url="http://localhost:6333",
    # api_key="your-key",  # Required for Qdrant Cloud
    timeout=10,
)

COLLECTION_NAME = "my_vectors"
VECTOR_DIM = 1536  # e.g., OpenAI text-embedding-3-small

# Create collection if it doesn't exist
async def ensure_collection():
    collections = await async_client.get_collections()
    existing = {c.name for c in collections.collections}
    if COLLECTION_NAME not in existing:
        await async_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )

# Upsert vectors
async def upsert(ids: list, embeddings: list, payloads: list):
    from qdrant_client.models import PointStruct
    points = [
        PointStruct(id=uid, vector=emb, payload=meta)
        for uid, emb, meta in zip(ids, embeddings, payloads)
    ]
    await async_client.upsert(collection_name=COLLECTION_NAME, points=points)

# Search
async def search(query_vector: list, limit: int = 5):
    results = await async_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=limit,
        with_payload=True,
    )
    return results
''',
    ),

    # ── LangSmith ─────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="langsmith",
        use_case="tracing",
        version_range=">=0.1.0",
        description=(
            "Enable LangSmith tracing for LangGraph and LangChain applications. "
            "Set env vars before importing LangChain — order matters."
        ),
        snippet='''\
import os

# Set BEFORE importing any langchain/langgraph modules — tracing is configured at import time
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-langsmith-api-key"  # From smith.langchain.com
os.environ["LANGCHAIN_PROJECT"] = "my-production-project"   # Organizes runs in the UI

# Now import LangGraph / LangChain
from langgraph.graph import StateGraph

# All graph invocations are now automatically traced — no code changes needed
# Each invocation creates a "run" in LangSmith with full token/cost tracking

# Optional: add custom metadata to a specific invocation
from langsmith import traceable

@traceable(name="my_custom_step", tags=["production", "v2"])
def my_function(input: str) -> str:
    # This function's inputs/outputs will appear in LangSmith
    return input.upper()

# Optional: tag a run for easier filtering in the UI
config = {
    "configurable": {"thread_id": "user_123"},
    "tags": ["prod", "customer_support"],
    "metadata": {"user_id": "u_456", "session_id": "s_789"},
}
''',
    ),

    # ── FastAPI ───────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="fastapi",
        use_case="async_lifespan",
        version_range=">=0.100.0",
        description=(
            "Correct async lifespan pattern for FastAPI 0.100+. "
            "Replaces the deprecated @app.on_event('startup') / @app.on_event('shutdown') pattern. "
            "Use this for database connection pools, ML model loading, and any startup/shutdown logic."
        ),
        snippet='''\
from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI

# Shared state initialized at startup
_db_pool = None
_ml_model = None

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Async lifespan — replaces deprecated startup and shutdown event decorators.
    Everything before `yield` runs at startup; everything after runs at shutdown.
    """
    global _db_pool, _ml_model

    # ── Startup ──────────────────────────────────────────────────────────────
    print("Starting up: initializing resources...")
    # Example: async database pool
    # _db_pool = await create_async_engine(DATABASE_URL)
    # Example: load ML model once
    # _ml_model = load_model("path/to/model")

    yield  # Application serves requests here

    # ── Shutdown ─────────────────────────────────────────────────────────────
    print("Shutting down: releasing resources...")
    # if _db_pool:
    #     await _db_pool.dispose()

# Pass lifespan to FastAPI constructor — NOT as a decorator
app = FastAPI(
    title="My API",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health():
    return {"status": "ok"}
''',
    ),

    CodePattern(
        framework_id="fastapi",
        use_case="opentelemetry",
        version_range=">=0.100.0",
        description=(
            "Setting up OpenTelemetry auto-instrumentation in FastAPI. "
            "Instrument AFTER creating the app instance, BEFORE defining routes."
        ),
        snippet='''\
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# 1. Configure the tracer provider
provider = TracerProvider()
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317")
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(provider)

# 2. Create FastAPI app
app = FastAPI(title="My API")

# 3. Instrument AFTER app creation, BEFORE route definitions
FastAPIInstrumentor.instrument_app(app)

# 4. Define routes — all requests are now automatically traced
@app.get("/")
def read_root():
    return {"status": "ok"}
''',
    ),

    # ── Pydantic AI ───────────────────────────────────────────────────────────

    CodePattern(
        framework_id="pydantic_ai",
        use_case="tool",
        version_range=">=0.0.14",
        description=(
            "Define a typed tool in Pydantic AI 0.0.14+. "
            "Tools are regular Python functions decorated with @agent.tool. "
            "RunContext provides access to agent dependencies (database, config, etc.)."
        ),
        snippet='''\
# pip install pydantic-ai>=0.0.14
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext

@dataclass
class Deps:
    """Inject dependencies via RunContext — not globals."""
    api_key: str
    db_url: str

agent = Agent(
    "openai:gpt-4o",
    deps_type=Deps,
    system_prompt="You are a helpful assistant with access to weather data.",
)

@agent.tool
async def get_weather(ctx: RunContext[Deps], city: str) -> str:
    """
    Fetch current weather for a city.

    Args:
        ctx: RunContext with deps (api_key, db_url)
        city: City name to fetch weather for

    Returns:
        Weather description string
    """
    # ctx.deps.api_key is available here
    # Tool return type is automatically validated by Pydantic
    return f"Sunny, 22°C in {city}"  # Replace with real API call

# Run the agent
async def main():
    deps = Deps(api_key="sk-...", db_url="postgresql://...")
    result = await agent.run("What's the weather in London?", deps=deps)
    print(result.data)
''',
    ),

    # ── Redis ─────────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="redis",
        use_case="session_memory",
        version_range=">=5.0.0",
        description=(
            "Redis session memory pattern for AI agent state storage (redis>=5.0.0). "
            "Stores conversation history with TTL-based expiry. Compatible with LangGraph checkpointer pattern."
        ),
        snippet='''\
# pip install redis>=5.0.0
import json
from redis.asyncio import Redis
from typing import Optional

class RedisSessionMemory:
    """
    Async Redis session memory for AI agents.
    Stores conversation state with automatic TTL expiry.
    """
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl_seconds: int = 86400):
        self._client: Optional[Redis] = None
        self._url = redis_url
        self._ttl = ttl_seconds  # Default: 24 hours

    async def connect(self):
        """Call once at application startup (use within lifespan context)."""
        self._client = Redis.from_url(
            self._url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,  # Pool size — tune for concurrency
        )
        await self._client.ping()  # Fail fast on bad connection

    async def save(self, session_id: str, state: dict) -> None:
        """Persist agent state for a session. Overwrites existing state."""
        key = f"truearch:session:{session_id}"
        await self._client.setex(key, self._ttl, json.dumps(state))

    async def load(self, session_id: str) -> Optional[dict]:
        """Load agent state for a session. Returns None if expired or not found."""
        key = f"truearch:session:{session_id}"
        raw = await self._client.get(key)
        return json.loads(raw) if raw else None

    async def delete(self, session_id: str) -> None:
        """Explicitly delete a session (e.g. on user logout)."""
        await self._client.delete(f"truearch:session:{session_id}")

    async def close(self):
        """Call at application shutdown."""
        if self._client:
            await self._client.aclose()
''',
    ),
]


# ── Lookup API ────────────────────────────────────────────────────────────────

def get_pattern(framework_id: str, use_case: str) -> Optional[CodePattern]:
    """
    Find a code pattern by framework ID and use_case keyword.
    Uses case-insensitive substring matching against use_case.
    Returns the first match found in definition order (most specific patterns listed first).
    """
    use_case_lower = use_case.lower()
    for pattern in _PATTERNS:
        if pattern.framework_id == framework_id and use_case_lower in pattern.use_case.lower():
            return pattern
    return None


def get_available_use_cases(framework_id: str) -> List[str]:
    """Returns all available use_case keys for a given framework_id."""
    return [p.use_case for p in _PATTERNS if p.framework_id == framework_id]


def get_all_patterns() -> List[CodePattern]:
    """Returns the full pattern library. Used by tests and admin tooling."""
    return list(_PATTERNS)


def get_supported_frameworks() -> List[str]:
    """Returns the distinct set of framework_ids that have at least one pattern."""
    return sorted(set(p.framework_id for p in _PATTERNS))
