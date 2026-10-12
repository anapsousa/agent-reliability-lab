"""pass^k: how often does the same agent pass the same task every time?

One run per task is a demo. A task that passes once and fails the next time is a flaky
test with good PR, and the single-run pass rate hides it. This reads repeat runs of one
series and reports, per layer:

- the mean single-run pass rate, and how far the runs differ from each other;
- **pass^k**: the share of tasks that passed in all k runs (the reliable ones);
- pass@k: the share that passed at least once (the ones that can work);
- the tasks that flip, and the categories they cluster in;
- whether the CI gate's tolerance sits above the run-to-run gap.

Runs are grouped by alias *and the model actually seen*. The alias is not a version: on
2026-10-12 `--model haiku` ran claude-haiku-5-5, where the 23 Sep baseline ran
claude-haiku-4-5. Mixing the two would measure a model change, not variance, so a group
that mixes models is refused.

    uv run python -m evals.passk --dir evals/reports/repeats-2026-10-12
    uv run python -m evals.passk --dir DIR --out FILE.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from evals.gate import TOLERANCE
from evals.runners.claude_code import wilson

LAYERS = ("outcome", "trajectory", "components", "all_layers")
TRACE_CHECKS = ("tool_choice", "stopping", "grounding")


def task_passed(task: dict, layer: str) -> bool | None:
    """The run's verdict on one task for one layer. None = the layer does not apply."""
    if layer == "all_layers":
        parts = [task["scores"][k]["passed"] for k in ("outcome", "trajectory", "components")]
        return all(parts)
    if layer in TRACE_CHECKS:
        return (task.get("trace_scores") or {}).get(layer, {}).get("passed")
    return task["scores"][layer]["passed"]


def load_groups(directory: Path) -> dict[tuple, list[dict]]:
    """Reports grouped by (alias, models actually seen). Mixed-model groups are an error."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    aliases: dict[str, set[tuple]] = defaultdict(set)
    for path in sorted(directory.glob("research-agent-*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        key = (report["model_alias"], tuple(report.get("models_seen") or ()))
        groups[key].append(report)
        aliases[report["model_alias"]].add(key[1])
    mixed = {a: sorted(m) for a, m in aliases.items() if len(m) > 1}
    if mixed:
        raise SystemExit(f"alias resolved to different models, refusing to pool: {mixed}")
    return dict(groups)


def analyse(runs: list[dict]) -> dict:
    """Per-layer pass^k statistics for k repeat runs of one series."""
    k = len(runs)
    ids = sorted({t["id"] for r in runs for t in r["tasks"]})
    by_run = [{t["id"]: t for t in r["tasks"]} for r in runs]
    category = {t["id"]: t["category"] for r in runs for t in r["tasks"]}
    out: dict = {"k": k, "tasks": len(ids), "layers": {}, "flips_by_category": {}}
    flip_cat: Counter = Counter()
    seen_cat: Counter = Counter()
    for layer in (*LAYERS, *TRACE_CHECKS):
        verdicts = {i: [task_passed(run[i], layer) for run in by_run if i in run] for i in ids}
        applicable = {i: v for i, v in verdicts.items() if len(v) == k and None not in v}
        if not applicable:
            continue
        per_run = [sum(v[j] for v in applicable.values()) / len(applicable) for j in range(k)]
        all_pass = sum(all(v) for v in applicable.values())
        any_pass = sum(any(v) for v in applicable.values())
        flips = sorted(i for i, v in applicable.items() if any(v) and not all(v))
        n = len(applicable)
        out["layers"][layer] = {
            "n": n,
            "per_run": per_run,
            "mean": sum(per_run) / k,
            "gap": max(per_run) - min(per_run),
            "pass_all": all_pass,
            "pass_all_ci95": wilson(all_pass, n),
            "pass_any": any_pass,
            "flips": flips,
        }
        if layer == "outcome":
            for i in applicable:
                seen_cat[category[i]] += 1
            flip_cat.update(category[i] for i in flips)
    out["flips_by_category"] = {c: (flip_cat[c], seen_cat[c]) for c in sorted(seen_cat)}
    out["gate_tolerance"] = TOLERANCE
    return out


def render(results: dict[tuple, dict]) -> str:
    lines: list[str] = []
    for (alias, models), r in sorted(results.items()):
        lines += [
            (
                f"## {alias} ({', '.join(models) or 'model not recorded'}), k = {r['k']}, "
                f"{r['tasks']} tasks"
            ),
            "",
            (
                "| Layer | Single-run pass rate (each run) | Largest gap between runs | "
                f"pass^{r['k']} | pass@{r['k']} | Tasks that flip |"
            ),
            "|---|---|---|---|---|---|",
        ]
        for layer, s in r["layers"].items():
            lo, hi = s["pass_all_ci95"]
            runs = ", ".join(f"{x:.0%}" for x in s["per_run"])
            lines.append(
                f"| {layer} | {s['mean']:.0%} ({runs}) | {s['gap'] * 100:.0f} pts | "
                f"{s['pass_all']}/{s['n']} = {s['pass_all'] / s['n']:.0%} ({lo:.0%}-{hi:.0%}) | "
                f"{s['pass_any']}/{s['n']} = {s['pass_any'] / s['n']:.0%} | {len(s['flips'])} |"
            )
        cats = ", ".join(f"{c} {f}/{n}" for c, (f, n) in r["flips_by_category"].items())
        lines += ["", f"Outcome flips by category: {cats}.", ""]
    return "\n".join(lines)


def gate_note(results: dict[tuple, dict]) -> str:
    gaps = [
        (alias, layer, s["gap"])
        for (alias, _m), r in results.items()
        for layer, s in r["layers"].items()
        if layer in ("outcome", "all_layers")
    ]
    if not gaps:
        return ""
    alias, layer, gap = max(gaps, key=lambda g: g[2])
    verdict = "above" if gap > TOLERANCE else "below"
    return (
        f"The gate fails a PR that loses more than {TOLERANCE * 100:.0f} points on `all_layers` "
        f"or `outcome`. The largest gap between two runs of the same unchanged agent here is "
        f"{gap * 100:.0f} points ({alias}, {layer}), {verdict} the tolerance.\n"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", type=Path, required=True, help="folder of repeat-run reports")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    groups = load_groups(args.dir)
    results = {key: analyse(runs) for key, runs in groups.items() if len(runs) >= 2}
    if not results:
        raise SystemExit("need at least two runs of the same series")
    text = render(results) + "\n" + gate_note(results)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
