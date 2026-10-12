"""Score the stored baseline runs at trace level. No model is called.

The committed reports keep each step's tool and arguments but not what the tool
returned (that would triple their size). Two ways to get the outputs back, per task:

1. **Raw transcript** (preferred, exact): `<runs>/<run_id>/<task>.jsonl`, written by the
   runner and parsed with the runner's own `parse_stream`. Gitignored, because it holds
   the private context files; `evals/keep_runs.py` copies it somewhere safe.
2. **Replay** (fallback): the fixture web is deterministic, so every `web_search` and
   `web_fetch` is replayed against the frozen corpus with the same functions the MCP
   server uses. `read_context` is replayed only if the vendored context files are
   present locally, else it is empty and any figure taken from the agent's own context
   shows up as ungrounded. For the 2026-09-23 baseline this is the only route: those
   transcripts were not kept.

The output says which route each report took. Steps that errored in the real run keep an
empty result: their text was an error message, never evidence.

    uv run python -m evals.trace_rescore                   # markdown to stdout
    uv run python -m evals.trace_rescore --out FILE.md     # also writes it
    uv run python -m evals.trace_rescore --runs DIR        # where the transcripts are
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evals.fixtures.corpus import Corpus, load_corpus
from evals.fixtures.tools import (
    AGENT_DIR,
    CONTEXT_FILES,
    ToolFailure,
    read_context_text,
    web_fetch_text,
    web_search_text,
)
from evals.runners.claude_code import RUNS, parse_stream, wilson
from evals.scorers.steps import Step
from evals.scorers.trace import evaluate_trace
from evals.tasks.research_agent import load_golden

REPORTS = Path(__file__).parent / "reports"
MODELS = ("haiku", "sonnet", "opus")
CHECKS = ("tool_choice", "stopping", "grounding")


def context_available(context_dir: Path = AGENT_DIR / "context") -> bool:
    return all((context_dir / f).exists() for f in CONTEXT_FILES.values())


def replay(stored: dict, corpus: Corpus, with_context: bool) -> Step:
    tool, args = stored["tool"], dict(stored.get("arguments") or {})
    result = ""
    if not stored.get("error"):
        try:
            if tool == "web_search":
                result = web_search_text(corpus, str(args.get("query", "")))
            elif tool == "web_fetch":
                result = web_fetch_text(corpus, str(args.get("url", "")))
            elif tool == "read_context" and with_context:
                result = read_context_text(str(args.get("name", "")))
        except ToolFailure:
            result = ""
    return Step(tool=tool, arguments=args, error=bool(stored.get("error")), result=result)


def load_raw(run_id: str, task_id: str, runs_dir: Path | None):
    """The runner's own parse of a kept transcript, or None if there is none."""
    if runs_dir is None:
        return None
    path = runs_dir / run_id / f"{task_id}.jsonl"
    if not path.exists():
        return None
    return parse_stream(path.read_text(encoding="utf-8").splitlines())


def score_report(
    report: dict,
    golden: dict[str, dict],
    corpus: Corpus,
    with_context: bool,
    runs_dir: Path | None = None,
):
    rows = []
    for task in report["tasks"]:
        spec = golden[task["id"]]
        raw = load_raw(report["run_id"], task["id"], runs_dir)
        if raw is not None:
            steps, answer, stop = raw.steps, raw.answer, raw.stop
        else:
            steps = [replay(s, corpus, with_context) for s in task["steps"]]
            answer, stop = task["answer"], task.get("stop", "")
        result = evaluate_trace(
            steps,
            answer,
            spec["expected"],
            spec.get("trajectory") or {},
            effort=spec.get("effort", "standard"),
            task_input=spec["input"].strip(),
            stop=stop,
        )
        rows.append(
            {
                "id": task["id"],
                "outcome": task["scores"]["outcome"]["passed"],
                "source": "raw" if raw is not None else "replay",
                **result.as_dict(),
            }
        )
    return rows


def summarise(rows: list[dict]) -> dict:
    out = {"n": len(rows)}
    for check in CHECKS:
        applies = [r[check] for r in rows if r[check]["passed"] is not None]
        passes = sum(c["passed"] for c in applies)
        scores = [c["score"] for c in applies if c["score"] is not None]
        out[check] = {
            "n": len(applies),
            "passed": passes,
            "ci95": wilson(passes, len(applies)),
            "mean_score": sum(scores) / len(scores) if scores else None,
        }
    verdicts = Counter(s["verdict"] for r in rows for s in r["steps"])
    out["step_verdicts"] = dict(verdicts)
    out["reasons"] = Counter(s["reason"] for r in rows for s in r["steps"] if s["verdict"] != "ok")
    out["ungrounded_figures"] = Counter(
        f for r in rows for f in r["grounding"]["detail"].get("ungrounded_figures", [])
    )
    strict = [r["grounding"]["detail"]["strict_passed"] for r in rows]
    strict = [x for x in strict if x is not None]
    out["grounding_strict"] = {
        "n": len(strict),
        "passed": sum(strict),
        "ci95": wilson(sum(strict), len(strict)),
    }

    def details(key: str) -> list:
        return [x for r in rows for x in r["grounding"]["detail"].get(key, [])]

    out["derived_verified"] = len(details("derived_verified"))
    out["derived_unverified"] = Counter(details("derived_unverified"))
    out["misattributed"] = details("misattributed")
    out["unattributed_figures"] = sum(
        r["grounding"]["detail"].get("unattributed_figures", 0) for r in rows
    )
    out["sources"] = Counter(r["source"] for r in rows)
    out["ungrounded_urls"] = sum(
        len(r["grounding"]["detail"].get("ungrounded_urls", [])) for r in rows
    )
    out["overruns"] = [
        r["stopping"]["detail"].get("calls_after_enough")
        for r in rows
        if r["stopping"]["passed"] is False and r["stopping"]["detail"].get("calls_after_enough")
    ]
    out["early"] = sum(
        1 for r in rows if any("stopped early" in f for f in r["stopping"]["failures"])
    )
    out["capped"] = sum(1 for r in rows if any("turn cap" in f for f in r["stopping"]["failures"]))
    # Does the trace explain the outcome? Runs that passed outcome but fail grounding are
    # the interesting ones: a right-looking answer built on something no tool returned.
    out["outcome_pass_grounding_fail"] = sum(
        1 for r in rows if r["outcome"] and r["grounding"]["passed"] is False
    )
    return out


def rescore_all(reports_dir: Path = REPORTS, runs_dir: Path | None = RUNS) -> tuple[dict, bool]:
    corpus = load_corpus()
    golden = {t["id"]: t for t in load_golden()}
    with_context = context_available()
    newest: dict[str, dict] = {}
    for path in sorted(reports_dir.glob("research-agent-v1-claude-code-*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        rows = score_report(report, golden, corpus, with_context, runs_dir)
        newest[report["model_alias"]] = {"report": path.name, "rows": rows, **summarise(rows)}
    return newest, with_context


def _cell(c: dict) -> str:
    if not c["n"]:
        return "n/a"
    lo, hi = c["ci95"]
    return f"{c['passed']}/{c['n']} = {c['passed'] / c['n']:.0%} ({lo:.0%}-{hi:.0%})"


def render(results: dict, with_context: bool) -> str:
    models = [m for m in MODELS if m in results]
    lines = [
        "Context replay: "
        + (
            "private context files present, read_context replayed"
            if with_context
            else (
                "private context files ABSENT, read_context results empty "
                "(figures taken from the agent's own context count as ungrounded)"
            )
        ),
        "",
        (
            "| Model | Tool choice (runs) | Mean step score | Stopping | "
            "Grounding, strict | Grounding, derivations checked | Outcome pass, grounding fail |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    for m in models:
        r = results[m]
        lines.append(
            f"| {m} | {_cell(r['tool_choice'])} | {r['tool_choice']['mean_score']:.0%} | "
            f"{_cell(r['stopping'])} | {_cell(r['grounding_strict'])} | "
            f"{_cell(r['grounding'])} | {r['outcome_pass_grounding_fail']} |"
        )
    header = (
        "| Model | Step verdicts | Overrun runs (calls after enough) | Early stops | "
        "Turn-cap | Ungrounded URLs |"
    )
    lines += ["", header, "|---|---|---|---|---|---|"]
    for m in models:
        r = results[m]
        v = r["step_verdicts"]
        lines.append(
            f"| {m} | ok {v.get('ok', 0)}, wrong {v.get('wrong', 0)}, "
            f"redundant {v.get('redundant', 0)} | {len(r['overruns'])} "
            f"({', '.join(map(str, sorted(r['overruns']))) or '-'}) | {r['early']} | "
            f"{r['capped']} | {r['ungrounded_urls']} |"
        )
    lines += [
        "",
        (
            "| Model | Tool output from | Derived figures verified | "
            "Marked derived, does not reproduce | "
            "Sentences citing a URL where the figure is not in it | "
            "Figures with no URL to check |"
        ),
        "|---|---|---|---|---|---|",
    ]
    for m in models:
        r = results[m]
        src = ", ".join(f"{n} {k}" for k, n in sorted(r["sources"].items()))
        lines.append(
            f"| {m} | {src} | {r['derived_verified']} | "
            f"{sum(r['derived_unverified'].values())} | {len(r['misattributed'])} | "
            f"{r['unattributed_figures']} |"
        )
    lines += ["", "Non-ok step reasons:", ""]
    for m in models:
        reasons = "; ".join(f"{k} ({n})" for k, n in results[m]["reasons"].most_common())
        lines.append(f"- **{m}**: {reasons or 'none'}")
    lines += ["", "Marked as derived but not reproducible:", ""]
    for m in models:
        figs = ", ".join(f"{k} x{n}" for k, n in results[m]["derived_unverified"].most_common())
        lines.append(f"- **{m}**: {figs or 'none'}")
    lines += ["", "Most frequent ungrounded figures (after derivations):", ""]
    for m in models:
        figs = ", ".join(f"{k} x{n}" for k, n in results[m]["ungrounded_figures"].most_common(8))
        lines.append(f"- **{m}**: {figs or 'none'}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, help="also write the markdown here")
    parser.add_argument("--runs", type=Path, default=RUNS, help="where the raw transcripts are")
    args = parser.parse_args(argv)
    results, with_context = rescore_all(runs_dir=args.runs)
    text = render(results, with_context)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
