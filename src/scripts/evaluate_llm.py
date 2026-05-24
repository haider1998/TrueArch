"""
LLM Evaluation Framework for TrueArch

This script tests the context compression and token footprint of TrueArch MCP tools.
It ensures that the outputs provided to LLMs are compact, accurate, and do not waste tokens.
"""
import sys
import json
from typing import Dict, Any

from src.mcp.server import quick_context, recommend_ai_stack, _clean_dict
from src.recommendation.models import StackQuery

def estimate_tokens(data: Dict[str, Any]) -> int:
    """
    Rough heuristic for token estimation without bringing in a heavy tokenizer like tiktoken.
    Usually 1 token ~= 4 characters of JSON string.
    """
    json_str = json.dumps(data)
    return len(json_str) // 4


def evaluate_quick_context():
    """Evaluate if quick_context stays under the 200 token budget and contains critical info."""
    result = quick_context(
        problem="HIPAA compliant multi-agent healthcare assistant",
        compliance=["hipaa"],
        scale="enterprise"
    )
    
    tokens = estimate_tokens(result)
    print(f"[EVAL] quick_context token estimate: {tokens}")
    
    if tokens > 200:
        print(f"❌ FAILED: quick_context exceeds 200 tokens ({tokens})")
        return False
        
    if "context_brief" not in result:
        print(f"❌ FAILED: quick_context missing 'context_brief'")
        return False
        
    print("✅ PASSED: quick_context")
    return True


def evaluate_recommend_stack():
    """Evaluate if recommend_ai_stack stays under the 800 token budget."""
    result = recommend_ai_stack(
        problem="Large scale vector search with high momentum tools",
        scale="growth",
        priority="developer_speed"
    )
    
    tokens = estimate_tokens(result)
    print(f"[EVAL] recommend_ai_stack token estimate: {tokens}")
    
    if tokens > 800:
        print(f"❌ FAILED: recommend_ai_stack exceeds 800 tokens ({tokens})")
        return False
        
    # Check for empty dicts/lists that should have been stripped
    json_str = json.dumps(result)
    if "[]" in json_str or "{}" in json_str or "null" in json_str:
        print(f"❌ FAILED: Found empty structures or null in JSON output.")
        return False

    print("✅ PASSED: recommend_ai_stack")
    return True


def run_evaluations():
    print("Starting LLM Context Evaluation...")
    passed = 0
    total = 2
    
    if evaluate_quick_context(): passed += 1
    if evaluate_recommend_stack(): passed += 1
    
    print(f"\nEvaluation Results: {passed}/{total} passed.")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    run_evaluations()
