import os
import sys
import asyncio
from typing import Optional
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from src.data.loader import FrameworkLoader
from src.scoring.engine import ScoringEngine

# Initialize standard components
server = Server("truearch-intelligence")

# Load data on start
base_dir = "." if os.path.exists("data/frameworks") else "../.."
data_dir = os.path.join(base_dir, "data/frameworks")

loader = FrameworkLoader(data_dir=data_dir)
engine = ScoringEngine()
frameworks_db = {}

def init_db():
    global frameworks_db
    if not frameworks_db:
        try:
            frameworks_db = loader.load_all()
            for fw in frameworks_db.values():
                fw.computed_scores = engine.compute_scores(fw)
        except Exception as e:
            # Log to stderr — MCP uses stdout for protocol messages
            print(f"[TrueArch MCP] ERROR loading framework data: {e}", file=sys.stderr)

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="get_framework_score",
            description="Get the detailed TrueArch score and confidence for a specific framework (e.g., 'langgraph', 'fastapi').",
            inputSchema={
                "type": "object",
                "properties": {
                    "framework_id": {
                        "type": "string",
                        "description": "The ID of the framework (e.g., langchain, fastapi)"
                    }
                },
                "required": ["framework_id"]
            }
        ),
        types.Tool(
            name="get_recommendation",
            description="Get the top recommended framework for a given category (e.g., 'orchestration', 'vector-db').",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "The category to search for (e.g., orchestration, vector-db, db, observability)"
                    }
                },
                "required": ["category"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str,
    arguments: Optional[dict] = None,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    init_db()

    # Guard against missing arguments
    args = arguments or {}

    if name == "get_framework_score":
        fw_id = args.get("framework_id")
        if not fw_id or fw_id not in frameworks_db:
            available = ", ".join(sorted(frameworks_db.keys()))
            return [types.TextContent(
                type="text",
                text=f"Framework '{fw_id}' not found. Available frameworks: {available}"
            )]
            
        fw = frameworks_db[fw_id]
        scores = fw.computed_scores
        
        result = (
            f"Framework: {fw.name} ({fw.id})\n"
            f"Category: {fw.category}\n"
            f"Overall Score: {scores.overall}/100 ({scores.score_band})\n"
            f"Confidence: {scores.confidence}%\n\n"
            f"Dimension Breakdown:\n"
            f"- Production Stability: {scores.production_stability}/100\n"
            f"- Ecosystem Momentum: {scores.ecosystem_momentum}/100\n"
            f"- Migration Risk: {scores.migration_risk}/100\n"
            f"- Governance Readiness: {scores.governance_readiness}/100\n"
            f"- Agent Compatibility: {scores.agent_compatibility}/100\n\n"
            f"Notes: {fw.curation.notes}"
        )
        return [types.TextContent(type="text", text=result)]
        
    elif name == "get_recommendation":
        category = args.get("category")
        candidates = [fw for fw in frameworks_db.values() if fw.category == category]
        
        if not candidates:
            cats = sorted(set(f.category for f in frameworks_db.values()))
            return [types.TextContent(
                type="text", 
                text=f"No frameworks found for category '{category}'. Available categories: {', '.join(cats)}"
            )]
            
        # Sort by overall score
        candidates.sort(key=lambda x: (x.computed_scores.overall or 0), reverse=True)
        top = candidates[0]
        
        result = (
            f"Top Recommendation for {category.upper()}:\n"
            f"🏆 {top.name} ({top.id})\n"
            f"Score: {top.computed_scores.overall}/100 ({top.computed_scores.score_band})\n"
            f"Confidence: {top.computed_scores.confidence}%\n\n"
            f"Why this is recommended:\n{top.curation.notes}\n\n"
        )
        
        if len(candidates) > 1:
            runner_up = candidates[1]
            result += f"Runner up: {runner_up.name} ({runner_up.computed_scores.overall}/100)\n"
            
        return [types.TextContent(type="text", text=result)]

    return [types.TextContent(
        type="text",
        text=f"Unknown tool: '{name}'. Available tools: get_framework_score, get_recommendation"
    )]

async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="truearch-intelligence",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
