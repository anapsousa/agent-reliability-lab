"""Hand labels for the trace checks: sample 30 traces blind, then measure agreement.

The three trace checks (tool choice, stopping, grounding) are policy: a slack, a
derivation rule, a quotation rule, all tuned on the same 120 runs they are reported on.
This is the calibration the report's "Next" section asks for. A person labels 30 traces
without seeing any model name or scorer verdict, and `compare` reports how often the
scorer agrees, and how many of the human-flagged failures it catches.

The sample is stratified so both outcomes are present: per model, half the runs the
scorer failed on at least one check and half it passed on all. Shuffled with a fixed
seed and renamed (T-01 ...). The key (item -> model, task) is committed; the page the
labeller sees is not, because the replayed tool outputs include the agent's private
context files. `export` writes it outside the repo.

    uv run python -m evals.judges.trace_labels export --out ~/somewhere/label-30.html
    uv run python -m evals.judges.trace_labels compare --labels trace-labels.json

The bars are fixed here, before any label exists. Never change them after labels are in.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from evals.fixtures.corpus import load_corpus
from evals.judges.stance import cohen_kappa
from evals.runners.claude_code import wilson
from evals.tasks.research_agent import load_golden
from evals.trace_rescore import MODELS, REPORTS, context_available, score_report

CAL_DIR = Path(__file__).parent / "trace-labels-2026-10-12"
KEY = CAL_DIR / "key.json"
TEMPLATE = Path(__file__).parent / "trace_label.template.html"
SEED = 20261012
PER_MODEL = 10
BASELINE_GLOB = "research-agent-v1-claude-code-*-2026-09-23T*.json"

# Pre-registered 2026-10-12, before any human label exists. Per check, over the traces
# where the scorer gives a verdict: the scorer must agree with the human on at least
# BAR_AGREEMENT of them, and catch at least BAR_FAIL_RECALL of the human-flagged failures.
BAR_AGREEMENT = 0.80
BAR_FAIL_RECALL = 0.80
CHECKS = ("tool", "stop", "ground")
GOOD = {"tool": "ok", "stop": "right", "ground": "grounded"}


def scorer_labels(row: dict) -> dict[str, str | None]:
    """The scorer's verdicts in the human's vocabulary. None = the check does not apply."""
    stop = row["stopping"]
    if stop["passed"] is None:
        stop_label = None
    elif stop["passed"]:
        stop_label = "right"
    elif any(f.startswith(("stopped early", "abandoned")) for f in stop["failures"]):
        stop_label = "early"
    else:
        stop_label = "overran"  # an overrun, or a run that hit the turn cap
    ground = row["grounding"]["passed"]
    return {
        "tool": "ok" if row["tool_choice"]["passed"] else "bad",
        "stop": stop_label,
        "ground": None if ground is None else ("grounded" if ground else "ungrounded"),
    }


def _failed_any(row: dict) -> bool:
    return any(v is not None and v != GOOD[k] for k, v in scorer_labels(row).items())


def scored_baseline() -> list[tuple[str, dict, dict]]:
    """(model, task from the report, trace row) for every baseline run."""
    corpus = load_corpus()
    golden = {t["id"]: t for t in load_golden()}
    with_context = context_available()
    out = []
    for path in sorted(REPORTS.glob(BASELINE_GLOB)):
        report = json.loads(path.read_text(encoding="utf-8"))
        rows = score_report(report, golden, corpus, with_context)
        for task, row in zip(report["tasks"], rows, strict=True):
            out.append((report["model_alias"], task, row))
    return out


def sample(runs: list[tuple[str, dict, dict]], seed: int = SEED) -> list[dict]:
    """Key entries, shuffled and renamed: half failed-on-something, half clean, per model."""
    rng = random.Random(seed)
    picked = []
    for model in MODELS:
        mine = [r for r in runs if r[0] == model]
        flagged = [r for r in mine if _failed_any(r[2])]
        clean = [r for r in mine if not _failed_any(r[2])]
        take_flagged = min(len(flagged), PER_MODEL // 2)
        take_clean = min(len(clean), PER_MODEL - take_flagged)
        take_flagged = min(len(flagged), PER_MODEL - take_clean)
        picked += rng.sample(flagged, take_flagged) + rng.sample(clean, take_clean)
    rng.shuffle(picked)
    return [
        {"item": f"T-{i + 1:02d}", "model": m, "task": t["id"]}
        for i, (m, t, _row) in enumerate(picked)
    ]


def _args(step: dict) -> str:
    args = step.get("arguments") or {}
    return ", ".join(f"{k}={v}" for k, v in args.items())


def build_items(key: list[dict]) -> list[dict]:
    """What the labeller sees. No model name, no verdicts. Includes private context text."""
    from evals.fixtures.tools import ToolFailure, read_context_text, web_fetch_text, web_search_text

    corpus = load_corpus()
    golden = {t["id"]: t for t in load_golden()}
    reports = {
        json.loads(p.read_text(encoding="utf-8"))["model_alias"]: json.loads(
            p.read_text(encoding="utf-8")
        )
        for p in sorted(REPORTS.glob(BASELINE_GLOB))
    }
    items = []
    for entry in key:
        report = reports[entry["model"]]
        task = next(t for t in report["tasks"] if t["id"] == entry["task"])
        spec = golden[entry["task"]]
        steps = []
        for s in task["steps"]:
            result = ""
            if not s.get("error"):
                try:
                    name = str((s.get("arguments") or {}).get("name", ""))
                    url = str((s.get("arguments") or {}).get("url", ""))
                    query = str((s.get("arguments") or {}).get("query", ""))
                    if s["tool"] == "web_search":
                        result = web_search_text(corpus, query)
                    elif s["tool"] == "web_fetch":
                        result = web_fetch_text(corpus, url)
                    elif s["tool"] == "read_context":
                        result = read_context_text(name)
                except ToolFailure:
                    result = ""
            steps.append(
                {
                    "tool": s["tool"],
                    "args": _args(s),
                    "error": bool(s.get("error")),
                    "result": result,
                }
            )
        items.append(
            {
                "id": entry["item"],
                "task": spec["input"].strip(),
                "effort": spec.get("effort", "standard"),
                "steps": steps,
                "answer": task["answer"],
            }
        )
    return items


def export(out: Path, runs: list[tuple[str, dict, dict]] | None = None) -> list[dict]:
    if not context_available():
        raise SystemExit("the vendored context files are needed to show read_context results")
    out = out.expanduser().resolve()
    repo = Path(__file__).resolve().parents[2]
    if out == repo or repo in out.parents:
        raise SystemExit(f"refusing {out}: inside the repo, and the page holds private context")
    runs = runs or scored_baseline()
    key = sample(runs)
    CAL_DIR.mkdir(parents=True, exist_ok=True)
    KEY.write_text(json.dumps(key, indent=1) + "\n", encoding="utf-8")
    data = json.dumps(build_items(key), ensure_ascii=False).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        TEMPLATE.read_text(encoding="utf-8").replace("/*ITEMS*/[]", data), encoding="utf-8"
    )
    return key


def compare(human: dict[str, dict], runs: list[tuple[str, dict, dict]], key: list[dict]) -> dict:
    """Per check: agreement, kappa, and recall on the human-flagged failures."""
    by_run = {(m, t["id"]): row for m, t, row in runs}
    result: dict = {"n_items": 0, "checks": {}}
    pairs: dict[str, list[tuple[str, str, str]]] = {c: [] for c in CHECKS}
    for entry in key:
        labels = human.get(entry["item"])
        if not labels or not all(labels.get(c) for c in CHECKS):
            continue
        result["n_items"] += 1
        scorer = scorer_labels(by_run[(entry["model"], entry["task"])])
        for c in CHECKS:
            if scorer[c] is not None:
                pairs[c].append((entry["item"], labels[c], scorer[c]))
    for c, rows in pairs.items():
        h = [r[1] for r in rows]
        s = [r[2] for r in rows]
        agree = sum(a == b for a, b in zip(h, s, strict=True))
        flagged = [r for r in rows if r[1] != GOOD[c]]
        caught = sum(1 for r in flagged if r[2] != GOOD[c])
        result["checks"][c] = {
            "n": len(rows),
            "agree": agree,
            "agree_ci95": wilson(agree, len(rows)) if rows else None,
            "kappa": cohen_kappa(h, s) if len(rows) > 1 else None,
            "human_failures": len(flagged),
            "caught": caught,
            "false_alarms": sum(1 for r in rows if r[1] == GOOD[c] and r[2] != GOOD[c]),
            "confusion": dict(Counter((r[1], r[2]) for r in rows)),
            "disagreements": [(r[0], r[1], r[2]) for r in rows if r[1] != r[2]],
            "meets_bar": bool(rows)
            and agree / len(rows) >= BAR_AGREEMENT
            and (not flagged or caught / len(flagged) >= BAR_FAIL_RECALL),
        }
    return result


def render(result: dict) -> str:
    lines = [
        (
            f"Items with a complete label: {result['n_items']}. Bars (fixed 2026-10-12): "
            f"agreement >= {BAR_AGREEMENT:.0%}, recall of human-flagged failures "
            f">= {BAR_FAIL_RECALL:.0%}."
        ),
        "",
        "| Check | n | Agreement | kappa | Human failures caught | False alarms | Meets bar |",
        "|---|---|---|---|---|---|---|",
    ]
    names = {"tool": "Tool choice", "stop": "Stopping", "ground": "Grounding"}
    for c in CHECKS:
        r = result["checks"][c]
        if not r["n"]:
            lines.append(f"| {names[c]} | 0 | n/a | n/a | n/a | n/a | n/a |")
            continue
        lo, hi = r["agree_ci95"]
        kappa = "n/a" if r["kappa"] is None else f"{r['kappa']:.2f}"
        lines.append(
            f"| {names[c]} | {r['n']} | {r['agree']}/{r['n']} = {r['agree'] / r['n']:.0%} "
            f"({lo:.0%}-{hi:.0%}) | {kappa} | {r['caught']}/{r['human_failures']} | "
            f"{r['false_alarms']} | {'yes' if r['meets_bar'] else 'NO'} |"
        )
    lines += ["", "Disagreements (item: human, scorer):", ""]
    for c in CHECKS:
        pairs = ", ".join(f"{i}: {h}, {s}" for i, h, s in result["checks"][c]["disagreements"])
        lines.append(f"- **{names[c]}**: {pairs or 'none'}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("compare")
    c.add_argument("--labels", type=Path, required=True)
    c.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "export":
        key = export(args.out)
        print(f"{len(key)} traces -> {args.out}; key -> {KEY}")
    else:
        human = json.loads(args.labels.read_text(encoding="utf-8"))
        text = render(
            compare(human, scored_baseline(), json.loads(KEY.read_text(encoding="utf-8")))
        )
        print(text)
        if args.out:
            args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
