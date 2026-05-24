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

    # ── CrewAI ────────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="crewai",
        use_case="crew_setup",
        version_range=">=0.80.0",
        description=(
            "Define a crew with agents and tasks in CrewAI 0.80+. "
            "Uses the new @agent, @task, @crew decorator API. "
            "Do NOT use the legacy Agent(role=..., goal=...) constructor from pre-0.60 tutorials."
        ),
        snippet='''\
# pip install crewai>=0.80.0
from crewai import Agent, Task, Crew, Process

# CrewAI 0.80+ agent definition — role-based, with explicit backstory
researcher = Agent(
    role="Senior Research Analyst",
    goal="Find and summarize the latest AI framework trends",
    backstory="You are an expert at analyzing technology trends and market signals.",
    verbose=True,
    allow_delegation=False,  # Set True only if this agent should delegate to others
)

writer = Agent(
    role="Technical Writer",
    goal="Write a clear, concise report from research findings",
    backstory="You excel at making complex technical topics accessible.",
    verbose=True,
    allow_delegation=False,
)

# Task definition — each task is assigned to exactly one agent
research_task = Task(
    description="Research the top 5 AI orchestration frameworks in 2026. Compare features, adoption, and risks.",
    expected_output="A structured comparison table with pros/cons for each framework.",
    agent=researcher,
)

write_task = Task(
    description="Write a 500-word executive summary based on the research findings.",
    expected_output="A polished executive summary in markdown format.",
    agent=writer,
)

# Crew — sequential process is the default and most predictable
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential,  # Tasks run in order; use Process.hierarchical for manager delegation
    verbose=True,
)

result = crew.kickoff()
print(result)
''',
    ),

    CodePattern(
        framework_id="crewai",
        use_case="tool",
        version_range=">=0.80.0",
        description=(
            "Add a custom tool to a CrewAI agent using the @tool decorator (CrewAI 0.80+). "
            "Tools must return a string. Use crewai_tools for built-in tools (search, scrape, etc.)."
        ),
        snippet='''\
# pip install crewai>=0.80.0 crewai-tools>=0.12.0
from crewai import Agent, Task, Crew
from crewai.tools import tool

@tool("Search Database")
def search_database(query: str) -> str:
    """Search the internal database for relevant documents.

    Args:
        query: The search query string.
    """
    # Tool must return a string — CrewAI passes it back to the agent as text
    # Replace with your actual database search logic
    return f"Found 3 results for: {query}"

# Attach tools to agent via the tools parameter
agent = Agent(
    role="Database Analyst",
    goal="Answer questions using our internal database",
    backstory="You are an expert at querying and interpreting database records.",
    tools=[search_database],  # List of tool functions
    verbose=True,
)
''',
    ),

    # ── Google ADK ────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="google_adk",
        use_case="agent",
        version_range=">=1.0.0",
        description=(
            "Create a basic Google ADK agent with tools (google-adk>=1.0.0). "
            "ADK agents are async-native and support MCP tool integration. "
            "Use InMemoryRunner for local testing, deploy via Cloud Run for production."
        ),
        snippet='''\
# pip install google-adk>=1.0.0
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner

# Define tools as regular Python functions — ADK wraps them automatically
def get_weather(city: str) -> dict:
    """Get the current weather for a city.

    Args:
        city: The name of the city.

    Returns:
        A dictionary with weather information.
    """
    return {"city": city, "temp_c": 22, "condition": "Sunny"}

# Create agent with tools
weather_agent = Agent(
    name="weather_agent",
    model="gemini-2.0-flash",
    instruction="You are a helpful weather assistant. Use your tools to answer weather questions.",
    tools=[get_weather],
)

# Local testing with InMemoryRunner
async def main():
    runner = InMemoryRunner(agent=weather_agent)
    async for event in runner.run_async(
        user_id="test_user",
        session_id="test_session",
        new_message="What's the weather in London?",
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(part.text)

import asyncio
asyncio.run(main())
''',
    ),

    CodePattern(
        framework_id="google_adk",
        use_case="multi_agent",
        version_range=">=1.0.0",
        description=(
            "Multi-agent delegation pattern in Google ADK 1.0+. "
            "Uses sub_agents for hierarchical delegation. The root agent delegates to specialists."
        ),
        snippet='''\
# pip install google-adk>=1.0.0
from google.adk.agents import Agent

# Specialist agents
researcher = Agent(
    name="researcher",
    model="gemini-2.0-flash",
    instruction="You are a research specialist. Find factual answers to questions.",
)

writer = Agent(
    name="writer",
    model="gemini-2.0-flash",
    instruction="You are a writing specialist. Create polished summaries from research notes.",
)

# Root agent delegates to specialists via sub_agents
coordinator = Agent(
    name="coordinator",
    model="gemini-2.0-flash",
    instruction=(
        "You are a project coordinator. "
        "Delegate research tasks to the researcher agent and writing tasks to the writer agent."
    ),
    sub_agents=[researcher, writer],  # ADK handles delegation routing
)
''',
    ),

    # ── LlamaIndex ────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="llamaindex",
        use_case="rag",
        version_range=">=0.11.0",
        description=(
            "Basic RAG pipeline in LlamaIndex 0.11+ (llama-index-core). "
            "Uses the new modular package structure — do NOT use 'from llama_index import ...' (pre-0.10 pattern). "
            "All imports go through llama_index.core."
        ),
        snippet='''\
# pip install llama-index-core>=0.11.0 llama-index-llms-openai llama-index-embeddings-openai
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# Configure global settings (replaces deprecated ServiceContext)
Settings.llm = OpenAI(model="gpt-4o", temperature=0)
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

# Load documents from a directory
documents = SimpleDirectoryReader("./data").load_data()

# Build vector index — embeddings are computed automatically
index = VectorStoreIndex.from_documents(documents)

# Query the index
query_engine = index.as_query_engine(
    similarity_top_k=5,  # Number of chunks to retrieve
)
response = query_engine.query("What are the key findings?")
print(response)
''',
    ),

    CodePattern(
        framework_id="llamaindex",
        use_case="agent",
        version_range=">=0.11.0",
        description=(
            "LlamaIndex ReAct agent pattern (0.11+). "
            "Uses FunctionTool for tool wrapping. Do NOT use the deprecated LangchainToolSpec."
        ),
        snippet='''\
# pip install llama-index-core>=0.11.0 llama-index-llms-openai
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

# Define tools as plain Python functions
def search_docs(query: str) -> str:
    """Search internal documentation for relevant information."""
    return f"Found results for: {query}"

def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression))  # noqa: S307 — demo only
    except Exception as e:
        return f"Error: {e}"

# Wrap as FunctionTool — LlamaIndex infers schema from type hints + docstring
search_tool = FunctionTool.from_defaults(fn=search_docs)
calc_tool = FunctionTool.from_defaults(fn=calculate)

# Create ReAct agent
llm = OpenAI(model="gpt-4o", temperature=0)
agent = ReActAgent.from_tools(
    tools=[search_tool, calc_tool],
    llm=llm,
    verbose=True,
    max_iterations=10,  # Prevent infinite loops — always set this in production
)

response = agent.chat("How many documents mention 'LangGraph'?")
print(response)
''',
    ),

    # ── Chroma ────────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="chroma",
        use_case="init",
        version_range=">=0.5.0",
        description=(
            "Initialize Chroma for local development and prototyping (chromadb>=0.5.0). "
            "Chroma is best for prototype/growth scale. For production (>100K users), prefer Qdrant or pgvector."
        ),
        snippet='''\
# pip install chromadb>=0.5.0
import chromadb

# Ephemeral client — data lives in memory only (for testing)
client = chromadb.Client()

# Persistent client — data saved to disk (for local development)
# client = chromadb.PersistentClient(path="./chroma_data")

# Create or get a collection
collection = client.get_or_create_collection(
    name="my_documents",
    metadata={"hnsw:space": "cosine"},  # Distance metric: cosine, l2, or ip
)

# Add documents — Chroma auto-embeds using its default model
collection.add(
    documents=["LangGraph is a graph-based orchestrator", "CrewAI uses role-based agents"],
    ids=["doc1", "doc2"],
    metadatas=[{"source": "blog"}, {"source": "docs"}],
)

# Query — returns nearest neighbors
results = collection.query(
    query_texts=["What is the best agent framework?"],
    n_results=2,
    include=["documents", "distances", "metadatas"],
)
print(results["documents"])
''',
    ),

    # ── Pinecone ──────────────────────────────────────────────────────────────

    CodePattern(
        framework_id="pinecone",
        use_case="init",
        version_range=">=5.0.0",
        description=(
            "Initialize Pinecone serverless index (pinecone>=5.0.0). "
            "The v5 SDK replaced pinecone-client. Do NOT use pinecone.init() or pinecone.Index() (deprecated v2 API)."
        ),
        snippet='''\
# pip install pinecone>=5.0.0
from pinecone import Pinecone, ServerlessSpec

# Initialize — v5 uses Pinecone() class, NOT pinecone.init() (deprecated)
pc = Pinecone(api_key="your-api-key")

INDEX_NAME = "my-vectors"
DIMENSION = 1536  # Match your embedding model dimension

# Create serverless index if it doesn't exist
existing = [idx.name for idx in pc.list_indexes()]
if INDEX_NAME not in existing:
    pc.create_index(
        name=INDEX_NAME,
        dimension=DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

# Connect to index
index = pc.Index(INDEX_NAME)

# Upsert vectors
index.upsert(
    vectors=[
        {"id": "vec1", "values": [0.1] * DIMENSION, "metadata": {"source": "doc1"}},
        {"id": "vec2", "values": [0.2] * DIMENSION, "metadata": {"source": "doc2"}},
    ],
    namespace="default",
)

# Query
results = index.query(
    vector=[0.15] * DIMENSION,
    top_k=5,
    include_metadata=True,
    namespace="default",
)
for match in results["matches"]:
    print(f"ID: {match['id']}, Score: {match['score']:.4f}")
''',
    ),

    # ── OpenTelemetry ─────────────────────────────────────────────────────────

    CodePattern(
        framework_id="opentelemetry",
        use_case="basic_tracing",
        version_range=">=1.24.0",
        description=(
            "Basic OpenTelemetry tracing setup (opentelemetry-sdk>=1.24.0). "
            "Sets up a TracerProvider with OTLP export. Use this as the foundation "
            "for instrumenting any Python service."
        ),
        snippet='''\
# pip install opentelemetry-sdk>=1.24.0 opentelemetry-exporter-otlp-proto-grpc
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# 1. Define service identity
resource = Resource.create({"service.name": "my-ai-service", "service.version": "1.0.0"})

# 2. Set up tracer provider with OTLP exporter
provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(provider)

# 3. Get a tracer for your module
tracer = trace.get_tracer(__name__)

# 4. Use spans to trace operations
with tracer.start_as_current_span("process_query") as span:
    span.set_attribute("query.type", "rag")
    span.set_attribute("query.tokens", 150)
    # ... your logic here ...
    span.set_status(trace.StatusCode.OK)
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
