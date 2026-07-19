# TrueArch Daily-Loop Evaluation — Real Results

**Date:** 2026-07-19
**Method:** Blind code generation by cold Claude subagents (no memory of TrueArch's
answer key), graded objectively by TrueArch's own `validate_code`. This substitutes
for the planned `claude -p` CLI harness ([daily_loop_eval.py](daily_loop_eval.py)),
which is blocked by "Credit balance is too low" on the CLI's API account.
**Models under test:** Claude Opus 4.8 and Claude Haiku 4.5 (both ~Jan 2026 cutoff).

> This is an honest, load-bearing negative result. Read the interpretation.

---

## Finding 1 — On popular frameworks, modern Claude models are already current

Six coding tasks, each a known deprecated-API trap, generated blind by each model,
then graded with `validate_code`:

| Task | Framework | Trap it could have hit | Opus 4.8 | Haiku 4.5 |
|---|---|---|---|---|
| Pinecone create + upsert | pinecone | `pinecone.init()` (removed v3) | ✅ clean | ✅ clean |
| OpenAI chat call | openai_sdk | `openai.ChatCompletion.create` | ✅ clean | ✅ clean |
| Weaviate nearest-objects | weaviate | `weaviate.Client()` / `query.get` (v3) | ✅ clean | ✅ clean |
| LangChain chat import | langchain | `langchain.chat_models` (moved v0.2) | ✅ clean | ✅ clean |
| AutoGen assistant | autogen | `from autogen import AssistantAgent` (v0.2) | ✅ clean | ✅ clean |
| Anthropic message | anthropic_sdk | `client.completions.create` | ✅ clean | ✅ clean |

**Deprecated-API violations: 0 / 6 for BOTH models.** Every model emitted the current
API unprompted (`from pinecone import Pinecone`, `client.chat.completions.create`,
`weaviate.connect_to_local()` + `collections.get(...).query.near_text`,
`langchain_openai`, `autogen_agentchat` + `.run()`, `messages.create`).

**Implication:** for *popular frameworks* + *frontier-cutoff Claude models*, the
"deprecated-API hallucination killer" catches almost nothing — the model already
knows. This is exactly the erosion the project's own VOUCH_BLUEPRINT predicted
("value shrinks as models improve"). We should NOT headline the daily loop as a
big win for this segment; that claim wouldn't survive contact with a skeptical
Claude Code user.

---

## Finding 2 — The durable edge is version freshness, not deprecated APIs

No model can know a version *released after its training cutoff*. TrueArch can.

TrueArch ground truth (`latest_stable_versions`, curated data):

| Framework | TrueArch version | Released | Data age |
|---|---|---|---|
| langgraph | 1.2.0 | 2026-05-11 | 64d |
| qdrant | 1.18.0 | 2026-05-01 | 64d |
| anthropic_sdk | 0.30.0 | 2026-05-08 | 64d |
| openai_sdk | 1.35.0 | 2026-05-10 | 64d |
| crewai | 1.14.4 | 2026-04-30 | 64d |
| langchain | 1.3.1 | 2026-05-15 | 64d |
| chroma | 1.5.9 | 2026-05-05 | 64d |

A model with a Jan 2026 cutoff cannot produce these May-2026 versions except by
luck. This is the value that does NOT erode as models improve — but it is entirely
contingent on **TrueArch's own data being fresh**. Note the data above is itself 64
days stale (past its review-due date), so today TrueArch would also give an outdated
pin. This makes the freshness automation (nightly refresh PRs) and the C3 refresh
not a nice-to-have but the core of the value.

*(The blind version-pinning arm was cut short by a session limit before returning
the model's guesses; notably, one subagent running with the repo CLAUDE.md
organically chose to call `latest_stable_versions` instead of guessing — a small
positive signal for tool-firing under the nudge. Re-run to complete this arm.)*

---

## Honest interpretation

- The **deprecated-API** pitch is weakest exactly where we'd most want to demo it
  (popular frameworks, best models). It is likely still valuable for: (a) weaker /
  older / non-Claude models many Cursor & Copilot users run (GPT-4o-mini, older
  Llama, older cutoffs) — untested here; (b) niche frameworks with little training
  signal; (c) APIs that changed *after* the model's cutoff.
- The **version-freshness** pitch is the durable, model-proof edge — but it lives
  or dies on TrueArch's data being fresh. Prioritize the refresh pipeline.
- Net: consider re-centering the headline from "stops hallucinated APIs" toward
  "keeps your agent current with the world after its training cutoff — versions
  first, breaking changes second," and prove it on weaker models + post-cutoff changes.

## Limitations
- Only Claude models tested (subagents); the most affected users run other/weaker
  models — untested here.
- Small N (6 frameworks), single run per model; no variance.
- Grading uses TrueArch's own validator (verifies avoidance of *known* patterns,
  not an independent oracle) — same caveat as the Gemini benchmark.
- Blind-subagent substitute for the real `claude -p` CLI harness (credit-blocked).

## To complete this evaluation
1. Fund the `claude` CLI (API credits) → run [daily_loop_eval.py](daily_loop_eval.py)
   for the organic-vs-nudged tool-firing rates, which subagents can't measure.
2. Add a weaker/non-Claude model arm (the segment most likely to hallucinate).
3. Add post-cutoff API-change tasks and a version-accuracy arm (Finding 2) to
   quantify the durable edge.
