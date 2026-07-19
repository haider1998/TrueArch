# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TrueArch is an **MCP server** that keeps AI-generated framework code in sync with the
current world — real versions, current APIs, and validated code patterns for ~38 AI
frameworks. The MCP server (`src/mcp/server.py`) is the product; a REST API
(`src/api/main.py`) mirrors it. Knowledge lives in hand-curated YAML, not a database.

## Commands

The Makefile targets assume an activated venv; the interpreter is `./venv/bin/python`.

```bash
# Tests (535+). Prefer -q locally.
./venv/bin/python -m pytest tests/ -q
# A single test / class / file:
./venv/bin/python -m pytest tests/test_code_validator.py -q
./venv/bin/python -m pytest "tests/test_code_validator.py::TestPineconeValidation::test_detects_pinecone_init"
./venv/bin/python -m pytest tests/ -k staleness -q

# Run the MCP server
./venv/bin/python -m src.mcp.server            # stdio (IDE integration)
PORT=7860 ./venv/bin/python -m src.mcp.server --http   # HTTP: /health, /mcp
uvicorn src.api.main:app --reload --port 8000  # REST API + /docs

# Wire into Claude Code locally (see .mcp.json). uvx/PyPI aren't set up yet:
./venv/bin/pip install -e .    # provides the `truearch-mcp` console script
claude mcp list                # → truearch: ✓ Connected

# Refresh framework data (objective fields only; opens no PR locally)
./venv/bin/python -m scripts.signal_pipeline.pipeline      # crawl → data/signal_patches/*.json
./venv/bin/python -m scripts.signal_pipeline.apply_patch   # apply → data/frameworks/*.yaml

# Evaluations
./venv/bin/python benchmark/daily_loop_eval.py --limit 3   # real `claude` CLI; needs API credits
./venv/bin/python benchmark/ab_evaluation.py               # Gemini judge; needs GOOGLE_API_KEY

# Build the distributable wheel (bundles data/ alongside src/)
./venv/bin/python -m build --wheel
```

## Architecture (the parts that span files)

**Startup compute model.** Framework scores are NOT stored — YAML `computed_scores`
are `null`. At server boot, `FrameworkLoader` (`src/data/loader.py`) reads every
`data/frameworks/*.yaml` into a `FrameworkSchema` (`src/data/models.py`), then
`ScoringEngine` (`src/scoring/engine.py`) computes all scores in memory and caches
them on the framework objects. The catalog is the source of truth; scoring is
deterministic and derived. Never hand-edit scores.

**Two product tiers in `src/mcp/server.py`.** The *daily loop* (`validate_code`,
`latest_stable_versions`, `quick_context`) is the hero; the *depth layer*
(`recommend_ai_stack`, `compare_frameworks`, `generate_adr`, `genome_compare`, …) is
for standing up new systems. `quick_context`/`recommend_ai_stack` route through
`src/mcp/context_optimizer.py` (intent classification + token budgeting).

**`validate_code` is YAML-driven and self-verifying.** Deprecated-API patterns live
in each framework YAML under `deprecated_patterns` (schema in
`data/frameworks/schema.yaml`). `src/mcp/code_validator.py` sources patterns from the
loaded catalog — the server injects it via `set_frameworks(_frameworks)` at boot.
`severity: advisory` is reported as a note, not a violation. **Every pattern is
enforced by a parametrized test** (`tests/test_code_validator.py`): its `bad_example`
must match its own regex and its `correct_example` must not. Adding/editing a pattern
means keeping those two fields consistent, or the suite fails.

**Staleness is computed from real data age.** `ScoringEngine._determine_staleness`
keys off `curation.last_validated` + per-signal `signals_date`, never process-start
time — so "fresh/stale/expired" tells the truth even across restarts. `valid_until`
is `data_date + 30d`. This is deliberate; don't reset these to `today`.

**Freshness pipeline (objective vs subjective split).** `scripts/signal_pipeline/`
crawls GitHub/PyPI/npm → writes a JSON patch → `apply_patch.py` writes **only
objective fields** (versions, release dates, stars, advisory counts) back to YAML
using `ruamel.yaml` (preserves comments) and bumps `curation`. It never touches
subjective fields (breaking-change counts, known issues, `deprecated_patterns`). The
nightly Action (`.github/workflows/sync_versions.yml`) runs this and opens a **PR** —
it must never push generated data to `main`.

**Packaging & data resolution.** `pyproject.toml` (hatchling) ships `data/` alongside
`src/` in the wheel. `src/data/paths.py::frameworks_dir()` resolves the catalog
absolutely from `__file__` (honoring `TRUEARCH_DATA_DIR`), so the server finds YAMLs
whether run from a checkout or an installed wheel. Console script:
`truearch-mcp = src.mcp.server:run`.

**Telemetry is local-only.** `src/telemetry/storage.py` owns a SQLite DB
(`TRUEARCH_DB_PATH`); it stores a SHA-256 hash of the query, never the text.
`get_telemetry_insights` and `scripts/dashboard.py` read through it — don't reopen the
DB or query it directly.

**Two evaluations, different questions.** `benchmark/ab_evaluation.py` measures
architecture-*advice* quality (Gemini judge, static context injection).
`benchmark/daily_loop_eval.py` measures the daily loop by driving the real `claude`
CLI and grading generated code with `validate_code`. See
`benchmark/daily_loop_results.md` for the current, honest finding: modern models
already emit current APIs on popular frameworks, so the durable value is version/
change freshness, not deprecated-API catching.

## When you write framework code in this repo

TrueArch is wired in as an MCP server (`.mcp.json`). When you write or edit code using
any covered framework (Pinecone, LangGraph, LangChain, LlamaIndex, Qdrant, Weaviate,
Chroma, the OpenAI or Anthropic SDK, AutoGen, CrewAI, PydanticAI, FastAPI, Supabase,
Ollama):

1. Before finalizing, call `mcp__truearch__validate_code` with the snippet and
   `framework_id`; apply the `correct_example` fix until the verdict is `clean`.
2. Use `mcp__truearch__latest_stable_versions` when pinning versions — don't guess.
3. Use `mcp__truearch__quick_context` for a grounded brief before choosing a stack.

Don't trust training-data memory of these frameworks' APIs — that memory is exactly
what TrueArch exists to correct. (This section is also the "nudged" condition in the
daily-loop eval; keep it in sync with that experiment.)
