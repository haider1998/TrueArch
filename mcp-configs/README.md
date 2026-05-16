# TrueArch MCP — Client Configuration Guide

> Connect any MCP-compatible AI coding assistant to TrueArch's centralized architecture intelligence.

---

## What TrueArch Gives Your AI Agent

Instead of your AI agent guessing at frameworks, it calls TrueArch once and gets:

- ✅ **Scored recommendations** — every framework rated across 5 dimensions
- ✅ **Architecture Genome™** — a unique fingerprint for your architectural decision (e.g. `MA-STAT-HOR-HIPAA-PY-MCP-REDIS`)
- ✅ **Known production issues** — curated real-world bugs and breaking changes
- ✅ **ADR output** — a committable Architecture Decision Record in Markdown
- ✅ **Deterministic** — same query = same answer on every machine

---

## Quick Setup (30 seconds)

### Cursor

1. Copy `cursor/mcp.json` to `.cursor/mcp.json` in your project root
2. Restart Cursor
3. Done — ask Cursor anything about your AI stack

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

1. Add to your `claude_desktop_config.json` (or use `claude-code/mcp.json`):

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

### Any MCP-Compatible Client

Point to: `https://smhrizvi281-truearch-mcp.hf.space/mcp`  
Transport: `streamable-http`  
Auth: None required (Phase 1 open access)

---

## Available Tools

Once connected, your AI agent has access to 6 tools:

| Tool | What It Does | Example Use |
|---|---|---|
| `recommend_ai_stack` | Full multi-layer stack recommendation with Genome + ADR | "What stack for HIPAA multi-agent?" |
| `compare_frameworks` | Head-to-head comparison across 5 scoring dimensions | "LangGraph vs CrewAI for my use case?" |
| `get_framework_score` | TrueArch score for a single framework | "What's LangGraph's current score?" |
| `get_recommendation` | Top frameworks in a category | "Best vector databases right now?" |
| `latest_stable_versions` | Pinned, verified versions for requirements.txt | "What version of FastAPI should I pin?" |
| `architecture_tradeoffs` | Known issues, compatibility, migration paths | "What are the risks of using CrewAI?" |

---

## Local Development (stdio)

If you're developing TrueArch locally, use the stdio config files (`mcp.local.json`):

```bash
# Install dependencies
pip install -r requirements.txt

# Test the MCP server locally
python -m src.mcp.server   # stdio mode (for IDE configs)
PORT=7860 python -m src.mcp.server --http   # HTTP mode on :7860
```

---

## Verify Connection

Once connected, ask your AI agent:
```
"Use TrueArch to recommend a stack for a multi-agent HIPAA patient support platform in Python"
```

You should get a structured response with scores, a Genome fingerprint, and an ADR.

---

## Architecture Genome™

Every recommendation includes a Genome code — the architectural fingerprint of your decision:

```
MA  - STAT - HOR  - HIPAA - PY  - MCP  - REDIS
↑     ↑      ↑      ↑       ↑     ↑      ↑
D1    D2     D3     D4      D5    D6     D7
Pattern Memory Scaling Compliance Lang Protocol Store
```

Teams with the same Genome can share architectural knowledge and ADRs.

---

*TrueArch — Decision Infrastructure for AI-Native Engineering*  
*[truearch.ai](https://truearch.ai) · [GitHub](https://github.com/TrueArchAI)*
