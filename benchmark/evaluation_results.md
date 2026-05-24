# TrueArch A/B Evaluation Results

**Date:** 2026-05-24 15:04  
**Provider:** gemini (gemini-2.5-flash)  
**Scenarios:** 10  

## Executive Summary

| Metric | Baseline (no TrueArch) | TrueArch-Augmented | Delta |
|--------|----------------------|-------------------|-------|
| **Quality Score** (avg/10) | 5.5 | 7.0 | **+26.0%** |
| **Deterministic Checks** | 14/19 | 18/19 | +4 |
| **Total Tokens** (all scenarios) | 21,164 | 28,862 | +7,698 |
| **Output Tokens** (all scenarios) | 5,746 | 9,800 | +4,054 |
| **TrueArch Context Overhead** | — | 8,579 tokens | — |

> **Verdict:** ✅ TrueArch improved recommendation quality by **26.0%** with 36% more total tokens (context injection overhead).

## Per-Scenario Quality Scores

| Scenario | Baseline Avg | TrueArch Avg | Δ | Winner |
|----------|-------------|-------------|---|--------|
| S01 | 4.7 | 6.0 | +1.3 | 🟢 TrueArch |
| S02 | 4.0 | 5.0 | +1.0 | 🟢 TrueArch |
| S03 | 8.0 | 7.0 | -1.0 | 🔴 Baseline |
| S04 | 7.0 | 6.2 | -0.8 | 🔴 Baseline |
| S05 | 6.0 | 9.2 | +3.2 | 🟢 TrueArch |
| S06 | 2.8 | 8.5 | +5.7 | 🟢 TrueArch |
| S07 | 7.7 | 7.3 | -0.3 | 🟡 Tie |
| S08 | 2.0 | 7.8 | +5.8 | 🟢 TrueArch |
| S09 | 3.2 | 5.5 | +2.3 | 🟢 TrueArch |
| S10 | 9.8 | 7.0 | -2.8 | 🔴 Baseline |

## Per-Dimension Breakdown (averaged across all scenarios)

| Dimension | Baseline | TrueArch | Δ |
|-----------|----------|----------|---|
| correctness | 5.8 | 7.6 | +1.8 |
| specificity | 5.1 | 7.7 | +2.6 |
| recency | 6.4 | 8.4 | +2.0 |
| known_issues | 2.9 | 4.3 | +1.4 |
| actionability | 4.6 | 7.6 | +3.0 |
| hallucination_free | 8.3 | 6.1 | -2.2 |

## Deterministic Fact Checks

| Scenario | Check | Baseline | TrueArch | Reason |
|----------|-------|----------|----------|--------|
| S01 | no_autogen_for_enterprise | ✅ | ✅ | AutoGen is in maintenance mode and must not be recommended for new enterprise projects |
| S01 | hipaa_awareness | ✅ | ✅ | HIPAA query must mention HIPAA compliance requirements |
| S02 | knows_langgraph_is_graph_based | ✅ | ✅ | Must know LangGraph's core differentiator |
| S02 | knows_crewai_is_role_based | ✅ | ✅ | Must know CrewAI's paradigm |
| S03 | no_chroma_for_enterprise | ✅ | ✅ | Chroma is prototype-only, must not be recommended for 10M+ docs |
| S03 | mentions_vector_db | ✅ | ✅ | RAG at scale needs a production vector DB |
| S04 | multi_agent_capable | ❌ | ✅ | Must recommend a multi-agent capable orchestrator |
| S05 | correct_checkpoint_api | ✅ | ✅ | Must use correct LangGraph checkpoint API |
| S05 | knows_bloat_issue | ❌ | ✅ | Must warn about checkpoint bloat (LGR-001) |
| S06 | correct_otel_imports | ✅ | ✅ | Must use correct OpenTelemetry API |
| S06 | has_pip_install | ✅ | ✅ | Must include installation instructions |
| S07 | production_vector_db | ✅ | ✅ | Must recommend a production-grade vector DB |
| S07 | no_chroma_solo | ✅ | ✅ | Chroma is prototype-only for 50M+ vectors |
| S08 | knows_maintenance_mode | ❌ | ✅ | CRITICAL: Must know AutoGen is in maintenance mode |
| S08 | suggests_alternatives | ❌ | ❌ | Must suggest modern alternatives |
| S09 | mentions_mcp | ❌ | ✅ | Query explicitly asks about MCP — must address it |
| S09 | mentions_memory | ✅ | ✅ | Query asks about persistent memory |
| S10 | chroma_limitation | ✅ | ✅ | Must note Chroma's production limitations |
| S10 | correct_pinecone_api | ✅ | ✅ | Must NOT use deprecated Pinecone v2 API (pinecone.init) |

## Token Usage Detail

| Scenario | A: Input | A: Output | A: Total | B: Input | B: Output | B: Total | TrueArch Ctx |
|----------|---------|----------|---------|---------|----------|---------|-------------|
| S01 | 75 | 80 | 2,119 | 1,169 | 1,304 | 3,213 | 912 |
| S02 | 71 | 678 | 2,115 | 1,173 | 757 | 2,810 | 871 |
| S03 | 76 | 719 | 2,120 | 1,093 | 794 | 3,137 | 788 |
| S04 | 68 | 845 | 2,112 | 1,078 | 1,745 | 3,122 | 793 |
| S05 | 69 | 627 | 2,113 | 1,498 | 908 | 2,770 | 1,307 |
| S06 | 70 | 80 | 2,114 | 654 | 1,136 | 2,698 | 434 |
| S07 | 73 | 559 | 2,117 | 1,089 | 848 | 2,197 | 788 |
| S08 | 71 | 802 | 2,115 | 1,349 | 387 | 2,347 | 933 |
| S09 | 76 | 81 | 2,120 | 1,088 | 950 | 3,134 | 795 |
| S10 | 75 | 1,275 | 2,119 | 1,390 | 971 | 3,434 | 958 |

## Sample Raw Responses (first 3 scenarios)

### S01: I need to build a HIPAA-compliant multi-agent healthcare assistant that handles ...

#### Arm A (Baseline)
```
Building a HIPAA-compliant multi-agent healthcare assistant requires a robust, secure, and auditable technology stack. My recommendation prioritizes security, compliance, scalability, and developer efficiency.

---

### Recommended Technology Stack

1.  **Cloud Provider:** **AWS (Amazon Web Services)**
    *   **Justification:** AWS offers the most mature and comprehensive suite of HIPAA-eligible services,
```

#### Arm B (TrueArch-Augmented)
```
For your HIPAA-compliant multi-agent healthcare assistant, you must use the following technology stack:

### Recommended Technology Stack

1.  **Orchestration: LangGraph (v1.2.0)**
    *   **Reasoning:** Provides native multi-agent and Message Passing Interface (MCP) support, crucial for complex agent interactions. It has verified HIPAA deployments and a strong governance posture.
    *   **Installation:**
        ```bash
        pip install langgraph==1.2.0
        ```
    *   **Example (Basic Graph Definition):**
        ```python
        from langgraph.graph import StateGraph, END

        class AgentState:
            messages: list

        graph_builder = StateGraph(AgentState)
        graph_builder.add_node("agent", lambda state: {"messages": state["messages"] + ["Agent processed"]})
        graph_builder.add_node("tool", lambda state: {"messages": state["messages"] + ["Tool executed"]})
        graph_builder.add_edge("agent", "tool")
        graph_builder.add_edge("tool", END)
        graph_builder.set_entry_point("agent")
        graph = graph_builder.compile()
        ```

2.  **Vector Database: PostgreSQL + pgvector (pgvector v0.8.2)**
    *   **Reasoning:** Offers production-grade reliability and is explicitly verified for HIPAA deployments with a strong governance posture. Leveraging an existing robust relational database for vector capabilities is highly efficient.
    *   **Installation:**
        *   **PostgreSQL:** Install PostgreSQL server (e.g., `sudo apt-g...
```

### S02: Should I use LangGraph or CrewAI for my AI agent orchestration layer in 2026?...

#### Arm A (Baseline)
```
For 2026, **LangGraph** is the superior choice for your AI agent orchestration layer.

While CrewAI offers a compelling high-level abstraction for defining teams of agents, LangGraph provides the foundational flexibility, control, and durability required for robust, production-grade AI systems that will evolve over time.

**Recommendation: LangGraph**

**Why LangGraph?**

1.  **Granular Control & Flexibility:** LangGraph allows you to define explicit state machines, giving you precise control over every transition, tool call, and LLM interaction. This is critical for handling complex logic, error recovery, human-in-the-loop scenarios, and optimizing performance. CrewAI's reliance on prompt-driven delegation, while intuitive, can become less deterministic and harder to debug for intricate workflows.
2.  **Durability & Ecosystem:** Built directly on LangChain, LangGraph benefits from a more mature, widely adopted, and actively developed ecosystem. LangChain's extensive integrations (models, tools, retrievers, memory) are directly accessible and seamlessly integrated. This ensures better long-term support and a richer set of components.
3.  **Debugging & Observability:** The graph-based structure of LangGraph makes workflows inherently more inspectable and debuggable. You can visualize the flow, trace execution paths, and pinpoint exactly where issues occur, which is paramount for production systems.
4.  **Scalability & Optimization:** With explicit state management, you have mo...
```

#### Arm B (TrueArch-Augmented)
```
For your AI agent orchestration layer in 2026, **TrueArch decisively recommends LangGraph.**

LangGraph significantly outperforms CrewAI across critical dimensions, making it the superior choice for production environments.

**Key Reasons for LangGraph:**

1.  **Agent Compatibility (Native Multi-Agent):** LangGraph leads by a substantial 36.2 points in Agent Compatibility, offering native support for true multi-agent orchestration. This is crucial for building sophisticated AI agent systems.
2.  **Production Stability:** With fewer breaking changes (2 per 90 days vs. CrewAI's 4) and a 17.2-point lead, LangGraph offers greater stability for your production deployments.
3.  **Governance Readiness:** LangGraph provides better audit support (plugin) and a 16.3-point lead, which is essential for compliance requirements like HIPAA, SOC 2, and GDPR.
4.  **Ecosystem Momentum:** LangGraph shows stronger growth (+4.5%/mo stars vs. +1.8%/mo for CrewAI), indicating a more vibrant and evolving ecosystem.
5.  **Migration Risk:** LangGraph scores higher, meaning it's easier to migrate away from if future needs change, offering better long-term flexibility.

**When to use LangGraph:**
*   Your system requires **true multi-agent orchestration**.
*   You need high concurrency or streaming responses.
*   Compliance (HIPAA, SOC 2, GDPR) and audit trails are critical.

**Installation:**
To get started with LangGraph, ensure you have Python 3.9+ and install it via pip:

```bash
pip install -U lang...
```

### S03: I need to set up a RAG pipeline for enterprise document search over 10M+ documen...

#### Arm A (Baseline)
```
For a RAG pipeline over 10M+ enterprise documents, you need a robust, scalable, and performant stack. My clear recommendation is:

**Qdrant + BGE-large + LangChain + OpenAI (GPT-4-Turbo)**

This combination offers excellent retrieval quality, scalability, and developer experience.

---

### 1. Document Ingestion & Preprocessing

*   **Tool:** `unstructured.io` for parsing, `LangChain` for chunking.
*   **Why:** `unstructured.io` excels at extracting clean text and metadata from diverse enterprise document formats (PDFs, DOCX, HTML, etc.), handling complex layouts. `LangChain` provides battle-tested text splitters.
*   **Versions:**
    *   `unstructured==0.12.6`
    *   `langchain-text-splitters==0.0.1`
    *   `langchain-community==0.0.29` (for document loaders)
*   **Installation:**
    ```bash
    pip install unstructured==0.12.6 "unstructured[pdf,docx]" langchain-text-splitters==0.0.1 langchain-community==0.0.29
    ```
*   **Action:** Use `unstructured.Partition` for initial parsing, then `RecursiveCharacterTextSplitter` for chunking.

### 2. Embedding Model

*   **Model:** `BAAI/bge-large-en-v1.5`
*   **Tool:** `sentence-transformers`
*   **Why:** `bge-large-en-v1.5` is a top-performing open-source embedding model, offering excellent semantic search capabilities. `sentence-transformers` provides an easy-to-use interface.
*   **Versions:**
    *   `sentence-transformers==2.2.2`
    *   `torch==2.2.1` (or compatible with your CUDA setup)
*   **Installation:**
    ```bash
...
```

#### Arm B (TrueArch-Augmented)
```
For an enterprise document search RAG pipeline over 10M+ documents, I recommend the following production-ready stack:

### Recommended AI Stack

1.  **Orchestration (RAG Flow): LangGraph `1.2.0`**
    *   **Reason:** LangGraph provides robust capabilities for building complex, multi-step RAG workflows, including multi-agent patterns, which are crucial for sophisticated enterprise search. Its strong overall score and native multi-agent support make it ideal for orchestrating retrieval, re-ranking, and generation steps.
    *   **Installation:**
        ```bash
        pip install langgraph==1.2.0 langchain==0.2.11 langchain-core==0.2.20
        ```
    *   **Example (Basic Node):**
        ```python
        from langgraph.graph import StateGraph, END

        class AgentState:
            query: str
            documents: list = []
            answer: str = ""

        def retrieve(state: AgentState):
            print("Retrieving documents...")
            # Placeholder for actual retrieval logic using Qdrant
            return {"documents": ["doc1_content", "doc2_content"]}

        def generate(state: AgentState):
            print("Generating answer...")
            # Placeholder for LLM call
            return {"answer": f"Answer based on: {state.documents[0]}"}

        workflow = StateGraph(AgentState)
        workflow.add_node("retrieve", retrieve)
        workflow.add_node("generate", generate)
        workflow.set_entry_point("retrieve")
        workflow.add_edge("re...
```

## Evaluation Metadata

| Item | Value |
|------|-------|
| Provider | gemini |
| Model | gemini-2.5-flash |
| Scenarios | 10 |
| Total LLM calls | 40 (2 arms + 2 judge calls per scenario) |
| Judge tokens used | 48,202 |
| Total evaluation tokens | 98,228 |
| Generated | 2026-05-24 15:04 |