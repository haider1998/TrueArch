#!/usr/bin/env python3
"""
TrueArch daily-loop evaluation — the real Claude Code, graded objectively.

For each trap task (benchmark/daily_loop_tasks.yaml) this drives the actual
`claude` CLI headlessly in three arms:

  baseline          — TrueArch NOT available (--strict-mcp-config + empty config)
  truearch_organic  — TrueArch tools available, no nudge (does Claude call them?)
  truearch_nudged   — TrueArch tools available + a system-prompt rule to validate

It then grades each arm's generated code with TrueArch's own `validate_code`
(counting deprecated-API violations), and detects whether the agent actually
called any `mcp__truearch__*` tool. Results → benchmark/daily_loop_results.md.

Honesty note: grading with our own validator verifies "avoids known-bad patterns"
(the exact product claim), not an independent oracle. `claude` runs have run-to-run
variance — use --repeats for a more stable estimate.

Usage:
    python benchmark/daily_loop_eval.py --limit 3        # cheap pilot
    python benchmark/daily_loop_eval.py                  # full run
    python benchmark/daily_loop_eval.py --repeats 3 --model sonnet
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.mcp.code_validator import validate_code_snippet  # noqa: E402

_TASKS_FILE = _ROOT / "benchmark" / "daily_loop_tasks.yaml"
_EMPTY_MCP = _ROOT / "benchmark" / "_empty_mcp.json"
_TRUEARCH_MCP = _ROOT / ".mcp.json"
_RESULTS_FILE = _ROOT / "benchmark" / "daily_loop_results.md"

_TRUEARCH_TOOLS = [
    "mcp__truearch__validate_code",
    "mcp__truearch__latest_stable_versions",
    "mcp__truearch__quick_context",
]

_NUDGE = (
    "When you write code that uses an AI framework, call the TrueArch "
    "validate_code tool on it before finalizing and apply any fixes it reports. "
    "Use latest_stable_versions when pinning dependency versions. Do not rely on "
    "your training-data memory of these frameworks' APIs."
)

# Keep the agent from writing files — we only want code in its reply.
_NO_EDIT_TOOLS = ["Write", "Edit", "MultiEdit", "NotebookEdit"]

_CODE_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)


@dataclass
class ArmResult:
    arm: str
    final_text: str = ""
    code: str = ""
    violations: int = 0
    violation_ids: List[str] = field(default_factory=list)
    advisories: int = 0
    verdict: str = "n/a"
    tools_called: List[str] = field(default_factory=list)
    cost_usd: float = 0.0
    error: Optional[str] = None

    @property
    def called_truearch(self) -> bool:
        return any(t.startswith("mcp__truearch__") for t in self.tools_called)


def _load_tasks(limit: Optional[int]) -> List[Dict[str, Any]]:
    tasks = yaml.safe_load(_TASKS_FILE.read_text())["tasks"]
    return tasks[:limit] if limit else tasks


def _run_claude(prompt: str, arm: str, model: str, budget: float, timeout: int) -> ArmResult:
    """Run one arm through the headless claude CLI and parse the stream-json."""
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--model", model,
        "--max-budget-usd", str(budget),
        "--permission-mode", "bypassPermissions",
        "--disallowedTools", *_NO_EDIT_TOOLS,
    ]
    if arm == "baseline":
        cmd += ["--strict-mcp-config", "--mcp-config", str(_EMPTY_MCP)]
    else:
        cmd += ["--strict-mcp-config", "--mcp-config", str(_TRUEARCH_MCP),
                "--allowedTools", *_TRUEARCH_TOOLS]
        if arm == "truearch_nudged":
            cmd += ["--append-system-prompt", _NUDGE]

    res = ArmResult(arm=arm)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(_ROOT)
        )
    except subprocess.TimeoutExpired:
        res.error = f"timeout after {timeout}s"
        return res
    except FileNotFoundError:
        res.error = "`claude` CLI not found on PATH"
        return res

    if proc.returncode != 0 and not proc.stdout.strip():
        res.error = f"claude exited {proc.returncode}: {proc.stderr[:300]}"
        return res

    # Parse newline-delimited JSON events.
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type")
        if etype == "assistant":
            for block in evt.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    res.tools_called.append(block.get("name", "?"))
        elif etype == "result":
            res.final_text = evt.get("result") or res.final_text
            res.cost_usd = float(evt.get("total_cost_usd") or 0.0)
            if evt.get("is_error"):
                # e.g. "Credit balance is too low", rate limits, budget exceeded.
                res.error = f"claude error: {(evt.get('result') or 'unknown')[:120]}"

    return res


def _grade(res: ArmResult, framework_id: str) -> None:
    """Extract code from the reply and grade it with validate_code."""
    blocks = _CODE_FENCE.findall(res.final_text)
    res.code = "\n\n".join(blocks).strip()
    if not res.code:
        res.verdict = "no_code"
        return
    result = validate_code_snippet(res.code, framework_id)
    res.violations = result.violations_found
    res.violation_ids = [v.pattern_id for v in result.violations]
    res.advisories = len(result.advisories)
    res.verdict = result.verdict


def run(limit: Optional[int], repeats: int, model: str, budget: float, timeout: int) -> Dict[str, Any]:
    tasks = _load_tasks(limit)
    arms = ["baseline", "truearch_organic", "truearch_nudged"]
    rows: List[Dict[str, Any]] = []
    total_cost = 0.0

    for task in tasks:
        for rep in range(repeats):
            label = f"{task['id']}" + (f".{rep+1}" if repeats > 1 else "")
            print(f"\n── Task {label} [{task['framework_id']}] ─────────────", file=sys.stderr)
            row: Dict[str, Any] = {"task": label, "framework_id": task["framework_id"],
                                   "trap": task.get("trap"), "arms": {}}
            for arm in arms:
                print(f"  {arm} ...", end="", flush=True, file=sys.stderr)
                r = _run_claude(task["prompt"].strip(), arm, model, budget, timeout)
                if not r.error:
                    _grade(r, task["framework_id"])
                total_cost += r.cost_usd
                row["arms"][arm] = r
                status = r.error or f"{r.verdict} (viol={r.violations}, tools={'Y' if r.called_truearch else 'n'})"
                print(f" {status}  ${r.cost_usd:.3f}", file=sys.stderr)
                time.sleep(1)
            rows.append(row)

    return {"rows": rows, "total_cost": total_cost, "model": model,
            "repeats": repeats, "tasks": len(tasks)}


def _pct_clean(rows: List[Dict[str, Any]], arm: str) -> str:
    graded = [row["arms"][arm] for row in rows if not row["arms"][arm].error]
    if not graded:
        return "n/a"
    clean = sum(1 for r in graded if r.violations == 0 and r.verdict != "no_code")
    return f"{clean}/{len(graded)}"


def _total_viol(rows: List[Dict[str, Any]], arm: str) -> int:
    return sum(row["arms"][arm].violations for row in rows if not row["arms"][arm].error)


def _organic_call_rate(rows: List[Dict[str, Any]]) -> str:
    graded = [row["arms"]["truearch_organic"] for row in rows
              if not row["arms"]["truearch_organic"].error]
    if not graded:
        return "n/a"
    called = sum(1 for r in graded if r.called_truearch)
    return f"{called}/{len(graded)} ({round(100*called/len(graded))}%)"


def write_results(data: Dict[str, Any]) -> None:
    rows = data["rows"]
    arms = ["baseline", "truearch_organic", "truearch_nudged"]
    lines: List[str] = []
    lines.append("# TrueArch Daily-Loop Evaluation (real Claude Code)\n")
    lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ")
    lines.append(f"**Engine:** `claude` CLI (headless), model `{data['model']}`  ")
    lines.append(f"**Tasks:** {data['tasks']}  |  **Repeats:** {data['repeats']}  "
                 f"|  **Total cost:** ${data['total_cost']:.2f}\n")

    lines.append("## Headline\n")
    lines.append("| Metric | baseline | truearch_organic | truearch_nudged |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Clean tasks (0 deprecated-API violations) | {_pct_clean(rows,'baseline')} "
                 f"| {_pct_clean(rows,'truearch_organic')} | {_pct_clean(rows,'truearch_nudged')} |")
    lines.append(f"| Total violations shipped | {_total_viol(rows,'baseline')} "
                 f"| {_total_viol(rows,'truearch_organic')} | {_total_viol(rows,'truearch_nudged')} |")
    lines.append(f"\n**Organic tool-call rate** (did Claude call a TrueArch tool without being told): "
                 f"{_organic_call_rate(rows)}\n")

    lines.append("## Per-task detail\n")
    lines.append("| Task | Framework | Arm | Verdict | Violations | TrueArch called | $ |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in rows:
        for arm in arms:
            r = row["arms"][arm]
            if r.error:
                lines.append(f"| {row['task']} | {row['framework_id']} | {arm} | "
                             f"ERROR: {r.error} | — | — | {r.cost_usd:.3f} |")
                continue
            vids = (" " + ",".join(r.violation_ids)) if r.violation_ids else ""
            lines.append(f"| {row['task']} | {row['framework_id']} | {arm} | {r.verdict} | "
                         f"{r.violations}{vids} | {'✅' if r.called_truearch else '—'} | {r.cost_usd:.3f} |")

    lines.append("\n## Methodology & limitations\n")
    lines.append("- **Engine is the real Claude Code** (`claude -p`), with TrueArch wired as an MCP "
                 "server exactly as a user would install it — highest fidelity to production use.")
    lines.append("- **Grading** runs each arm's generated code through TrueArch's own `validate_code`. "
                 "This verifies the code avoids *known* deprecated patterns (the product's exact claim), "
                 "not an independent notion of correctness.")
    lines.append("- **Variance:** `claude` output is not deterministic; single-run deltas are noisy. "
                 "Use `--repeats` for a stable estimate.")
    lines.append("- **`truearch_organic`** relies only on tool descriptions (no nudge); "
                 "**`truearch_nudged`** adds a system-prompt rule to validate. The gap indicates how "
                 "much usage guidance (e.g. a shipped CLAUDE.md snippet) matters.")

    _RESULTS_FILE.write_text("\n".join(lines) + "\n")
    print(f"\n✅ Wrote {_RESULTS_FILE}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description="TrueArch daily-loop eval via the real claude CLI")
    p.add_argument("--limit", type=int, default=None, help="Only run the first N tasks (pilot).")
    p.add_argument("--repeats", type=int, default=1, help="Repeat each task N times (variance).")
    p.add_argument("--model", default="sonnet", help="Model alias for `claude --model` (default: sonnet).")
    p.add_argument("--budget", type=float, default=0.50, help="--max-budget-usd cap per claude run.")
    p.add_argument("--timeout", type=int, default=300, help="Per-run timeout in seconds.")
    args = p.parse_args()

    data = run(args.limit, args.repeats, args.model, args.budget, args.timeout)
    write_results(data)


if __name__ == "__main__":
    main()
