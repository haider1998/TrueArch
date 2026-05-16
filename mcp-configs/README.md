# TrueArch MCP — Client Configuration Guide

> Connect any MCP-compatible AI coding assistant to TrueArch's centralized architecture intelligence.  
> **Live endpoint:** `https://smhrizvi281-truearch-mcp.hf.space/mcp`

---

## Available Tools (once connected)

| Tool | What It Does |
|---|---|
| `recommend_ai_stack` | Full stack recommendation with Genome + ADR |
| `compare_frameworks` | Head-to-head across 5 scoring dimensions |
| `get_framework_score` | TrueArch score for a single framework |
| `get_recommendation` | Top frameworks in a category |
| `latest_stable_versions` | Pinned, verified versions for lockfiles |
| `architecture_tradeoffs` | Known issues, compatibility, migration paths |

---

## Antigravity (this AI assistant)

**Already added!** TrueArch is live in your Antigravity config at `~/.gemini/antigravity/mcp_config.json`. Restart Antigravity and TrueArch tools will appear automatically.

To add it to another machine, add this block to `~/.gemini/antigravity/mcp_config.json`:
```json
"truearch": {
  "command": "npx",
  "args": ["-y", "mcp-remote", "https://smhrizvi281-truearch-mcp.hf.space/mcp"]
}
```

---

## Cursor

Copy `cursor/mcp.json` to `.cursor/mcp.json` in your project root and restart Cursor:

```json
{
  "mcpServers": {
    "truearch": {
      "url": "https://smhrizvi281-truearch-mcp.hf.space/mcp"
    }
  }
}
```

---

## Claude Code

Add to `~/.claude/claude_desktop_config.json`:

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

---

## VS Code + GitHub Copilot

Create `.vscode/mcp.json` in your project root:

```json
{
  "servers": {
    "truearch": {
      "type": "http",
      "url": "https://smhrizvi281-truearch-mcp.hf.space/mcp"
    }
  }
}
```

This works for both **VS Code native MCP** and **GitHub Copilot Chat** (Copilot reads `.vscode/mcp.json` automatically). Alternatively, add to VS Code `settings.json`:

```json
{
  "github.copilot.chat.mcp.servers": {
    "truearch": {
      "type": "http",
      "url": "https://smhrizvi281-truearch-mcp.hf.space/mcp"
    }
  }
}
```

---

## Windsurf (Codeium)

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "truearch": {
      "serverUrl": "https://smhrizvi281-truearch-mcp.hf.space/mcp"
    }
  }
}
```

---

## Continue.dev

Add to `~/.continue/config.json`:

```json
{
  "mcpServers": [
    {
      "name": "truearch",
      "url": "https://smhrizvi281-truearch-mcp.hf.space/mcp"
    }
  ]
}
```

---

## Zed Editor

Add to `~/.config/zed/settings.json` (Zed uses stdio bridge via `mcp-remote`):

```json
{
  "context_servers": {
    "truearch": {
      "command": {
        "path": "npx",
        "args": ["-y", "mcp-remote", "https://smhrizvi281-truearch-mcp.hf.space/mcp"]
      }
    }
  }
}
```

---

## OpenAI Codex CLI

```bash
codex --mcp-server "https://smhrizvi281-truearch-mcp.hf.space/mcp" \
  "Recommend an AI stack for a HIPAA multi-agent platform"
```

Or add to `~/.codex/config.json`:
```json
{
  "mcpServers": [
    {
      "name": "truearch",
      "url": "https://smhrizvi281-truearch-mcp.hf.space/mcp"
    }
  ]
}
```

---

## Any MCP-Compatible Client

Point to: `https://smhrizvi281-truearch-mcp.hf.space/mcp`  
Transport: `streamable-http`  
Auth: None required (Phase 1 open access)

If your client only supports stdio, bridge via `mcp-remote`:
```bash
npx -y mcp-remote https://smhrizvi281-truearch-mcp.hf.space/mcp
```

---

## Local Development (stdio)

For developing TrueArch locally, use the stdio configs (`mcp.local.json`):

```bash
pip install -r requirements.txt
python -m src.mcp.server          # stdio mode for IDE configs
PORT=7860 python -m src.mcp.server --http  # HTTP mode on :7860
```

---

## Verify Connection

Once connected, ask your AI agent:
> *"Use TrueArch to recommend a stack for a multi-agent HIPAA patient support platform"*

You should get back a structured response with scores, an Architecture Genome fingerprint, and a committable ADR.

---

*TrueArch — Decision Infrastructure for AI-Native Engineering*
