"""
TrueArch Code Validator — Post-generation hallucination killer.

Scans LLM-generated code snippets for:
  - Deprecated API calls (e.g., pinecone.init() → Pinecone())
  - Wrong import paths (e.g., langchain.chat_models → langchain_openai)
  - Version-specific pattern mismatches

This is the daily-loop hero tool: AI coding assistants call it immediately after
generating code to catch hallucinated or stale API patterns.

Patterns live in the framework YAML files (data/frameworks/*.yaml) under the
`deprecated_patterns` section — so the library scales with the catalog and the
signal pipeline can update it. This module is the matching engine.

Severity model:
  critical | high | medium  → violations (verdict escalates)
  advisory                  → notes (works, but a better pattern exists; never a violation)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.data.models import DeprecatedPattern


# ── Data Models ───────────────────────────────────────────────────────────────

class CodeViolation(BaseModel):
    """A single violation (or advisory) found in a code snippet."""
    pattern_id: str
    framework_id: str
    severity: str
    line_number: Optional[int]
    matched_text: str
    bad_example: str
    correct_example: str
    description: str
    docs_url: Optional[str] = None


class CodeValidationResult(BaseModel):
    """Full result of validating a code snippet."""
    framework_id: str
    violations_found: int
    has_critical: bool
    has_high: bool
    violations: List[CodeViolation]
    advisories: List[CodeViolation] = []
    verdict: str  # "clean" | "advisory" | "warnings" | "errors" | "critical"
    summary: str
    auto_fix_available: bool


# ── Pattern source (from framework YAML) ──────────────────────────────────────

# Frameworks injected by the server at startup (already loaded + validated).
# Falls back to loading from disk on first use for standalone / test contexts.
_FRAMEWORKS: Optional[Dict[str, Any]] = None


def set_frameworks(frameworks: Dict[str, Any]) -> None:
    """Inject the already-loaded framework catalog (called by the MCP server)."""
    global _FRAMEWORKS
    _FRAMEWORKS = frameworks


def _frameworks() -> Dict[str, Any]:
    global _FRAMEWORKS
    if _FRAMEWORKS is None:
        # Lazy fallback: load from disk (standalone use, tests).
        from src.data.loader import FrameworkLoader
        from src.data.paths import frameworks_dir

        _FRAMEWORKS = FrameworkLoader(data_dir=frameworks_dir()).load_all()
    return _FRAMEWORKS


def _patterns_for_framework(framework_id: str) -> List[DeprecatedPattern]:
    fw = _frameworks().get(framework_id)
    return list(fw.deprecated_patterns) if fw else []


def _all_patterns() -> List[DeprecatedPattern]:
    patterns: List[DeprecatedPattern] = []
    for fw in _frameworks().values():
        patterns.extend(fw.deprecated_patterns)
    return patterns


def _framework_id_for_pattern(pattern_id: str) -> str:
    """Reverse-lookup the owning framework id for a pattern (for cross-framework
    strict mode, where patterns from many frameworks are checked at once)."""
    for fid, fw in _frameworks().items():
        if any(p.id == pattern_id for p in fw.deprecated_patterns):
            return fid
    return "unknown"


# ── Version awareness ─────────────────────────────────────────────────────────

def _pattern_applies_to_version(pattern: DeprecatedPattern, version: Optional[str]) -> bool:
    """A deprecated pattern is only relevant if the user is on (or past) the
    version where the old API was removed/deprecated. On older versions the old
    API is still valid, so we don't flag it. Fails open on unparseable versions.
    """
    if not version:
        return True
    try:
        from packaging.version import Version, InvalidVersion

        try:
            user_v = Version(str(version).lstrip("^~>=< "))
            dep_v = Version(str(pattern.version_deprecated).lstrip("^~>=< "))
        except InvalidVersion:
            return True
        return user_v >= dep_v
    except Exception:
        return True


# ── Validator ─────────────────────────────────────────────────────────────────

def _find_line_number(code: str, match_start: int) -> int:
    """Return the 1-indexed line number for a match at `match_start` in `code`."""
    return code[:match_start].count("\n") + 1


def validate_code_snippet(
    code: str,
    framework_id: str,
    strict: bool = False,
    version: Optional[str] = None,
) -> CodeValidationResult:
    """
    Validate a code snippet against known deprecated patterns for a framework.

    Args:
        code:         The code string to validate.
        framework_id: Framework to check against (e.g., 'pinecone', 'langchain').
        strict:       If True, also check every other framework's patterns
                      (catches e.g. Pinecone v2 calls inside LangChain code).
        version:      Optional framework version the code targets. When given,
                      patterns for APIs not yet deprecated at that version are skipped.

    Returns:
        CodeValidationResult with all violations (and advisories) found.
    """
    if strict:
        candidate_patterns = _all_patterns()
    else:
        candidate_patterns = _patterns_for_framework(framework_id)

    violations: List[CodeViolation] = []
    advisories: List[CodeViolation] = []

    for pattern in candidate_patterns:
        if not _pattern_applies_to_version(pattern, version):
            continue
        try:
            compiled = re.compile(pattern.bad_pattern, re.MULTILINE)
        except re.error:
            # Should never happen (validated at load), but skip defensively.
            continue

        owner = framework_id if not strict else _framework_id_for_pattern(pattern.id)
        for match in compiled.finditer(code):
            item = CodeViolation(
                pattern_id=pattern.id,
                framework_id=owner,
                severity=pattern.severity,
                line_number=_find_line_number(code, match.start()),
                matched_text=match.group(0)[:120],
                bad_example=pattern.bad_example,
                correct_example=pattern.correct_example,
                description=pattern.description,
                docs_url=pattern.docs_url,
            )
            if pattern.severity == "advisory":
                advisories.append(item)
            else:
                violations.append(item)

    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    violations.sort(key=lambda v: sev_order.get(v.severity, 9))

    has_critical = any(v.severity == "critical" for v in violations)
    has_high = any(v.severity == "high" for v in violations)
    n = len(violations)

    if has_critical:
        verdict = "critical"
        summary = (
            f"🚨 {n} violation(s) found — {sum(1 for v in violations if v.severity == 'critical')} critical. "
            "This code uses APIs that were REMOVED in recent versions and WILL fail at runtime."
        )
    elif has_high:
        verdict = "errors"
        summary = "⚠️ {} violation(s) found — deprecated APIs that may fail or behave incorrectly.".format(n)
    elif n > 0:
        verdict = "warnings"
        summary = f"ℹ️ {n} warning(s) found — deprecated patterns that may cause issues in future versions."
    elif advisories:
        verdict = "advisory"
        summary = (
            f"✅ No deprecated APIs for {framework_id}, but {len(advisories)} advisory note(s) — "
            "the code works, but a stronger pattern is available."
        )
    else:
        verdict = "clean"
        summary = (
            f"✅ No known deprecated patterns detected for {framework_id}. "
            "Code uses current stable APIs."
        )

    return CodeValidationResult(
        framework_id=framework_id,
        violations_found=n,
        has_critical=has_critical,
        has_high=has_high,
        violations=violations,
        advisories=advisories,
        verdict=verdict,
        summary=summary,
        auto_fix_available=n > 0,  # corrections are always provided
    )


def list_checked_frameworks() -> List[Dict[str, Any]]:
    """Return a summary of which frameworks have validation patterns."""
    out: List[Dict[str, Any]] = []
    for fid, fw in _frameworks().items():
        patterns = fw.deprecated_patterns
        if not patterns:
            continue
        out.append({
            "framework_id": fid,
            "patterns": len(patterns),
            "critical": sum(1 for p in patterns if p.severity == "critical"),
            "high": sum(1 for p in patterns if p.severity == "high"),
            "advisory": sum(1 for p in patterns if p.severity == "advisory"),
        })
    return sorted(out, key=lambda x: x["framework_id"])
