"""
Tests for src/mcp/code_validator.py

Covers:
  - Detection of critical deprecated patterns (Pinecone v2, OpenAI v0)
  - Detection of high-severity patterns (LangChain imports, LangGraph compile)
  - Clean code produces no violations
  - Correct verdict strings
  - Framework coverage listing
"""
import pytest
from src.mcp.code_validator import (
    validate_code_snippet,
    list_checked_frameworks,
    CodeValidationResult,
    _frameworks,
)


def _all_patterns_with_owner():
    """(framework_id, pattern) for every deprecated_pattern in the catalog."""
    pairs = []
    for fid, fw in _frameworks().items():
        for p in fw.deprecated_patterns:
            pairs.append(pytest.param(fid, p, id=f"{fid}:{p.id}"))
    return pairs


# ── Pinecone Tests ────────────────────────────────────────────────────────────

class TestPineconeValidation:

    def test_detects_pinecone_init(self):
        code = """
import pinecone
pinecone.init(api_key='xxx', environment='us-east1-gcp')
index = pinecone.Index('my-index')
"""
        result = validate_code_snippet(code, "pinecone")
        assert result.violations_found >= 1
        assert result.has_critical is True
        assert result.verdict == "critical"
        ids = [v.pattern_id for v in result.violations]
        assert "PCN-001" in ids

    def test_detects_module_level_import(self):
        code = "import pinecone\n"
        result = validate_code_snippet(code, "pinecone")
        # bare `import pinecone` on its own line should trigger PCN-002
        assert result.violations_found >= 1
        ids = [v.pattern_id for v in result.violations]
        assert "PCN-002" in ids

    def test_detects_module_level_create_index(self):
        code = "pinecone.create_index('my-index', dimension=1536)\n"
        result = validate_code_snippet(code, "pinecone")
        assert any(v.pattern_id == "PCN-003" for v in result.violations)

    def test_clean_pinecone_code(self):
        code = """
from pinecone import Pinecone, ServerlessSpec
pc = Pinecone(api_key='xxx')
index = pc.Index('my-index')
"""
        result = validate_code_snippet(code, "pinecone")
        assert result.verdict == "clean"
        assert result.violations_found == 0

    def test_violations_sorted_by_severity(self):
        code = """
import pinecone
pinecone.init(api_key='xxx')
pinecone.create_index('idx', dimension=1536)
"""
        result = validate_code_snippet(code, "pinecone")
        sevs = [v.severity for v in result.violations]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        assert all(
            order[sevs[i]] <= order[sevs[i + 1]] for i in range(len(sevs) - 1)
        )


# ── LangChain Tests ───────────────────────────────────────────────────────────

class TestLangChainValidation:

    def test_detects_old_chat_models_import(self):
        code = "from langchain.chat_models import ChatOpenAI\n"
        result = validate_code_snippet(code, "langchain")
        assert result.violations_found >= 1
        assert any(v.pattern_id == "LCH-001" for v in result.violations)

    def test_detects_old_llms_import(self):
        code = "from langchain.llms import OpenAI\n"
        result = validate_code_snippet(code, "langchain")
        assert any(v.pattern_id == "LCH-002" for v in result.violations)

    def test_detects_old_embeddings_import(self):
        code = "from langchain.embeddings import OpenAIEmbeddings\n"
        result = validate_code_snippet(code, "langchain")
        assert any(v.pattern_id == "LCH-003" for v in result.violations)

    def test_detects_predict_method(self):
        code = 'result = chain.predict("hello")\n'
        result = validate_code_snippet(code, "langchain")
        assert any(v.pattern_id == "LCH-004" for v in result.violations)

    def test_clean_langchain_code(self):
        code = """
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
llm = ChatOpenAI(model="gpt-4o")
response = llm.invoke("Tell me a joke")
"""
        result = validate_code_snippet(code, "langchain")
        assert result.verdict == "clean"


# ── LangGraph Tests ───────────────────────────────────────────────────────────

class TestLangGraphValidation:

    def test_detects_memory_saver_import(self):
        code = "from langgraph.checkpoint.memory import MemorySaver\n"
        result = validate_code_snippet(code, "langgraph")
        assert any(v.pattern_id == "LGR-V-001" for v in result.violations)
        assert result.has_critical is True

    def test_detects_compile_without_checkpointer_as_advisory(self):
        # LGR-V-002 is advisory (stateless compile is legitimate) — it must be
        # reported as an advisory note, NOT a hard violation.
        code = "graph = builder.compile()\n"
        result = validate_code_snippet(code, "langgraph")
        assert any(a.pattern_id == "LGR-V-002" for a in result.advisories)
        assert not any(v.pattern_id == "LGR-V-002" for v in result.violations)
        assert result.verdict == "advisory"

    def test_compile_with_checkpointer_is_not_flagged(self):
        # Regression: the classic false positive must stay fixed.
        code = "graph = builder.compile(checkpointer=cp)\n"
        result = validate_code_snippet(code, "langgraph")
        assert result.violations_found == 0
        assert result.advisories == []
        assert result.verdict == "clean"

    def test_clean_langgraph_code(self):
        code = """
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
"""
        result = validate_code_snippet(code, "langgraph")
        assert result.violations_found == 0


# ── OpenAI SDK Tests ──────────────────────────────────────────────────────────

class TestOpenAIValidation:

    def test_detects_chat_completion_create(self):
        code = "response = openai.ChatCompletion.create(model='gpt-4', messages=[{'role': 'user', 'content': 'hi'}])\n"
        result = validate_code_snippet(code, "openai_sdk")
        assert result.has_critical is True
        assert any(v.pattern_id == "OAI-V-001" for v in result.violations)

    def test_detects_completion_create(self):
        code = "response = openai.Completion.create(engine='text-davinci-003', prompt='test')\n"
        result = validate_code_snippet(code, "openai_sdk")
        assert any(v.pattern_id == "OAI-V-002" for v in result.violations)

    def test_detects_api_key_assignment(self):
        code = "openai.api_key = 'sk-abc123'\n"
        result = validate_code_snippet(code, "openai_sdk")
        assert any(v.pattern_id == "OAI-V-003" for v in result.violations)
        assert result.has_high is True

    def test_clean_openai_sdk_code(self):
        code = """
from openai import OpenAI
client = OpenAI(api_key='sk-xxx')
response = client.chat.completions.create(model='gpt-4o', messages=[{'role': 'user', 'content': 'hi'}])
"""
        result = validate_code_snippet(code, "openai_sdk")
        assert result.verdict == "clean"


# ── Qdrant Tests ──────────────────────────────────────────────────────────────

class TestQdrantValidation:

    def test_detects_old_collection_name_in_constructor(self):
        code = "client = QdrantClient(url='http://localhost:6333', collection_name='my-col')\n"
        result = validate_code_snippet(code, "qdrant")
        assert any(v.pattern_id == "QDR-V-001" for v in result.violations)

    def test_detects_old_http_models_import(self):
        code = "from qdrant_client.http.models import Distance, VectorParams\n"
        result = validate_code_snippet(code, "qdrant")
        assert any(v.pattern_id == "QDR-V-002" for v in result.violations)


# ── Result Model Tests ────────────────────────────────────────────────────────

class TestValidationResultModel:

    def test_returns_code_validation_result(self):
        result = validate_code_snippet("import pinecone\npinecone.init()", "pinecone")
        assert isinstance(result, CodeValidationResult)

    def test_correct_example_always_present_on_violation(self):
        result = validate_code_snippet("import pinecone\npinecone.init(api_key='x')", "pinecone")
        for v in result.violations:
            assert v.correct_example, f"Missing correct_example for {v.pattern_id}"

    def test_violation_has_line_number(self):
        code = "line1\nline2\nimport pinecone\npinecone.init(api_key='x')\n"
        result = validate_code_snippet(code, "pinecone")
        critical = [v for v in result.violations if v.pattern_id == "PCN-001"]
        assert critical, "PCN-001 not detected"
        assert critical[0].line_number == 4

    def test_auto_fix_available_when_violations(self):
        result = validate_code_snippet("pinecone.init()", "pinecone")
        assert result.auto_fix_available is True

    def test_auto_fix_not_available_when_clean(self):
        code = "from pinecone import Pinecone\npc = Pinecone(api_key='x')\n"
        result = validate_code_snippet(code, "pinecone")
        assert result.auto_fix_available is False


# ── Framework Coverage Tests ──────────────────────────────────────────────────

class TestFrameworkCoverage:

    def test_list_checked_frameworks_returns_list(self):
        result = list_checked_frameworks()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_frameworks_have_required_keys(self):
        for fw in list_checked_frameworks():
            assert "framework_id" in fw
            assert "patterns" in fw
            assert fw["patterns"] > 0

    def test_pinecone_in_coverage(self):
        ids = [f["framework_id"] for f in list_checked_frameworks()]
        assert "pinecone" in ids

    def test_langchain_in_coverage(self):
        ids = [f["framework_id"] for f in list_checked_frameworks()]
        assert "langchain" in ids

    def test_openai_sdk_in_coverage(self):
        ids = [f["framework_id"] for f in list_checked_frameworks()]
        assert "openai_sdk" in ids


# ── Strict Mode Tests ─────────────────────────────────────────────────────────

class TestStrictMode:

    def test_strict_mode_catches_cross_framework(self):
        # LangChain code that also contains a Pinecone v2 call
        code = """
from langchain.chat_models import ChatOpenAI
import pinecone
pinecone.init(api_key='xxx')
"""
        result = validate_code_snippet(code, "langchain", strict=True)
        ids = [v.pattern_id for v in result.violations]
        # Should catch both langchain AND pinecone violations
        assert any("LCH" in pid for pid in ids)
        assert any("PCN" in pid for pid in ids)


# ── Self-verifying pattern library ────────────────────────────────────────────
# Every shipped pattern must (a) flag its own bad_example and (b) leave its own
# correct_example clean. This is what keeps the YAML pattern library trustworthy
# and maintainable as it grows across frameworks.

class TestPatternLibraryIsSelfConsistent:

    @pytest.mark.parametrize("framework_id,pattern", _all_patterns_with_owner())
    def test_bad_example_triggers_its_own_pattern(self, framework_id, pattern):
        result = validate_code_snippet(pattern.bad_example, framework_id)
        found = [v.pattern_id for v in result.violations] + [
            a.pattern_id for a in result.advisories
        ]
        assert pattern.id in found, (
            f"{pattern.id}: bad_example does not match its own bad_pattern regex."
        )

    @pytest.mark.parametrize("framework_id,pattern", _all_patterns_with_owner())
    def test_correct_example_does_not_trigger_its_own_pattern(self, framework_id, pattern):
        result = validate_code_snippet(pattern.correct_example, framework_id)
        found = [v.pattern_id for v in result.violations] + [
            a.pattern_id for a in result.advisories
        ]
        assert pattern.id not in found, (
            f"{pattern.id}: correct_example still matches the deprecated pattern "
            f"(false positive on the recommended fix)."
        )


# ── Version awareness ─────────────────────────────────────────────────────────

class TestVersionAwareness:

    def test_old_api_not_flagged_on_pre_deprecation_version(self):
        # pinecone.init() was removed in 3.0.0 — on 2.2.4 it is still valid.
        code = "import pinecone\npinecone.init(api_key='x')\n"
        result = validate_code_snippet(code, "pinecone", version="2.2.4")
        assert not any(v.pattern_id == "PCN-001" for v in result.violations)

    def test_old_api_flagged_on_post_deprecation_version(self):
        code = "import pinecone\npinecone.init(api_key='x')\n"
        result = validate_code_snippet(code, "pinecone", version="5.0.0")
        assert any(v.pattern_id == "PCN-001" for v in result.violations)

    def test_no_version_checks_everything(self):
        code = "pinecone.init(api_key='x')\n"
        result = validate_code_snippet(code, "pinecone")  # version=None
        assert any(v.pattern_id == "PCN-001" for v in result.violations)


# ── MCP tool wrapper (validate_code) ──────────────────────────────────────────

class TestValidateCodeMcpWrapper:

    def _tool(self):
        from src.mcp.server import validate_code
        return validate_code

    def test_unknown_framework_non_strict_returns_unchecked(self):
        result = self._tool()(code="foo()", framework_id="not_a_framework")
        assert result["verdict"] == "unchecked"
        assert "supported_frameworks" in result

    def test_known_framework_detects_violation(self):
        result = self._tool()(
            code="import pinecone\npinecone.init(api_key='x')", framework_id="pinecone"
        )
        assert result["verdict"] == "critical"
        assert result["violations_found"] >= 1

    def test_wrapper_passes_version_through(self):
        result = self._tool()(
            code="pinecone.init(api_key='x')", framework_id="pinecone", version="2.2.4"
        )
        # On 2.2.4 the init() call is still valid → no critical violation.
        assert result["verdict"] in ("clean", "advisory", "warnings")
