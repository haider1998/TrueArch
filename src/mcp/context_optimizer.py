"""
TrueArch Context Optimizer — Adaptive Context Compression.

Reduces token overhead by selecting only the most relevant sections of TrueArch
data for a given query, instead of dumping everything.

Design principles:
  - Query-aware: classifies intent → selects relevant sections
  - Token-budgeted: targets 400-600 tokens per query (down from 850+)
  - Anti-hallucination: wraps context with guardrail instructions
  - Confidence-tagged: marks data points as verified/estimated
"""
from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class QueryIntent(str, Enum):
    """Classified intent of the user's query."""
    FULL_STACK = "full_stack"            # "Build me a HIPAA agent system"
    COMPARISON = "comparison"             # "LangGraph vs CrewAI"
    EVALUATION = "evaluation"             # "Is AutoGen still good?"
    CODE_HELP = "code_help"              # "How do I set up checkpointing?"
    TROUBLESHOOT = "troubleshoot"         # "My LangGraph agent loops forever"
    MIGRATION = "migration"              # "Migrate from AutoGen to LangGraph"


# ── Guardrail Instructions ───────────────────────────────────────────────────

ANTI_HALLUCINATION_HEADER = """\
## ⚠️ IMPORTANT: Data Integrity Rules
- Use ONLY the TrueArch data below for scores and statistics. Do NOT invent raw score numbers or benchmarks.
- If a required version, installation command, or code example is not in the data below, you may use standard, verified software engineering knowledge to provide correct, stable instructions for the recommended framework.
- Data marked [estimated] should be cited as estimates, not facts.
- Data marked [verified] can be cited with confidence.
"""


ANTI_HALLUCINATION_FOOTER = """\
---
End of TrueArch data. Do NOT fabricate additional data points beyond what is listed above.
"""


# ── Intent Classification ────────────────────────────────────────────────────

_COMPARISON_PATTERNS = [
    r'\bvs\.?\b', r'\bversus\b', r'\bcompare\b', r'\bchoose between\b',
    r'\bwhich (?:one|is better)\b', r'\bor\b.*\bfor\b',
]

_EVALUATION_PATTERNS = [
    r'\bstill (?:a )?good\b', r'\bstill (?:worth|viable|recommended)\b',
    r'\bis .+ (?:dead|alive|maintained)\b', r'\bshould I (?:use|pick|choose)\b',
    r'\bwhat.*(?:status|state)\b',
]

_CODE_HELP_PATTERNS = [
    r'\bhow (?:do I|to|can I)\b', r'\bset up\b', r'\bconfigure\b',
    r'\bimplement\b', r'\bcode (?:example|snippet|pattern)\b',
    r'\bimport\b', r'\bpip install\b',
]

_TROUBLESHOOT_PATTERNS = [
    r'\berror\b', r'\bbug\b', r'\bcrash\b', r'\bfail\b', r'\bfix\b',
    r'\bloop(?:s|ing)?\b', r'\bperformance\b', r'\bslow\b', r'\bmemory\b',
]

_MIGRATION_PATTERNS = [
    r'\bmigrat\w*\b', r'\bswitch(?:ing)? (?:from|to)\b', r'\breplace\b',
    r'\balternative\b', r'\bmove (?:from|to|away)\b',
]


def classify_intent(query: str) -> QueryIntent:
    """Classify the user query into one of the known intents."""
    q = query.lower()

    # Check patterns in priority order (most specific first)
    for pattern in _MIGRATION_PATTERNS:
        if re.search(pattern, q):
            return QueryIntent.MIGRATION

    for pattern in _TROUBLESHOOT_PATTERNS:
        if re.search(pattern, q):
            return QueryIntent.TROUBLESHOOT

    for pattern in _CODE_HELP_PATTERNS:
        if re.search(pattern, q):
            return QueryIntent.CODE_HELP

    for pattern in _COMPARISON_PATTERNS:
        if re.search(pattern, q):
            return QueryIntent.COMPARISON

    for pattern in _EVALUATION_PATTERNS:
        if re.search(pattern, q):
            return QueryIntent.EVALUATION

    # Default: full stack recommendation
    return QueryIntent.FULL_STACK


# ── Section Selection ────────────────────────────────────────────────────────
# For each intent, define which sections of tool results are most relevant.

# Keys that should be kept per intent type
_INTENT_SECTIONS: Dict[QueryIntent, Dict[str, List[str]]] = {
    QueryIntent.FULL_STACK: {
        "recommend_ai_stack": [
            "layers", "genome_short", "confidence", "score_band",
            "context_brief", "staleness_warning",
        ],
        "compare_frameworks": ["overall_winner", "overall_winner_name", "recommendation", "when_to_pick_a", "when_to_pick_b", "dimensions"],
        "get_framework_score": ["scores", "known_issues_count", "critical_issues", "curation"],
        "explain_score": ["overall_score", "score_band", "dimensions"],
        "architecture_tradeoffs": ["known_issues", "compatible_with", "migration_paths"],
        "get_code_patterns": ["snippet", "version_range", "description"],
    },
    QueryIntent.COMPARISON: {
        "compare_frameworks": [
            "overall_winner", "overall_winner_name", "recommendation", "when_to_pick_a", "when_to_pick_b",
            "dimensions", "migration_note", "context_brief"
        ],
        "get_framework_score": ["scores", "version", "critical_issues", "curation"],
        "explain_score": ["overall_score", "dimensions", "confidence"],
    },
    QueryIntent.EVALUATION: {
        "get_framework_score": [
            "scores", "version", "category", "critical_issues",
            "known_issues_count", "staleness", "curation",
        ],
        "explain_score": [
            "overall_score", "score_band", "dimensions",
            "confidence_rationale", "curation",
            # NEW: migration advisory fields
            "migration_advisory", "recommended_alternatives", "superseded_by",
        ],
        "architecture_tradeoffs": [
            "known_issues", "migration_paths", "conflicts_with",
        ],
    },
    QueryIntent.CODE_HELP: {
        "get_code_patterns": ["snippet", "version_range", "description", "use_case"],
        "get_framework_score": ["version"],
        "architecture_tradeoffs": ["known_issues"],
    },
    QueryIntent.TROUBLESHOOT: {
        "architecture_tradeoffs": ["known_issues", "compatible_with", "conflicts_with"],
        "get_framework_score": ["version", "critical_issues"],
        "explain_score": ["dimensions"],
    },
    QueryIntent.MIGRATION: {
        "explain_score": [
            "overall_score", "dimensions",
            "migration_advisory", "recommended_alternatives", "superseded_by",
        ],
        "architecture_tradeoffs": [
            "migration_paths", "known_issues", "conflicts_with", "supersedes",
        ],
        "compare_frameworks": ["overall_winner", "overall_winner_name", "recommendation", "dimensions", "migration_note"],
        "get_framework_score": ["scores", "version", "curation"],
    },
}

_DEFAULT_TOOL_KEYS: Dict[str, List[str]] = {
    "recommend_ai_stack": [
        "layers", "genome_short", "confidence", "score_band",
        "context_brief", "staleness_warning",
    ],
    "compare_frameworks": [
        "overall_winner", "overall_winner_name", "recommendation",
        "when_to_pick_a", "when_to_pick_b", "dimensions",
        "migration_note", "context_brief"
    ],
    "get_framework_score": [
        "framework_id", "framework_name", "scores", "score_band",
        "version", "known_issues_count", "critical_issues", "staleness", "curation"
    ],
    "explain_score": [
        "framework_id", "framework_name", "overall_score", "score_band",
        "dimensions", "migration_advisory", "recommended_alternatives", "superseded_by"
    ],
    "architecture_tradeoffs": [
        "framework_id", "framework_name", "known_issues", "compatible_with",
        "conflicts_with", "migration_paths"
    ],
    "get_code_patterns": [
        "snippet", "version_range", "description", "use_case", "framework_id"
    ],
    "quick_context": [
        "brief", "framework_name", "overall_score"
    ]
}


def _select_keys(data: dict, allowed_keys: List[str]) -> dict:
    """Keep only allowed keys from a dict (one level deep)."""
    return {k: v for k, v in data.items() if k in allowed_keys}


def _add_confidence_tags(data: dict) -> dict:
    """Tag data points with confidence level for anti-hallucination."""
    tagged = {}
    for k, v in data.items():
        if isinstance(v, dict):
            tagged[k] = _add_confidence_tags(v)
        elif k in (
            "incident_rate", "star_growth_30d_pct", "job_postings_30d",
            "so_questions_30d", "commits_last_90d",
        ):
            tagged[f"{k} [estimated]"] = v
        elif k in (
            "github_stars", "latest_stable_version", "version",
            "breaking_changes_per_90d", "open_security_advisories",
            "hipaa_deployments", "soc2_deployments",
        ):
            tagged[f"{k} [verified]"] = v
        else:
            tagged[k] = v
    return tagged


def _score_to_band(score: Any) -> Any:
    try:
        val = float(score)
        if val >= 90: return "Excellent"
        if val >= 75: return "Strong"
        if val >= 60: return "Good"
        if val >= 45: return "Fair"
        if val >= 30: return "Weak"
        return "Poor"
    except (ValueError, TypeError):
        return score


def _sanitize_scores(obj: Any) -> Any:
    """Translate raw numerical score values in JSON payload to qualitative bands and strip delta/diff fields."""
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            if k in ("overall_score", "overall", "score") or k.endswith("_score"):
                new_dict[k] = _score_to_band(v)
            elif k in ("delta", "diff"):
                # Strip numeric delta/diff values
                continue
            elif k == "scores" and isinstance(v, dict):
                new_dict[k] = {sk: _score_to_band(sv) for sk, sv in v.items()}
            else:
                new_dict[k] = _sanitize_scores(v)
        return new_dict
    elif isinstance(obj, list):
        return [_sanitize_scores(item) for item in obj]
    else:
        return obj


def _reorder_known_issues(issues: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Reorder known issues so that those matching query keywords appear first."""
    if not isinstance(issues, list):
        return issues
    q_words = set(re.findall(r'\b\w+\b', query.lower()))
    
    def relevance_score(issue: Dict[str, Any]) -> int:
        if not isinstance(issue, dict):
            return 0
        score = 0
        desc = str(issue.get("description", "")).lower()
        cat = str(issue.get("category", "")).lower()
        workaround = str(issue.get("workaround", "")).lower()
        
        # Check for query words in description, category, and workaround
        for word in q_words:
            if len(word) < 3:
                continue
            if word in desc:
                score += 2
            if word in cat:
                score += 3
            if word in workaround:
                score += 1
                
        # Also give a boost for higher severity (critical=10, high=5, medium=2, low=0)
        sev = str(issue.get("severity", "")).lower()
        sev_boost = {"critical": 10, "high": 5, "medium": 2, "low": 0}.get(sev, 0)
        
        return score * 10 + sev_boost

    try:
        return sorted(issues, key=relevance_score, reverse=True)
    except Exception:
        return issues


def compress_context(
    tool_results: List[Dict[str, Any]],
    query: str,
    token_budget: int = 600,
) -> Tuple[str, int, QueryIntent]:
    """
    Compress TrueArch tool results based on query intent.

    Args:
        tool_results: List of {"tool": tool_name, "result": {...}} dicts
        query: The original user query
        token_budget: Target token count (approximate)

    Returns:
        (compressed_context_string, estimated_tokens, detected_intent)
    """
    intent = classify_intent(query)
    section_map = _INTENT_SECTIONS.get(intent, _INTENT_SECTIONS[QueryIntent.FULL_STACK])

    compressed_results = []
    for item in tool_results:
        tool_name = item.get("tool", "")
        result = item.get("result", {})

        if isinstance(result, dict) and "error" in result:
            # Keep errors as-is (they're short)
            compressed_results.append({"tool": tool_name, "result": result})
            continue

        # Determine allowed keys: merge intent-specific allowed keys with tool's fallback default keys
        intent_keys = section_map.get(tool_name, [])
        default_keys = _DEFAULT_TOOL_KEYS.get(tool_name, [])
        allowed_keys = list(set(intent_keys + default_keys))

        if allowed_keys and isinstance(result, dict):
            filtered = _select_keys(result, allowed_keys)
            # Reorder known issues if present in the filtered result
            if "known_issues" in filtered and isinstance(filtered["known_issues"], list):
                filtered["known_issues"] = _reorder_known_issues(filtered["known_issues"], query)
            if "critical_issues" in filtered and isinstance(filtered["critical_issues"], list):
                filtered["critical_issues"] = _reorder_known_issues(filtered["critical_issues"], query)
            tagged = _add_confidence_tags(filtered)
            compressed_results.append({"tool": tool_name, "result": tagged})
        else:
            # Tool not in intent map and no defaults — include minimal info
            if isinstance(result, dict):
                # Keep just the top-level summary keys
                minimal = {k: v for k, v in result.items()
                           if k in ("framework_id", "framework_name", "overall_score",
                                    "score_band", "version", "error")}
                if minimal:
                    compressed_results.append({"tool": tool_name, "result": minimal})

    # Sanitize numerical scores
    sanitized_results = _sanitize_scores(compressed_results)

    # Build the context string
    context_json = json.dumps(sanitized_results, indent=1, default=str)

    # If over budget, truncate individual results more aggressively
    estimated_tokens = len(context_json) // 4
    if estimated_tokens > token_budget * 1.5:
        # Second pass: remove verbose fields
        for item in sanitized_results:
            result = item.get("result", {})
            if isinstance(result, dict):
                # Remove long string values
                for k, v in list(result.items()):
                    if isinstance(v, str) and len(v) > 200:
                        result[k] = v[:200] + "..."
                    elif isinstance(v, list) and len(v) > 3:
                        result[k] = v[:3]

        context_json = json.dumps(sanitized_results, indent=1, default=str)
        estimated_tokens = len(context_json) // 4

    return context_json, estimated_tokens, intent



def build_augmented_prompt(
    context_json: str,
    intent: QueryIntent,
) -> str:
    """
    Wrap TrueArch context with anti-hallucination guardrails
    and intent-specific instructions.
    """
    intent_instructions = {
        QueryIntent.FULL_STACK: (
            "Recommend specific frameworks for each architectural layer. "
            "Use the scores, genome, and curation notes to justify choices. "
            "If any compared or recommended framework has production limitations or is "
            "curated as local/prototype-only (like Chroma), explicitly warn that it is not suitable for production scale."
        ),
        QueryIntent.COMPARISON: (
            "Compare the frameworks using the dimension scores and curation notes provided. "
            "Give a clear winner with specific reasons. If any compared framework is curated as "
            "local/prototype-only (like Chroma) or has production limitations, explicitly warn the developer about it."
        ),
        QueryIntent.EVALUATION: (
            "Evaluate the framework's current health using the scores and curation notes. "
            "If it has critical issues, low scores, or is curated as local/prototype-only (like Chroma), recommend alternatives."
        ),
        QueryIntent.CODE_HELP: (
            "Use the exact code patterns provided — they are version-verified. "
            "Do NOT modify import paths or API calls."
        ),
        QueryIntent.TROUBLESHOOT: (
            "Reference the known issues data to diagnose the problem. "
            "Provide the documented workaround if available."
        ),
        QueryIntent.MIGRATION: (
            "Use the migration paths and effort estimates to guide the migration. "
            "Reference alternatives with their scores."
        ),
    }

    instruction = intent_instructions.get(intent, intent_instructions[QueryIntent.FULL_STACK])

    return (
        f"{ANTI_HALLUCINATION_HEADER}\n"
        f"## Intent: {intent.value}\n"
        f"{instruction}\n\n"
        f"## TrueArch Intelligence Data\n\n"
        f"{context_json}\n\n"
        f"{ANTI_HALLUCINATION_FOOTER}"
    )
