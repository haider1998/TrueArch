"""
Tests for the code pattern library (src/data/patterns.py).

Validates that:
  1. Every pattern has valid, non-empty fields
  2. version_range uses PEP 440 / pip-specifier syntax
  3. framework_id maps to a known framework in the data directory
  4. get_pattern() lookup works with both exact and partial use_case keys
  5. get_available_use_cases() returns non-empty lists for covered frameworks
  6. Snippets contain the expected key identifiers (API names, class names)
"""
import re
import os
import pytest

from src.data.patterns import (
    get_pattern,
    get_available_use_cases,
    get_all_patterns,
    get_supported_frameworks,
    CodePattern,
)
from src.data.loader import FrameworkLoader

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def known_framework_ids():
    """Load all real framework IDs from the YAML data directory."""
    data_dir = "data/frameworks" if os.path.exists("data/frameworks") else "../../data/frameworks"
    loader = FrameworkLoader(data_dir=data_dir)
    frameworks = loader.load_all()
    return set(frameworks.keys())


@pytest.fixture(scope="module")
def all_patterns():
    return get_all_patterns()


# ── Parametrized: every pattern in the library ───────────────────────────────

@pytest.mark.parametrize("pattern", get_all_patterns(), ids=lambda p: f"{p.framework_id}/{p.use_case}")
class TestEveryPattern:

    def test_framework_id_is_non_empty(self, pattern: CodePattern, known_framework_ids):
        assert pattern.framework_id, "framework_id must not be empty"

    def test_framework_id_is_known(self, pattern: CodePattern, known_framework_ids):
        assert pattern.framework_id in known_framework_ids, (
            f"Pattern framework_id '{pattern.framework_id}' is not a known framework. "
            f"Known: {sorted(known_framework_ids)}"
        )

    def test_use_case_is_non_empty(self, pattern: CodePattern, known_framework_ids):
        assert pattern.use_case, "use_case must not be empty"

    def test_use_case_is_snake_case(self, pattern: CodePattern, known_framework_ids):
        """use_case should be lowercase with underscores, no spaces."""
        assert re.match(r"^[a-z][a-z0-9_]*$", pattern.use_case), (
            f"use_case '{pattern.use_case}' should be snake_case (lowercase, underscores only)"
        )

    def test_version_range_is_valid_specifier(self, pattern: CodePattern, known_framework_ids):
        """version_range must be a valid pip specifier (>=X.Y.Z format)."""
        assert pattern.version_range, "version_range must not be empty"
        # Accept: >=X.Y.Z, >X, ==X.Y, ~=X.Y, >=X.Y.Z,<X+1
        assert re.match(r"^[><=~!]", pattern.version_range), (
            f"version_range '{pattern.version_range}' must start with a comparison operator "
            f"(>=, >, ==, ~=, !=, <)"
        )

    def test_description_is_non_empty(self, pattern: CodePattern, known_framework_ids):
        assert pattern.description, "description must not be empty"
        assert len(pattern.description) >= 20, "description must be at least 20 characters"

    def test_snippet_is_non_empty(self, pattern: CodePattern, known_framework_ids):
        assert pattern.snippet, "snippet must not be empty"
        assert len(pattern.snippet) >= 50, "snippet must be at least 50 characters"

    def test_snippet_is_valid_python(self, pattern: CodePattern, known_framework_ids):
        """Snippet must compile as valid Python (syntax check only)."""
        try:
            compile(pattern.snippet, "<snippet>", "exec")
        except SyntaxError as e:
            pytest.fail(
                f"Snippet for {pattern.framework_id}/{pattern.use_case} has a syntax error: {e}"
            )


# ── Lookup API tests ──────────────────────────────────────────────────────────

class TestGetPattern:

    def test_exact_use_case_key(self):
        result = get_pattern("langgraph", "checkpoint_sqlite")
        assert result is not None
        assert result.use_case == "checkpoint_sqlite"

    def test_partial_use_case_key(self):
        """Partial substring match should work — e.g. 'checkpoint' matches 'checkpoint_sqlite'."""
        result = get_pattern("langgraph", "checkpoint")
        assert result is not None
        assert "checkpoint" in result.use_case

    def test_partial_use_case_redis(self):
        result = get_pattern("langgraph", "redis")
        assert result is not None
        assert "redis" in result.use_case

    def test_case_insensitive_lookup(self):
        result = get_pattern("langgraph", "STREAMING")
        assert result is not None

    def test_unknown_framework_returns_none(self):
        result = get_pattern("totally_fake_framework", "anything")
        assert result is None

    def test_unknown_use_case_returns_none(self):
        result = get_pattern("langgraph", "definitely_not_a_use_case_xyz_abc")
        assert result is None

    def test_fastapi_lifespan_lookup(self):
        result = get_pattern("fastapi", "lifespan")
        assert result is not None
        assert "asynccontextmanager" in result.snippet

    def test_qdrant_init_lookup(self):
        result = get_pattern("qdrant", "init")
        assert result is not None
        assert "AsyncQdrantClient" in result.snippet

    def test_pydantic_ai_tool_lookup(self):
        result = get_pattern("pydantic_ai", "tool")
        assert result is not None
        assert "RunContext" in result.snippet


class TestGetAvailableUseCases:

    def test_langgraph_has_multiple_patterns(self):
        cases = get_available_use_cases("langgraph")
        assert len(cases) >= 3, f"Expected >=3 LangGraph patterns, got {len(cases)}: {cases}"

    def test_fastapi_has_patterns(self):
        cases = get_available_use_cases("fastapi")
        assert len(cases) >= 1

    def test_unknown_framework_returns_empty_list(self):
        cases = get_available_use_cases("nonexistent_framework")
        assert cases == []

    def test_returns_list_of_strings(self):
        cases = get_available_use_cases("langgraph")
        assert all(isinstance(c, str) for c in cases)


class TestGetSupportedFrameworks:

    def test_returns_multiple_frameworks(self):
        supported = get_supported_frameworks()
        assert len(supported) >= 5

    def test_langgraph_supported(self):
        assert "langgraph" in get_supported_frameworks()

    def test_fastapi_supported(self):
        assert "fastapi" in get_supported_frameworks()

    def test_sorted_alphabetically(self):
        supported = get_supported_frameworks()
        assert supported == sorted(supported)


# ── Snippet content spot checks ───────────────────────────────────────────────

class TestSnippetContent:
    """Verify that snippets contain expected key API identifiers."""

    def test_langgraph_sqlite_snippet_has_thread_id(self):
        p = get_pattern("langgraph", "checkpoint_sqlite")
        assert "thread_id" in p.snippet

    def test_langgraph_redis_snippet_is_async(self):
        p = get_pattern("langgraph", "checkpoint_redis")
        assert "async" in p.snippet

    def test_langgraph_step_budget_has_max_steps(self):
        p = get_pattern("langgraph", "step_budget")
        assert "MAX_STEPS" in p.snippet
        assert "recursion_limit" in p.snippet

    def test_langgraph_streaming_uses_v2(self):
        """The v2 streaming API must be used — the v1 API is deprecated."""
        p = get_pattern("langgraph", "streaming")
        assert 'version="v2"' in p.snippet or "version='v2'" in p.snippet

    def test_fastapi_lifespan_not_on_event(self):
        """FastAPI lifespan pattern must NOT use the deprecated @on_event pattern."""
        p = get_pattern("fastapi", "async_lifespan")
        assert "on_event" not in p.snippet, (
            "FastAPI snippet must use lifespan=, not the deprecated @app.on_event() pattern."
        )
        assert "asynccontextmanager" in p.snippet

    def test_langsmith_snippet_sets_env_before_import(self):
        """LangSmith env vars must be set before LangChain imports."""
        p = get_pattern("langsmith", "tracing")
        snippet = p.snippet
        env_pos = snippet.find("LANGCHAIN_TRACING_V2")
        import_pos = snippet.find("from langgraph")
        if import_pos >= 0:
            assert env_pos < import_pos, (
                "LangSmith snippet must set env vars BEFORE importing langgraph/langchain."
            )
