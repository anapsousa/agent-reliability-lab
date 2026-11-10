"""The five evaluation dimensions, side by side, from reports already on disk.

An agent is not "good" on one number. This reads repeat-run reports and puts quality,
reliability, latency and cost for each series in one table, and says plainly where a
dimension is not measured. It calls no model and costs nothing: every figure is read
from the committed report JSON (`wall_s`, `cost_usd` per task, the layer verdicts).

| Dimension | Measured as | Source in the report |
|---|---|---|
| Quality | mean single-run pass rate, `all_layers` and `outcome` | `tasks[].scores` |
| Reliability | pass^k and pass@k on `all_layers` | same, via `evals.passk` |
| Latency | p50 / p95 / max of per-task wall time, all runs pooled | `tasks[].wall_s` |
| Cost | API-equivalent USD per run, per task, per `all_layers` pass | `tasks[].cost_usd` |
| Safety | **not measured**: `redteam/suites/` and `redteam/findings/` are empty | none |

Cost is Claude Code's API-equivalent figure; the runs were on the subscription, so no
money was spent. Layers are as recorded in each report. Re-scored verdicts (the stance
labels, the forbidden-source fix) live in other reports and are not applied here.

    uv run python -m evals.dimensions --dir evals/reports/repeats-2026-10-12 \\
        --dir evals/reports/repeats-2026-11-02 --out evals/reports/dimensions-2026-11-10.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

from evals.passk import analyse, load_groups
from evals.runners.claude_code import percentile

SAFETY_NOTE = (
    "not measured: `redteam/suites/` and `redteam/findings/` hold no suite and no finding yet "
    "(planned P5, 3-4 Dec)"
)


def _wall(runs: list[dict]) -> list[float]:
    return [t["wall_s"] for r in runs for t in r["tasks"] if t.get("wall_s") is not None]


def _run_costs(runs: list[dict]) -> list[float]:
    return [sum(t.get("cost_usd") or 0.0 for t in r["tasks"]) for r in runs]


def dimensions(runs: list[dict]) -> dict:
    """The five dimensions for k repeat runs of one series."""
    stats = analyse(runs)
    wall = _wall(runs)
    costs = _run_costs(runs)
    total = sum(costs)
    n_tasks = sum(len(r["tasks"]) for r in runs)
    all_layers_passes = sum(
        all(t["scores"][k]["passed"] for k in ("outcome", "trajectory", "components"))
        for r in runs
        for t in r["tasks"]
    )
    layers = stats["layers"]
    return {
        "k": stats["k"],
        "tasks": stats["tasks"],
        "quality": {x: layers[x]["mean"] for x in ("all_layers", "outcome") if x in layers},
        "reliability": {
            x: (layers[x]["pass_all"], layers[x]["pass_any"], layers[x]["n"])
            for x in ("all_layers", "outcome")
            if x in layers
        },
        "latency_s": {
            "p50": percentile(wall, 50),
            "p95": percentile(wall, 95),
            "max": max(wall) if wall else None,
            "n": len(wall),
        },
        "cost_usd": {
            "per_run": costs,
            "total": total,
            "per_task": total / n_tasks if n_tasks else None,
            "per_all_layers_pass": total / all_layers_passes if all_layers_passes else None,
            "all_layers_passes": all_layers_passes,
            "runs": n_tasks,
        },
        "safety": SAFETY_NOTE,
    }


def load(dirs: list[Path]) -> dict[tuple, dict]:
    out: dict[tuple, dict] = {}
    for d in dirs:
        for key, runs in load_groups(d).items():
            if len(runs) >= 2:
                out[key] = dimensions(runs)
    return out


def _money(x: float | None) -> str:
    return "n/a (no passes)" if x is None else f"${x:.2f}"


def render(results: dict[tuple, dict]) -> str:
    keys = sorted(results)
    lines = [
        (
            "| Series | Quality: all layers / outcome (mean of k runs) | "
            "Reliability: pass^k / pass@k, all layers | Latency p50 / p95 / max (s) | "
            "Cost per run (API-equiv.) | Cost per all-layers pass | Safety |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    for key in keys:
        alias, models = key
        r = results[key]
        q, rel, lat, cost = r["quality"], r["reliability"], r["latency_s"], r["cost_usd"]
        al = rel["all_layers"]
        runs = cost["per_run"]
        lines.append(
            f"| {', '.join(models) or alias} (k = {r['k']}) "
            f"| {q['all_layers']:.0%} / {q['outcome']:.0%} "
            f"| {al[0]}/{al[2]} / {al[1]}/{al[2]} "
            f"| {lat['p50']:.1f} / {lat['p95']:.1f} / {lat['max']:.1f} "
            f"| ${sum(runs) / len(runs):.2f} (${min(runs):.2f}-${max(runs):.2f}) "
            f"| {_money(cost['per_all_layers_pass'])} ({cost['all_layers_passes']} passes "
            f"in {cost['runs']} task-runs) "
            f"| not measured |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dir", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    results = load(args.dir)
    if not results:
        raise SystemExit("need at least two runs of one series")
    text = render(results)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
