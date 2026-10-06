"""Regression gate: a PR may not make the agent worse, or change it unmeasured.

Evals run locally on the Claude subscription (`evals/runners/claude_code.py`) and the
reports are committed. CI cannot re-run them — it holds no Claude credentials, and
must not — so the gate checks the evidence rather than regenerating it:

1. **Regression.** For every (agent, harness, model) series, the newest report on the
   PR is compared with the newest on the base branch. If the all-layers pass rate,
   or the outcome pass rate, fell by more than TOLERANCE, the PR fails.
2. **Unmeasured change.** If anything under `agent/` changed and the PR adds no new
   report, the PR fails. A prompt edit with no measurement is exactly the change this
   lab exists to stop.

TOLERANCE is 15 points (CLAUDE.md, decision #2, revised 2026-10-06). The first version
was 5 points, which on 40 tasks is two tasks, well inside the ±15-point Wilson interval
of a single run: it would have flagged noise and said nothing about real change. 15 is
what one 40-task run can resolve (a test pins this to the Wilson half-width at p = 0.5).
The gate is still a policy line, not a significance test: it catches a large regression,
not a subtle one, and the difference between two noisy runs is wider still (about ±21
points at p = 0.4). Tightening it needs more tasks or repeated runs (k >= 3), not a
smaller number. The report's CI columns are there so nobody mistakes one for the other.

    uv run python -m evals.gate --base origin/main
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORTS = "evals/reports"
TOLERANCE = 0.15
GATED_LAYERS = ("all_layers", "outcome")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def series_key(report: dict) -> tuple[str, str, str]:
    return (report["agent"], report.get("harness", "inspect"), report.get("model_alias", "?"))


def newest_by_series(reports: dict[str, dict]) -> dict[tuple, tuple[str, dict]]:
    """Newest report per series. Filenames end in a UTC stamp, so name order is time order."""
    newest: dict[tuple, tuple[str, dict]] = {}
    for name in sorted(reports):
        newest[series_key(reports[name])] = (name, reports[name])
    return newest


def compare(
    base: dict[str, dict],
    head: dict[str, dict],
    agent_changed: bool,
    tolerance: float = TOLERANCE,
) -> list[str]:
    """Return the gate's failures; empty means the PR passes."""
    failures: list[str] = []
    added = set(head) - set(base)
    if agent_changed and not added:
        failures.append(
            "agent/ changed but no new report was committed to evals/reports/ — "
            "run `uv run python -m evals.runners.claude_code` and commit the report"
        )
    base_new = newest_by_series(base)
    for key, (name, report) in newest_by_series(head).items():
        if name not in added or key not in base_new:
            continue  # nothing new in this series, or a brand-new series with no baseline
        base_name, base_report = base_new[key]
        for layer in GATED_LAYERS:
            was = base_report["summary"][layer]["rate"]
            now = report["summary"][layer]["rate"]
            if now < was - tolerance:
                failures.append(
                    f"{'/'.join(key)} {layer}: {now:.0%} vs {was:.0%} on base "
                    f"({name} vs {base_name}), a drop of {was - now:.0%} "
                    f"> {tolerance:.0%} tolerance"
                )
    return failures


def reports_at(ref: str | None) -> dict[str, dict]:
    if ref is None:
        return {
            p.name: json.loads(p.read_text(encoding="utf-8"))
            for p in (REPO / REPORTS).glob("*.json")
        }
    names = _git("ls-tree", "--name-only", ref, f"{REPORTS}/").split()
    return {
        Path(n).name: json.loads(_git("show", f"{ref}:{n}")) for n in names if n.endswith(".json")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval regression gate")
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)

    merge_base = _git("merge-base", args.base, "HEAD").strip()
    changed = _git("diff", "--name-only", merge_base, "HEAD").split()
    agent_changed = any(p.startswith("agent/") for p in changed)

    failures = compare(reports_at(merge_base), reports_at(None), agent_changed)
    for f in failures:
        print(f"GATE FAIL: {f}")
    if not failures:
        print(f"gate ok (agent changed: {agent_changed})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
