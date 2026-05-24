#!/usr/bin/env python3
"""
TrueArch A/B Evaluation Framework.

Compares LLM architecture recommendations WITH vs WITHOUT TrueArch MCP context.
Measures: correctness, specificity, recency, known-issues awareness,
actionability, hallucination rate, and token efficiency.

Usage:
    # With Gemini (default)
    GOOGLE_API_KEY=xxx python benchmark/ab_evaluation.py

    # With OpenAI
    OPENAI_API_KEY=xxx python benchmark/ab_evaluation.py --provider openai

    # With specific model
    GOOGLE_API_KEY=xxx python benchmark/ab_evaluation.py --model gemini-2.5-flash
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Ensure project root is importable ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── TrueArch imports (direct Python, no server needed) ────────────────────────
from src.mcp.server import (
    quick_context,
    recommend_ai_stack,
    compare_frameworks,
    get_framework_score,
    get_code_patterns,
    explain_score,
    architecture_tradeoffs,
)


# ══════════════════════════════════════════════════════════════════════════════
# DATA: Test Scenarios
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Scenario:
    id: str
    prompt: str
    truearch_calls: List[Dict[str, Any]]  # TrueArch tool calls for Arm B
    ground_truth: str  # Expert-curated correct answer summary
    deterministic_checks: List[Dict[str, Any]]  # Keyword/fact checks
    mcp_kwargs: Dict[str, Any] = field(default_factory=dict)  # kwargs for recommend_ai_stack


SCENARIOS: List[Scenario] = [
    Scenario(
        id="S01",
        prompt="I need to build a HIPAA-compliant multi-agent healthcare assistant that handles patient data. What technology stack should I use?",
        truearch_calls=[
            {"tool": "recommend_ai_stack", "kwargs": {"problem": "HIPAA-compliant multi-agent healthcare assistant with patient data handling", "compliance": ["hipaa"], "scale": "enterprise", "priority": "governance"}},
        ],
        mcp_kwargs={"problem": "HIPAA-compliant multi-agent healthcare assistant", "compliance": ["hipaa"], "scale": "enterprise", "priority": "governance"},
        ground_truth=(
            "Should recommend LangGraph or Google ADK for orchestration (not AutoGen — maintenance mode). "
            "Must warn about HIPAA compliance requirements: PHI encryption, BAA with cloud providers, audit logging. "
            "Should NOT recommend Chroma for vector DB at enterprise scale. "
            "Must mention specific compliance deployment counts or governance readiness."
        ),
        deterministic_checks=[
            {"name": "no_autogen_for_enterprise", "type": "must_not_contain", "keywords": ["recommend autogen", "choose autogen", "autogen is a great"], "reason": "AutoGen is in maintenance mode and must not be recommended for new enterprise projects"},
            {"name": "hipaa_awareness", "type": "must_contain_any", "keywords": ["hipaa", "phi", "protected health", "baa", "business associate"], "reason": "HIPAA query must mention HIPAA compliance requirements"},
        ],
    ),
    Scenario(
        id="S02",
        prompt="Should I use LangGraph or CrewAI for my AI agent orchestration layer in 2026?",
        truearch_calls=[
            {"tool": "compare_frameworks", "kwargs": {"framework_a": "langgraph", "framework_b": "crewai"}},
        ],
        mcp_kwargs={},
        ground_truth=(
            "LangGraph: graph-based, best-in-class state management (100/100), v1.2.0 stable, 32K stars, "
            "but watch for checkpoint bloat and infinite looping. "
            "CrewAI: role-based, simpler mental model, growing fast but less mature. "
            "Must NOT say AutoGen is a viable alternative without noting maintenance mode."
        ),
        deterministic_checks=[
            {"name": "knows_langgraph_is_graph_based", "type": "must_contain_any", "keywords": ["graph", "stateful", "state management", "checkpoint"], "reason": "Must know LangGraph's core differentiator"},
            {"name": "knows_crewai_is_role_based", "type": "must_contain_any", "keywords": ["role", "crew", "agent roles", "task-based"], "reason": "Must know CrewAI's paradigm"},
        ],
    ),
    Scenario(
        id="S03",
        prompt="I need to set up a RAG pipeline for enterprise document search over 10M+ documents. What should I use?",
        truearch_calls=[
            {"tool": "recommend_ai_stack", "kwargs": {"problem": "RAG pipeline for 10M+ enterprise document search", "scale": "enterprise"}},
        ],
        mcp_kwargs={"problem": "RAG pipeline for enterprise document search", "scale": "enterprise"},
        ground_truth=(
            "Should recommend LlamaIndex or LangChain for the RAG orchestration layer. "
            "Vector DB should be Qdrant or Pinecone (not Chroma — prototype only). "
            "Should mention embedding model selection and chunking strategy."
        ),
        deterministic_checks=[
            {"name": "no_chroma_for_enterprise", "type": "must_not_contain", "keywords": ["recommend chroma for production", "chroma for enterprise", "chroma at scale"], "reason": "Chroma is prototype-only, must not be recommended for 10M+ docs"},
            {"name": "mentions_vector_db", "type": "must_contain_any", "keywords": ["vector", "embedding", "qdrant", "pinecone", "weaviate", "pgvector"], "reason": "RAG at scale needs a production vector DB"},
        ],
    ),
    Scenario(
        id="S04",
        prompt="Build a multi-agent customer support system where agents can hand off conversations between specialist agents.",
        truearch_calls=[
            {"tool": "recommend_ai_stack", "kwargs": {"problem": "Multi-agent customer support system with handoffs between specialist agents"}},
        ],
        mcp_kwargs={"problem": "Multi-agent customer support with handoffs"},
        ground_truth=(
            "LangGraph is the best fit — its graph-based state management enables explicit handoff edges. "
            "Should mention step budgets to prevent infinite loops. "
            "Google ADK or CrewAI are valid alternatives. AutoGen should not be recommended."
        ),
        deterministic_checks=[
            {"name": "multi_agent_capable", "type": "must_contain_any", "keywords": ["langgraph", "crewai", "google adk", "adk", "pydantic ai"], "reason": "Must recommend a multi-agent capable orchestrator"},
        ],
    ),
    Scenario(
        id="S05",
        prompt="What's the correct way to set up checkpointing in LangGraph to persist agent state?",
        truearch_calls=[
            {"tool": "get_code_patterns", "kwargs": {"framework_id": "langgraph", "use_case": "checkpoint"}},
            {"tool": "architecture_tradeoffs", "kwargs": {"framework_id": "langgraph"}},
        ],
        mcp_kwargs={},
        ground_truth=(
            "LangGraph v1.2.0 uses MemorySaver (dev) or AsyncPostgresSaver/RedisSaver (production). "
            "v1.2+ introduced DeltaChannel (beta) for reduced checkpoint overhead. "
            "Must warn about checkpoint serialization bloat (known issue LGR-001). "
            "Code should import from langgraph.checkpoint, NOT deprecated paths."
        ),
        deterministic_checks=[
            {"name": "correct_checkpoint_api", "type": "must_contain_any", "keywords": ["MemorySaver", "checkpointer", "checkpoint", "PostgresSaver", "RedisSaver"], "reason": "Must use correct LangGraph checkpoint API"},
            {"name": "knows_bloat_issue", "type": "must_contain_any", "keywords": ["bloat", "serialization", "DeltaChannel", "overhead", "checkpoint size"], "reason": "Must warn about checkpoint bloat (LGR-001)"},
        ],
    ),
    Scenario(
        id="S06",
        prompt="I need to add OpenTelemetry tracing to my FastAPI + LangGraph agent service. Show me how.",
        truearch_calls=[
            {"tool": "get_code_patterns", "kwargs": {"framework_id": "opentelemetry", "use_case": "basic_tracing"}},
            {"tool": "get_code_patterns", "kwargs": {"framework_id": "fastapi", "use_case": "production"}},
        ],
        mcp_kwargs={},
        ground_truth=(
            "Should set up TracerProvider with OTLP exporter. "
            "FastAPI instrumentation via opentelemetry-instrumentation-fastapi. "
            "LangGraph spans via LangSmith or direct OTEL node instrumentation. "
            "Must include pip install commands and correct import paths."
        ),
        deterministic_checks=[
            {"name": "correct_otel_imports", "type": "must_contain_any", "keywords": ["TracerProvider", "opentelemetry", "OTLP", "BatchSpanProcessor"], "reason": "Must use correct OpenTelemetry API"},
            {"name": "has_pip_install", "type": "must_contain_any", "keywords": ["pip install", "opentelemetry-sdk", "opentelemetry"], "reason": "Must include installation instructions"},
        ],
    ),
    Scenario(
        id="S07",
        prompt="Recommend a production vector database for semantic search at enterprise scale. I need to handle 50M+ vectors.",
        truearch_calls=[
            {"tool": "recommend_ai_stack", "kwargs": {"problem": "Production vector database for semantic search at enterprise scale with 50M+ vectors", "scale": "enterprise"}},
        ],
        mcp_kwargs={"problem": "Production vector DB for 50M+ vectors", "scale": "enterprise"},
        ground_truth=(
            "Qdrant or Pinecone for enterprise scale. "
            "Chroma is NOT suitable (prototype-only). "
            "Should mention quantization, sharding, or horizontal scaling capabilities. "
            "Pinecone serverless is easiest; Qdrant is best self-hosted option."
        ),
        deterministic_checks=[
            {"name": "production_vector_db", "type": "must_contain_any", "keywords": ["qdrant", "pinecone", "weaviate", "pgvector", "milvus"], "reason": "Must recommend a production-grade vector DB"},
            {"name": "no_chroma_solo", "type": "must_not_contain", "keywords": ["recommend chroma", "chroma is the best", "chroma for production"], "reason": "Chroma is prototype-only for 50M+ vectors"},
        ],
    ),
    Scenario(
        id="S08",
        prompt="Is AutoGen still a good choice for my new multi-agent project in 2026?",
        truearch_calls=[
            {"tool": "get_framework_score", "kwargs": {"framework_id": "autogen"}},
            {"tool": "explain_score", "kwargs": {"framework_id": "autogen"}},
        ],
        mcp_kwargs={},
        ground_truth=(
            "NO — AutoGen was placed in MAINTENANCE MODE by Microsoft in early 2026. "
            "Primary development shifted to Microsoft Agent Framework. "
            "Existing v0.2 code is incompatible with v0.4+. "
            "Recommend LangGraph, Google ADK, or CrewAI instead. "
            "Must explicitly warn against starting new projects with AutoGen."
        ),
        deterministic_checks=[
            {"name": "knows_maintenance_mode", "type": "must_contain_any", "keywords": ["maintenance mode", "maintenance", "deprecated", "no longer actively", "microsoft agent framework", "not recommended"], "reason": "CRITICAL: Must know AutoGen is in maintenance mode"},
            {"name": "suggests_alternatives", "type": "must_contain_any", "keywords": ["langgraph", "crewai", "google adk", "adk", "pydantic ai"], "reason": "Must suggest modern alternatives"},
        ],
    ),
    Scenario(
        id="S09",
        prompt="I want to build a Python AI agent with tool use, persistent memory, and MCP integration. What's the best stack?",
        truearch_calls=[
            {"tool": "recommend_ai_stack", "kwargs": {"problem": "Python AI agent with tool use, persistent memory, and MCP integration", "language": "python"}},
        ],
        mcp_kwargs={"problem": "Python AI agent with tool use, memory, MCP integration", "language": "python"},
        ground_truth=(
            "LangGraph for orchestration (best state management, MCP community plugin). "
            "Or Google ADK (native MCP support). "
            "Redis for state persistence. "
            "FastAPI for API layer. "
            "Should mention MCP support levels for each framework."
        ),
        deterministic_checks=[
            {"name": "mentions_mcp", "type": "must_contain_any", "keywords": ["mcp", "model context protocol", "tool protocol"], "reason": "Query explicitly asks about MCP — must address it"},
            {"name": "mentions_memory", "type": "must_contain_any", "keywords": ["memory", "state", "persist", "redis", "checkpoint", "session"], "reason": "Query asks about persistent memory"},
        ],
    ),
    Scenario(
        id="S10",
        prompt="Compare Pinecone vs Qdrant vs Chroma for my vector search use case. I'm building a production SaaS product.",
        truearch_calls=[
            {"tool": "compare_frameworks", "kwargs": {"framework_a": "pinecone", "framework_b": "qdrant"}},
            {"tool": "get_framework_score", "kwargs": {"framework_id": "chroma"}},
        ],
        mcp_kwargs={},
        ground_truth=(
            "Pinecone: serverless, managed, easiest ops but vendor lock-in. Uses Pinecone() class in v5 SDK (NOT pinecone.init()). "
            "Qdrant: best self-hosted, Rust-native, growing fast. "
            "Chroma: prototype-only, NOT for production SaaS. "
            "Must warn that Chroma is unsuitable for production SaaS workloads."
        ),
        deterministic_checks=[
            {"name": "chroma_limitation", "type": "must_contain_any", "keywords": ["prototype", "not production", "development", "local", "small scale", "not suitable", "limited"], "reason": "Must note Chroma's production limitations"},
            {"name": "correct_pinecone_api", "type": "must_not_contain", "keywords": ["pinecone.init(", "pinecone.init ("], "reason": "Must NOT use deprecated Pinecone v2 API (pinecone.init)"},
        ],
    ),
]


# ══════════════════════════════════════════════════════════════════════════════
# LLM Provider Abstraction
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    model: str


def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    model: str = "gemini-2.0-flash",
) -> LLMResponse:
    """Call Google Gemini API."""
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(temperature=0.0, max_output_tokens=2048),
    )

    start = time.time()
    response = gen_model.generate_content(user_prompt)
    latency_ms = int((time.time() - start) * 1000)

    usage = response.usage_metadata
    return LLMResponse(
        text=response.text or "",
        input_tokens=usage.prompt_token_count,
        output_tokens=usage.candidates_token_count,
        total_tokens=usage.total_token_count,
        latency_ms=latency_ms,
        model=model,
    )


def _call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4o-mini",
) -> LLMResponse:
    """Call OpenAI API."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    start = time.time()
    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    latency_ms = int((time.time() - start) * 1000)

    usage = response.usage
    return LLMResponse(
        text=response.choices[0].message.content or "",
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        latency_ms=latency_ms,
        model=model,
    )


def call_llm(
    system_prompt: str,
    user_prompt: str,
    provider: str = "gemini",
    model: str | None = None,
) -> LLMResponse:
    """Unified LLM call dispatcher."""
    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, model or "gemini-2.0-flash")
    elif provider == "openai":
        return _call_openai(system_prompt, user_prompt, model or "gpt-4o-mini")
    else:
        raise ValueError(f"Unknown provider: {provider}")


# ══════════════════════════════════════════════════════════════════════════════
# TrueArch Context Builder
# ══════════════════════════════════════════════════════════════════════════════

def build_truearch_context(scenario: Scenario) -> Tuple[str, int]:
    """
    Call TrueArch tools for a scenario and build the context injection string.
    Returns (context_string, estimated_tokens).
    """
    results = []
    for call in scenario.truearch_calls:
        tool_name = call["tool"]
        kwargs = call["kwargs"]

        if tool_name == "recommend_ai_stack":
            result = recommend_ai_stack(**kwargs)
        elif tool_name == "compare_frameworks":
            result = compare_frameworks(**kwargs)
        elif tool_name == "get_framework_score":
            result = get_framework_score(**kwargs)
        elif tool_name == "get_code_patterns":
            result = get_code_patterns(**kwargs)
        elif tool_name == "explain_score":
            result = explain_score(**kwargs)
        elif tool_name == "architecture_tradeoffs":
            result = architecture_tradeoffs(**kwargs)
        elif tool_name == "quick_context":
            result = quick_context(**kwargs)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        results.append({"tool": tool_name, "result": result})

    context_json = json.dumps(results, indent=2, default=str)
    estimated_tokens = len(context_json) // 4  # rough heuristic
    return context_json, estimated_tokens


# ══════════════════════════════════════════════════════════════════════════════
# System Prompts
# ══════════════════════════════════════════════════════════════════════════════

BASELINE_SYSTEM_PROMPT = """\
You are a senior software architect specializing in AI/ML systems. \
Provide specific, actionable technology recommendations. \
Include version numbers, installation commands, and code examples where relevant. \
Be concise and opinionated — give a clear recommendation, not a menu of options."""

TRUEARCH_SYSTEM_PROMPT_TEMPLATE = """\
You are a senior software architect specializing in AI/ML systems. \
You have access to TrueArch architecture intelligence data (below). \
Use this data to provide specific, accurate, and production-ready recommendations. \
Include version numbers, installation commands, and code examples where relevant. \
Be concise and opinionated — give a clear recommendation, not a menu of options.

## TrueArch Intelligence Data

{truearch_context}"""


# ══════════════════════════════════════════════════════════════════════════════
# Scoring: Deterministic Checks
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CheckResult:
    name: str
    passed: bool
    reason: str


def run_deterministic_checks(response_text: str, checks: List[Dict]) -> List[CheckResult]:
    """Run keyword-based deterministic checks against a response."""
    results = []
    text_lower = response_text.lower()

    for check in checks:
        name = check["name"]
        check_type = check["type"]
        keywords = [k.lower() for k in check["keywords"]]
        reason = check["reason"]

        if check_type == "must_contain_any":
            passed = any(kw in text_lower for kw in keywords)
        elif check_type == "must_not_contain":
            passed = not any(kw in text_lower for kw in keywords)
        else:
            passed = False

        results.append(CheckResult(name=name, passed=passed, reason=reason))

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Scoring: LLM-as-Judge
# ══════════════════════════════════════════════════════════════════════════════

JUDGE_SYSTEM_PROMPT = """\
You are an expert evaluator of AI architecture recommendations. \
Score the following response on 6 dimensions (0-10 each). \
You MUST respond with ONLY a valid JSON object — no markdown, no explanation.

Dimensions:
1. correctness: Is the recommendation architecturally sound and appropriate?
2. specificity: Does it include version numbers, config details, specific APIs?
3. recency: Does it reflect the current (2026) state of the ecosystem?
4. known_issues: Does it warn about real production gotchas and limitations?
5. actionability: Can a developer immediately start coding from this? (pip install, imports, code)
6. hallucination_free: Does it avoid inventing non-existent features, wrong APIs, or false claims?

Respond with EXACTLY this JSON structure:
{"correctness": N, "specificity": N, "recency": N, "known_issues": N, "actionability": N, "hallucination_free": N}"""

JUDGE_USER_TEMPLATE = """\
## User Question
{question}

## Expert Ground Truth
{ground_truth}

## Response to Evaluate
{response}

Score this response (0-10 per dimension). Respond with JSON only."""


@dataclass
class JudgeScores:
    correctness: int = 0
    specificity: int = 0
    recency: int = 0
    known_issues: int = 0
    actionability: int = 0
    hallucination_free: int = 0

    @property
    def total(self) -> int:
        return (self.correctness + self.specificity + self.recency +
                self.known_issues + self.actionability + self.hallucination_free)

    @property
    def average(self) -> float:
        return self.total / 6.0


def judge_response(
    question: str,
    ground_truth: str,
    response_text: str,
    provider: str,
    model: str | None = None,
) -> Tuple[JudgeScores, int]:
    """Use LLM-as-judge to score a response. Returns (scores, judge_tokens_used)."""
    user_prompt = JUDGE_USER_TEMPLATE.format(
        question=question,
        ground_truth=ground_truth,
        response=response_text[:3000],  # Cap to avoid huge judge costs
    )

    judge_response = call_llm(
        system_prompt=JUDGE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        provider=provider,
        model=model,
    )

    # Parse JSON from judge response
    try:
        # Strip any markdown fencing
        text = judge_response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        scores_dict = json.loads(text)
        scores = JudgeScores(**{k: min(10, max(0, int(v))) for k, v in scores_dict.items()
                                if k in JudgeScores.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"  ⚠️  Judge parse error: {e}. Using zeros.")
        scores = JudgeScores()

    return scores, judge_response.total_tokens


# ══════════════════════════════════════════════════════════════════════════════
# Main Evaluation Loop
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScenarioResult:
    scenario_id: str
    prompt: str
    # Arm A (baseline)
    arm_a_response: str = ""
    arm_a_tokens: int = 0
    arm_a_input_tokens: int = 0
    arm_a_output_tokens: int = 0
    arm_a_latency_ms: int = 0
    arm_a_judge_scores: JudgeScores = field(default_factory=JudgeScores)
    arm_a_deterministic: List[CheckResult] = field(default_factory=list)
    # Arm B (TrueArch-augmented)
    arm_b_response: str = ""
    arm_b_tokens: int = 0
    arm_b_input_tokens: int = 0
    arm_b_output_tokens: int = 0
    arm_b_latency_ms: int = 0
    arm_b_judge_scores: JudgeScores = field(default_factory=JudgeScores)
    arm_b_deterministic: List[CheckResult] = field(default_factory=list)
    truearch_context_tokens: int = 0
    # Judge overhead
    judge_tokens_used: int = 0


def run_evaluation(
    provider: str = "gemini",
    model: str | None = None,
    scenarios: List[Scenario] | None = None,
) -> List[ScenarioResult]:
    """Run the full A/B evaluation across all scenarios."""
    scenarios = scenarios or SCENARIOS
    results = []

    print(f"\n{'='*70}")
    print(f"  TrueArch A/B Evaluation — {provider.upper()} ({model or 'default'})")
    print(f"  {len(scenarios)} scenarios × 2 arms + LLM-as-judge")
    print(f"{'='*70}\n")

    for i, scenario in enumerate(scenarios, 1):
        print(f"[{i}/{len(scenarios)}] {scenario.id}: {scenario.prompt[:60]}...")
        result = ScenarioResult(scenario_id=scenario.id, prompt=scenario.prompt)

        # ── Arm A: Baseline (no TrueArch) ─────────────────────────────────
        print(f"  Arm A (baseline)...", end=" ", flush=True)
        try:
            arm_a = call_llm(
                system_prompt=BASELINE_SYSTEM_PROMPT,
                user_prompt=scenario.prompt,
                provider=provider,
                model=model,
            )
            result.arm_a_response = arm_a.text
            result.arm_a_tokens = arm_a.total_tokens
            result.arm_a_input_tokens = arm_a.input_tokens
            result.arm_a_output_tokens = arm_a.output_tokens
            result.arm_a_latency_ms = arm_a.latency_ms
            print(f"✓ ({arm_a.total_tokens} tokens, {arm_a.latency_ms}ms)")
        except Exception as e:
            print(f"✗ Error: {e}")
            result.arm_a_response = f"ERROR: {e}"

        # Small delay to respect rate limits
        time.sleep(1)

        # ── Arm B: TrueArch-augmented ─────────────────────────────────────
        print(f"  Arm B (TrueArch)...", end=" ", flush=True)
        try:
            truearch_context, ctx_tokens = build_truearch_context(scenario)
            result.truearch_context_tokens = ctx_tokens

            system_prompt = TRUEARCH_SYSTEM_PROMPT_TEMPLATE.format(
                truearch_context=truearch_context
            )

            arm_b = call_llm(
                system_prompt=system_prompt,
                user_prompt=scenario.prompt,
                provider=provider,
                model=model,
            )
            result.arm_b_response = arm_b.text
            result.arm_b_tokens = arm_b.total_tokens
            result.arm_b_input_tokens = arm_b.input_tokens
            result.arm_b_output_tokens = arm_b.output_tokens
            result.arm_b_latency_ms = arm_b.latency_ms
            print(f"✓ ({arm_b.total_tokens} tokens, {arm_b.latency_ms}ms)")
        except Exception as e:
            print(f"✗ Error: {e}")
            result.arm_b_response = f"ERROR: {e}"

        time.sleep(1)

        # ── Deterministic checks ──────────────────────────────────────────
        result.arm_a_deterministic = run_deterministic_checks(
            result.arm_a_response, scenario.deterministic_checks
        )
        result.arm_b_deterministic = run_deterministic_checks(
            result.arm_b_response, scenario.deterministic_checks
        )

        a_passed = sum(1 for c in result.arm_a_deterministic if c.passed)
        b_passed = sum(1 for c in result.arm_b_deterministic if c.passed)
        total = len(scenario.deterministic_checks)
        print(f"  Deterministic: A={a_passed}/{total}, B={b_passed}/{total}")

        # ── LLM-as-Judge ──────────────────────────────────────────────────
        print(f"  Judging Arm A...", end=" ", flush=True)
        try:
            result.arm_a_judge_scores, j1_tokens = judge_response(
                question=scenario.prompt,
                ground_truth=scenario.ground_truth,
                response_text=result.arm_a_response,
                provider=provider,
                model=model,
            )
            result.judge_tokens_used += j1_tokens
            print(f"✓ (avg={result.arm_a_judge_scores.average:.1f}/10)")
        except Exception as e:
            print(f"✗ Error: {e}")

        time.sleep(1)

        print(f"  Judging Arm B...", end=" ", flush=True)
        try:
            result.arm_b_judge_scores, j2_tokens = judge_response(
                question=scenario.prompt,
                ground_truth=scenario.ground_truth,
                response_text=result.arm_b_response,
                provider=provider,
                model=model,
            )
            result.judge_tokens_used += j2_tokens
            print(f"✓ (avg={result.arm_b_judge_scores.average:.1f}/10)")
        except Exception as e:
            print(f"✗ Error: {e}")

        time.sleep(1)

        results.append(result)
        print()

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Report Generation
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(
    results: List[ScenarioResult],
    provider: str,
    model: str,
    output_path: Path,
) -> str:
    """Generate a Markdown evaluation report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# TrueArch A/B Evaluation Results",
        f"",
        f"**Date:** {now}  ",
        f"**Provider:** {provider} ({model})  ",
        f"**Scenarios:** {len(results)}  ",
        f"",
    ]

    # ── Aggregate Statistics ──────────────────────────────────────────────
    a_avgs = [r.arm_a_judge_scores.average for r in results]
    b_avgs = [r.arm_b_judge_scores.average for r in results]

    a_mean = sum(a_avgs) / len(a_avgs) if a_avgs else 0
    b_mean = sum(b_avgs) / len(b_avgs) if b_avgs else 0
    improvement = ((b_mean - a_mean) / a_mean * 100) if a_mean > 0 else 0

    a_total_tokens = sum(r.arm_a_tokens for r in results)
    b_total_tokens = sum(r.arm_b_tokens for r in results)
    truearch_overhead = sum(r.truearch_context_tokens for r in results)
    b_output_tokens = sum(r.arm_b_output_tokens for r in results)
    a_output_tokens = sum(r.arm_a_output_tokens for r in results)

    a_det_passed = sum(sum(1 for c in r.arm_a_deterministic if c.passed) for r in results)
    b_det_passed = sum(sum(1 for c in r.arm_b_deterministic if c.passed) for r in results)
    total_det = sum(len(r.arm_a_deterministic) for r in results)

    lines += [
        f"## Executive Summary",
        f"",
        f"| Metric | Baseline (no TrueArch) | TrueArch-Augmented | Delta |",
        f"|--------|----------------------|-------------------|-------|",
        f"| **Quality Score** (avg/10) | {a_mean:.1f} | {b_mean:.1f} | **{'+' if improvement >= 0 else ''}{improvement:.1f}%** |",
        f"| **Deterministic Checks** | {a_det_passed}/{total_det} | {b_det_passed}/{total_det} | {'+' if b_det_passed >= a_det_passed else ''}{b_det_passed - a_det_passed} |",
        f"| **Total Tokens** (all scenarios) | {a_total_tokens:,} | {b_total_tokens:,} | {'+' if b_total_tokens >= a_total_tokens else ''}{b_total_tokens - a_total_tokens:,} |",
        f"| **Output Tokens** (all scenarios) | {a_output_tokens:,} | {b_output_tokens:,} | {'+' if b_output_tokens >= a_output_tokens else ''}{b_output_tokens - a_output_tokens:,} |",
        f"| **TrueArch Context Overhead** | — | {truearch_overhead:,} tokens | — |",
        f"",
    ]

    # ── Verdict ───────────────────────────────────────────────────────────
    if improvement > 0:
        verdict = f"✅ TrueArch improved recommendation quality by **{improvement:.1f}%**"
    elif improvement == 0:
        verdict = "➡️ TrueArch produced equivalent quality"
    else:
        verdict = f"⚠️ TrueArch showed {improvement:.1f}% quality change"

    token_delta_pct = ((b_total_tokens - a_total_tokens) / a_total_tokens * 100) if a_total_tokens > 0 else 0
    if token_delta_pct > 10:
        token_verdict = f"with {token_delta_pct:.0f}% more total tokens (context injection overhead)"
    elif token_delta_pct < -5:
        token_verdict = f"while using {abs(token_delta_pct):.0f}% fewer total tokens"
    else:
        token_verdict = "with comparable token usage"

    lines += [
        f"> **Verdict:** {verdict} {token_verdict}.",
        f"",
    ]

    # ── Per-Scenario Quality Scores ───────────────────────────────────────
    lines += [
        f"## Per-Scenario Quality Scores",
        f"",
        f"| Scenario | Baseline Avg | TrueArch Avg | Δ | Winner |",
        f"|----------|-------------|-------------|---|--------|",
    ]

    for r in results:
        a_avg = r.arm_a_judge_scores.average
        b_avg = r.arm_b_judge_scores.average
        delta = b_avg - a_avg
        winner = "🟢 TrueArch" if delta > 0.5 else ("🔴 Baseline" if delta < -0.5 else "🟡 Tie")
        lines.append(
            f"| {r.scenario_id} | {a_avg:.1f} | {b_avg:.1f} | {'+' if delta >= 0 else ''}{delta:.1f} | {winner} |"
        )

    lines += [""]

    # ── Per-Dimension Breakdown ───────────────────────────────────────────
    dims = ["correctness", "specificity", "recency", "known_issues", "actionability", "hallucination_free"]
    lines += [
        f"## Per-Dimension Breakdown (averaged across all scenarios)",
        f"",
        f"| Dimension | Baseline | TrueArch | Δ |",
        f"|-----------|----------|----------|---|",
    ]
    for dim in dims:
        a_vals = [getattr(r.arm_a_judge_scores, dim) for r in results]
        b_vals = [getattr(r.arm_b_judge_scores, dim) for r in results]
        a_avg = sum(a_vals) / len(a_vals) if a_vals else 0
        b_avg = sum(b_vals) / len(b_vals) if b_vals else 0
        delta = b_avg - a_avg
        lines.append(f"| {dim} | {a_avg:.1f} | {b_avg:.1f} | {'+' if delta >= 0 else ''}{delta:.1f} |")

    lines += [""]

    # ── Deterministic Fact Checks ─────────────────────────────────────────
    lines += [
        f"## Deterministic Fact Checks",
        f"",
        f"| Scenario | Check | Baseline | TrueArch | Reason |",
        f"|----------|-------|----------|----------|--------|",
    ]
    for r in results:
        for a_check, b_check in zip(r.arm_a_deterministic, r.arm_b_deterministic):
            a_icon = "✅" if a_check.passed else "❌"
            b_icon = "✅" if b_check.passed else "❌"
            lines.append(f"| {r.scenario_id} | {a_check.name} | {a_icon} | {b_icon} | {a_check.reason} |")

    lines += [""]

    # ── Token Usage Detail ────────────────────────────────────────────────
    lines += [
        f"## Token Usage Detail",
        f"",
        f"| Scenario | A: Input | A: Output | A: Total | B: Input | B: Output | B: Total | TrueArch Ctx |",
        f"|----------|---------|----------|---------|---------|----------|---------|-------------|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario_id} | {r.arm_a_input_tokens:,} | {r.arm_a_output_tokens:,} | {r.arm_a_tokens:,} "
            f"| {r.arm_b_input_tokens:,} | {r.arm_b_output_tokens:,} | {r.arm_b_tokens:,} "
            f"| {r.truearch_context_tokens:,} |"
        )

    lines += [""]

    # ── Raw Responses (first 3 scenarios for manual review) ───────────────
    lines += [
        f"## Sample Raw Responses (first 3 scenarios)",
        f"",
    ]
    for r in results[:3]:
        lines += [
            f"### {r.scenario_id}: {r.prompt[:80]}...",
            f"",
            f"#### Arm A (Baseline)",
            f"```",
            r.arm_a_response[:1500] + ("..." if len(r.arm_a_response) > 1500 else ""),
            f"```",
            f"",
            f"#### Arm B (TrueArch-Augmented)",
            f"```",
            r.arm_b_response[:1500] + ("..." if len(r.arm_b_response) > 1500 else ""),
            f"```",
            f"",
        ]

    # ── Evaluation Metadata ───────────────────────────────────────────────
    judge_total = sum(r.judge_tokens_used for r in results)
    lines += [
        f"## Evaluation Metadata",
        f"",
        f"| Item | Value |",
        f"|------|-------|",
        f"| Provider | {provider} |",
        f"| Model | {model} |",
        f"| Scenarios | {len(results)} |",
        f"| Total LLM calls | {len(results) * 4} (2 arms + 2 judge calls per scenario) |",
        f"| Judge tokens used | {judge_total:,} |",
        f"| Total evaluation tokens | {a_total_tokens + b_total_tokens + judge_total:,} |",
        f"| Generated | {now} |",
    ]

    report = "\n".join(lines)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"\n📄 Report written to: {output_path}")

    return report


# ══════════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="TrueArch A/B Evaluation: Compare LLM output with vs without TrueArch."
    )
    parser.add_argument(
        "--provider", choices=["gemini", "openai"], default=None,
        help="LLM provider (auto-detected from env vars if not specified)"
    )
    parser.add_argument(
        "--model", default=None,
        help="Model name (default: gemini-2.0-flash / gpt-4o-mini)"
    )
    parser.add_argument(
        "--scenarios", default=None,
        help="Comma-separated scenario IDs to run (e.g. S01,S02,S08). Default: all"
    )
    parser.add_argument(
        "--output", default="benchmark/evaluation_results.md",
        help="Output path for the Markdown report"
    )
    args = parser.parse_args()

    # Auto-detect provider from env vars
    provider = args.provider
    if not provider:
        if os.environ.get("GOOGLE_API_KEY"):
            provider = "gemini"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        else:
            print("❌ Error: No API key found.")
            print("   Set GOOGLE_API_KEY or OPENAI_API_KEY environment variable.")
            print("   Or use --provider with the appropriate key set.")
            sys.exit(1)

    model = args.model or ("gemini-2.0-flash" if provider == "gemini" else "gpt-4o-mini")

    # Filter scenarios if requested
    scenarios = SCENARIOS
    if args.scenarios:
        ids = {s.strip().upper() for s in args.scenarios.split(",")}
        scenarios = [s for s in SCENARIOS if s.id in ids]
        if not scenarios:
            print(f"❌ No matching scenarios for: {args.scenarios}")
            sys.exit(1)

    # Run evaluation
    results = run_evaluation(provider=provider, model=model, scenarios=scenarios)

    # Generate report
    output_path = Path(args.output)
    generate_report(results, provider=provider, model=model, output_path=output_path)

    # Print summary
    a_avgs = [r.arm_a_judge_scores.average for r in results]
    b_avgs = [r.arm_b_judge_scores.average for r in results]
    a_mean = sum(a_avgs) / len(a_avgs) if a_avgs else 0
    b_mean = sum(b_avgs) / len(b_avgs) if b_avgs else 0

    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"  Baseline quality:    {a_mean:.1f}/10")
    print(f"  TrueArch quality:    {b_mean:.1f}/10")
    improvement = ((b_mean - a_mean) / a_mean * 100) if a_mean > 0 else 0
    print(f"  Quality improvement: {'+' if improvement >= 0 else ''}{improvement:.1f}%")
    print(f"  Report: {output_path.resolve()}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
