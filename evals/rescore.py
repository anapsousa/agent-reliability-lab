"""Re-score stored transcripts with the human stance labels. No model is called.

The first baseline's outcome layer fails any answer in which a tier-4 figure appears,
even when the answer quotes it to reject it. This module re-runs the *existing* outcome
scorer over the answers stored in `evals/reports/*.json`, with one change: each
unsupported-claim regex hit is decided by the human label for that passage
(`stance.load_labels()`: round-1 labels with the adjudication laid over them) instead of
failing automatically. The scorer, the golden set and the stored trajectory and component
verdicts are untouched, so any movement is attributable to the stance labels alone.

    uv run python -m evals.rescore                    # prints the markdown tables
    uv run python -m evals.rescore --json out.json    # also writes the numbers
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evals.fixtures.corpus import load_corpus
from evals.judges.stance import CAL_DIR, load_labels
from evals.runners.claude_code import wilson
from evals.scorers.outcome import StanceFn, evaluate_outcome
from evals.tasks.research_agent import load_golden

REPORTS = Path(__file__).parent / "reports"
MODELS = ("haiku", "sonnet", "opus")


def labels_by_passage(cal_dir: Path = CAL_DIR) -> dict[str, str]:
    """passage -> stance. Items were de-duplicated per passage, so the passage is the key.

    One passage can match two claims (a profile line quoting both the ARR and the
    customer count); it was labelled once and the label applies to both.
    """
    labels = load_labels(cal_dir)
    out: dict[str, str] = {}
    for line in (cal_dir / "items.jsonl").open(encoding="utf-8"):
        item = json.loads(line)
        if item["passage"] in out and out[item["passage"]] != labels[item["item"]]:
            raise ValueError(f"{item['item']}: same passage labelled two ways")
        out[item["passage"]] = labels[item["item"]]
    return out


def label_stance(by_passage: dict[str, str], unlabelled: str) -> StanceFn:
    """Stance function backed by the human labels.

    A regex hit can fall outside the labelled set: round 1 labelled 94 passages covering
    three of the four tier-4 claims, so hits on the fourth ($40M ARR) in a paragraph of
    their own were never seen by a human. `unlabelled` says what to do with them:
    "fail" keeps the regex behaviour (a lower bound on the pass rate), "pass" ignores
    them (an upper bound). Reporting both shows how much the open question matters.
    """
    if unlabelled not in ("fail", "pass"):
        raise ValueError(unlabelled)

    def stance(claim: str, passage: str) -> str:
        if passage in by_passage:
            return by_passage[passage]
        return "ASSERTED" if unlabelled == "fail" else "REFUTED"

    return stance


def _category(failure: str) -> str:
    for prefix in (
        "unsupported claim",
        "cited forbidden source",
        "fabricated URL",
        "missing required citation",
        "did not mention",
        "mentioned forbidden",
        "missing section",
    ):
        if failure.startswith(prefix):
            return prefix
    return "other"


def _rate(passes: int, n: int) -> dict:
    return {"passed": passes, "rate": round(passes / n, 4), "ci95": wilson(passes, n)}


def rescore_report(report: dict, golden: dict[str, dict], ground_truth: dict, stance: StanceFn):
    rows = []
    for task in report["tasks"]:
        spec = golden[task["id"]]
        before = evaluate_outcome(task["answer"], spec["expected"], ground_truth)
        after = evaluate_outcome(task["answer"], spec["expected"], ground_truth, stance=stance)
        if before.passed != task["scores"]["outcome"]["passed"]:
            raise ValueError(f"{task['id']}: stored outcome verdict does not match the scorer")
        rest = all(task["scores"][k]["passed"] for k in ("trajectory", "components"))
        rows.append(
            {
                "id": task["id"],
                "before": before,
                "after": after,
                "all_before": before.passed and rest,
                "all_after": after.passed and rest,
            }
        )
    n = len(rows)
    return {
        "n": n,
        "outcome_before": _rate(sum(r["before"].passed for r in rows), n),
        "outcome_after": _rate(sum(r["after"].passed for r in rows), n),
        "all_before": _rate(sum(r["all_before"] for r in rows), n),
        "all_after": _rate(sum(r["all_after"] for r in rows), n),
        "failing_runs_by_check_before": dict(
            Counter(c for r in rows for c in {_category(f) for f in r["before"].failures})
        ),
        "failing_runs_by_check_after": dict(
            Counter(c for r in rows for c in {_category(f) for f in r["after"].failures})
        ),
        "sole_failure_after": dict(
            Counter(
                next(iter({_category(f) for f in r["after"].failures}))
                for r in rows
                if len({_category(f) for f in r["after"].failures}) == 1
            )
        ),
        "regex_hit_runs": sum(
            any(f.startswith("unsupported claim") for f in r["before"].failures) for r in rows
        ),
    }


def rescore_all(reports_dir: Path = REPORTS) -> dict[str, dict[str, dict]]:
    """{"strict": {model: ...}, "lenient": {model: ...}}, see `label_stance`."""
    ground_truth = load_corpus().ground_truth
    golden = {t["id"]: t for t in load_golden()}
    by_passage = labels_by_passage()
    out: dict[str, dict[str, dict]] = {}
    for bound, unlabelled in (("strict", "fail"), ("lenient", "pass")):
        stance = label_stance(by_passage, unlabelled)
        newest: dict[str, dict] = {}
        for path in sorted(reports_dir.glob("research-agent-v1-claude-code-*.json")):
            report = json.loads(path.read_text(encoding="utf-8"))
            newest[report["model_alias"]] = {
                "report": path.name,
                **rescore_report(report, golden, ground_truth, stance),
            }
        out[bound] = newest
    return out


def _pct(cell: dict) -> str:
    lo, hi = cell["ci95"]
    return f"{cell['rate']:.0%} ({lo:.0%}-{hi:.0%})"


def render(results: dict[str, dict[str, dict]]) -> str:
    lines = []
    for bound, note in (
        ("strict", "hits no human saw still fail (lower bound)"),
        ("lenient", "hits no human saw are ignored (upper bound)"),
    ):
        lines += [
            f"{bound}: {note}",
            "",
            "| Model | Outcome before | Outcome after | All layers before | All layers after |",
            "|---|---|---|---|---|",
        ]
        for model in MODELS:
            r = results[bound][model]
            lines.append(
                f"| {model} | {_pct(r['outcome_before'])} | {_pct(r['outcome_after'])} | "
                f"{_pct(r['all_before'])} | {_pct(r['all_after'])} |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", type=Path, help="also write the numbers here")
    args = parser.parse_args(argv)
    results = rescore_all()
    print(render(results))
    if args.json:
        args.json.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
