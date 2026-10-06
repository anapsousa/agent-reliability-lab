"""Run the pinned research-agent as itself: real Claude Code, fixture web.

The Inspect task (`evals/tasks/research_agent.py`) measures a *port*: the agent's
prompt driven by Inspect's own tool loop. This runner measures the agent the way it
actually runs — `claude -p` with the pinned `agent.md` as its system prompt — and
swaps only the web, via the `fixture-web` MCP server. Scoring is the same three
layers, from the same functions, so the two harnesses are directly comparable.

It runs on the Claude subscription, not billed API spend. `total_cost_usd` in the
report is Claude Code's API-equivalent figure: the cost of the run had it been billed.

    uv run python -m evals.runners.claude_code --model sonnet
    uv run python -m evals.runners.claude_code --model sonnet --tasks rsch-001,rsch-002

Isolation, verified against Claude Code 2.1.280 by listing the tools in the stream's
init event: the three fixture tools and nothing else. Every built-in is disabled by
name (`--tools ""` alone is not honoured — see evals/judges/run_llm_judge.py), no MCP
server but fixture-web is loaded, no settings file is read, and each task runs in a
fresh empty directory so no CLAUDE.md or auto-memory from another project reaches it.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from evals.fixtures.corpus import load_corpus
from evals.fixtures.tools import CONTEXT_FILES, REPO
from evals.judges.run_llm_judge import JUDGE_DISALLOWED_TOOLS
from evals.scorers.components import evaluate_components
from evals.scorers.outcome import evaluate_outcome
from evals.scorers.steps import Step
from evals.scorers.trajectory import evaluate_trajectory
from evals.tasks.research_agent import agent_system_prompt, load_golden

SERVER = "fixture-web"
TOOL_PREFIX = f"mcp__{SERVER}__"
FIXTURE_TOOLS = ("read_context", "web_search", "web_fetch")
REPORTS = REPO / "evals" / "reports"
RUNS = REPO / "evals" / "runs" / "claude-code"  # gitignored: full transcripts

# The Inspect port caps a run at 25 messages. Claude Code counts agentic turns, one
# assistant message plus its tool results, so 12 turns is the nearest equivalent.
DEFAULT_MAX_TURNS = 12

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def redact(text: str) -> str:
    """Claude Code injects the account email into every session. This repo is public."""
    return _EMAIL.sub("[email]", text)


# --------------------------------------------------------------------------- #
# Invocation
# --------------------------------------------------------------------------- #


def mcp_config(python: Path = REPO / ".venv" / "bin" / "python") -> dict:
    return {
        "mcpServers": {
            SERVER: {"command": str(python), "args": [str(REPO / "mcp" / SERVER / "server.py")]}
        }
    }


def agent_argv(
    system_prompt: str,
    mcp_config_path: Path,
    model: str,
    max_turns: int = DEFAULT_MAX_TURNS,
    effort: str | None = None,
) -> list[str]:
    argv = [
        "claude",
        "-p",
        "--model",
        model,
        "--system-prompt",
        system_prompt,
        "--mcp-config",
        str(mcp_config_path),
        "--strict-mcp-config",
        "--tools",
        "",
        "--disallowedTools",
        ",".join(JUDGE_DISALLOWED_TOOLS),
        "--allowedTools",
        ",".join(TOOL_PREFIX + t for t in FIXTURE_TOOLS),
        "--setting-sources",
        "",
        "--no-session-persistence",
        "--max-turns",
        str(max_turns),
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    if effort:
        argv += ["--effort", effort]
    return argv


# --------------------------------------------------------------------------- #
# Stream parsing
# --------------------------------------------------------------------------- #


@dataclass
class Trace:
    steps: list[Step] = field(default_factory=list)
    answer: str = ""
    tools_offered: list[str] = field(default_factory=list)
    model: str = ""
    cost_usd: float | None = None
    duration_ms: int | None = None
    num_turns: int | None = None
    stop: str = ""  # the result event's subtype: success, error_max_turns, ...
    usage: dict = field(default_factory=dict)


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if b.get("type") == "text")


def parse_stream(lines) -> Trace:
    """Turn `claude -p --output-format stream-json` output into scorer-ready steps.

    Tool calls arrive on assistant events and their results on the following user
    event, keyed by id — the same pairing `steps_from_messages` does for Inspect, so a
    call with no result (the run hit its turn cap mid-flight) still counts as a step.
    The MCP prefix is stripped, so the scorers see `web_fetch` exactly as they do
    under Inspect. Any other tool keeps its full name and fails the component layer.
    """
    trace = Trace()
    calls: list[dict] = []
    results: dict[str, dict] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        event = json.loads(line)
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            trace.tools_offered = list(event.get("tools") or [])
            trace.model = event.get("model", "")
        elif kind == "assistant":
            for block in event.get("message", {}).get("content") or []:
                if block.get("type") == "tool_use":
                    calls.append(block)
        elif kind == "user":
            content = event.get("message", {}).get("content")
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    results[block.get("tool_use_id")] = block
        elif kind == "result":
            trace.answer = event.get("result") or ""
            trace.cost_usd = event.get("total_cost_usd")
            trace.duration_ms = event.get("duration_ms")
            trace.num_turns = event.get("num_turns")
            trace.stop = event.get("subtype", "")
            trace.usage = event.get("usage") or {}

    for call in calls:
        name = call.get("name", "")
        result = results.get(call.get("id"))
        trace.steps.append(
            Step(
                tool=name.removeprefix(TOOL_PREFIX),
                arguments=dict(call.get("input") or {}),
                error=bool(result and result.get("is_error")),
                result=_result_text(result.get("content")) if result else "",
            )
        )
    return trace


# --------------------------------------------------------------------------- #
# Scoring and statistics
# --------------------------------------------------------------------------- #


def score(spec: dict, trace: Trace, ground_truth: dict) -> dict:
    outcome = evaluate_outcome(trace.answer, spec["expected"], ground_truth)
    trajectory = evaluate_trajectory(trace.steps, trace.answer, spec.get("trajectory") or {})
    components = evaluate_components(
        trace.steps,
        spec.get("trajectory") or {},
        context_names=list(CONTEXT_FILES),
        task_input=spec["input"].strip(),
    )
    return {
        layer: {"passed": r.passed, "failures": r.failures, "checks_run": r.checks_run}
        for layer, r in (
            ("outcome", outcome),
            ("trajectory", trajectory),
            ("components", components),
        )
    }


def wilson(passes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval. On 40 tasks it is roughly ±15 points — say so next to the rate."""
    if n == 0:
        return (0.0, 0.0)
    p = passes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile: p95 of 40 runs is the 38th slowest, an observed value."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    summary: dict = {"n": n}
    for layer in ("outcome", "trajectory", "components"):
        passes = sum(r["scores"][layer]["passed"] for r in rows)
        summary[layer] = {
            "passed": passes,
            "rate": round(passes / n, 4) if n else 0.0,
            "ci95": wilson(passes, n),
        }
    all_three = sum(all(r["scores"][k]["passed"] for k in r["scores"]) for r in rows)
    summary["all_layers"] = {
        "passed": all_three,
        "rate": round(all_three / n, 4) if n else 0.0,
        "ci95": wilson(all_three, n),
    }
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    wall = [r["wall_s"] for r in rows]
    summary["cost_usd"] = {
        "total": round(sum(costs), 4),
        "mean": round(sum(costs) / len(costs), 4) if costs else None,
        "note": "API-equivalent, reported by Claude Code; run on subscription",
    }
    summary["latency_s"] = {
        "p50": percentile(wall, 50),
        "p95": percentile(wall, 95),
        "max": max(wall) if wall else None,
    }
    summary["stops"] = {
        s: sum(r["stop"] == s for r in rows) for s in sorted({r["stop"] for r in rows})
    }
    return summary


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #


def run_task(
    spec: dict,
    system_prompt: str,
    model: str,
    max_turns: int,
    effort: str | None,
    ground_truth: dict,
    run_dir: Path,
    timeout: int,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="ral-") as tmp:
        cfg = Path(tmp) / "mcp.json"
        cfg.write_text(json.dumps(mcp_config()), encoding="utf-8")
        started = time.monotonic()
        try:
            proc = subprocess.run(
                agent_argv(system_prompt, cfg, model, max_turns, effort),
                input=spec["input"].strip(),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                check=False,
            )
            stdout, rc = proc.stdout, proc.returncode
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            rc, stderr = -1, f"timeout after {timeout}s"
        wall = round(time.monotonic() - started, 2)

    (run_dir / f"{spec['id']}.jsonl").write_text(stdout, encoding="utf-8")
    trace = parse_stream(stdout.splitlines())
    offered = sorted(trace.tools_offered)
    expected = sorted(TOOL_PREFIX + t for t in FIXTURE_TOOLS)
    if offered and offered != expected:
        # Isolation failed: the agent could reach something other than the fixture web.
        # Every score from this run would be measuring the wrong system.
        raise RuntimeError(f"{spec['id']}: tool surface was {offered}, expected {expected}")
    return {
        "id": spec["id"],
        "category": spec["category"],
        "difficulty": spec["difficulty"],
        "rc": rc,
        "stop": trace.stop or ("timeout" if rc == -1 else "no-result"),
        "stderr_tail": redact(stderr[-400:]) if rc else "",
        "model": trace.model,
        "cost_usd": trace.cost_usd,
        "wall_s": wall,
        "num_turns": trace.num_turns,
        "steps": [
            {"tool": s.tool, "arguments": s.arguments, "error": s.error} for s in trace.steps
        ],
        "answer": redact(trace.answer),
        "scores": score(spec, trace, ground_truth),
    }


def cli_version() -> str:
    out = subprocess.run(["claude", "--version"], capture_output=True, text=True, check=False)
    return out.stdout.strip()


def git_sha() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", default="v1", help="pinned agent version under agent/")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default=None)
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument("--tasks", default="", help="comma-separated ids; default all")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=900, help="seconds per task")
    args = parser.parse_args(argv)

    corpus = load_corpus()
    golden = load_golden()
    if args.tasks:
        wanted = set(args.tasks.split(","))
        golden = [t for t in golden if t["id"] in wanted]
    system_prompt = agent_system_prompt(args.version)

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_id = f"research-agent-{args.version}-claude-code-{args.model}-{stamp}"
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    def one(spec: dict) -> dict:
        row = run_task(
            spec,
            system_prompt,
            args.model,
            args.max_turns,
            args.effort,
            corpus.ground_truth,
            run_dir,
            args.timeout,
        )
        verdict = "".join("P" if row["scores"][k]["passed"] else "." for k in row["scores"])
        print(
            f"{row['id']}  {verdict}  {row['stop']:<16} {row['wall_s']:>6}s  "
            f"${row['cost_usd'] or 0:.4f}",
            flush=True,
        )
        return row

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        rows = sorted(pool.map(one, golden), key=lambda r: r["id"])

    report = {
        "run_id": run_id,
        "agent": "research-agent",
        "agent_version": args.version,
        "harness": "claude-code-cli",
        "claude_code": cli_version(),
        "model_alias": args.model,
        "models_seen": sorted({r["model"] for r in rows if r["model"]}),
        "effort": args.effort,
        "max_turns": args.max_turns,
        "corpus_version": corpus.ground_truth["corpus_version"],
        "repo_sha": git_sha(),
        "started": stamp,
        "summary": summarise(rows),
        "tasks": rows,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"{run_id}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = report["summary"]
    print(f"\n{run_id}")
    for layer in ("outcome", "trajectory", "components", "all_layers"):
        lo, hi = s[layer]["ci95"]
        print(
            f"  {layer:<11} {s[layer]['passed']:>2}/{s['n']}  {s[layer]['rate']:.0%}"
            f"  (95% CI {lo:.0%}–{hi:.0%})"
        )
    print(
        f"  cost ${s['cost_usd']['total']} API-equiv   p95 {s['latency_s']['p95']}s   {s['stops']}"
    )
    print(f"  report: {out.relative_to(REPO)}")
    return out


if __name__ == "__main__":
    main()
