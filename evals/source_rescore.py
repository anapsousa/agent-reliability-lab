"""Re-score stored answers with the forbidden-source heuristic. No model is called.

`must_not_cite` failed any answer in which the forbidden URL appeared, including answers
that named it only to reject it ("Excluded: <url> (AI-generated, unsourced)"). This module
re-runs the existing outcome scorer over the answers stored in the committed reports with
one change: `source_use=forbidden_source_stance` (evals/scorers/outcome.py), so the URL
counts as cited only when some mention of it is support or carries no verdict. Every other
check, the golden set and the stored trajectory and component verdicts are untouched, so
any movement is attributable to that check alone.

Covered: the 23 Sep baseline (three models, also combined with the human stance labels
from `evals.rescore`) and the 12 Oct repeats (haiku-5-5 and sonnet-5-5, three runs each).

Every mention was also read once, by the assistant, not by the owner
(`judges/forbidden-source-2026-10-20/reader.json`). That reading checks the heuristic's
bar (tests) and gives an upper bound only: what the rate would be if the mentions that
critique the source without saying it was not used were passed as well.

    uv run python -m evals.source_rescore                  # prints the markdown tables
    uv run python -m evals.source_rescore --json out.json  # also writes the numbers
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evals.fixtures.corpus import load_corpus
from evals.rescore import _category, label_stance, labels_by_passage
from evals.runners.claude_code import wilson
from evals.scorers.outcome import (
    StanceFn,
    evaluate_outcome,
    forbidden_source_mentions,
    forbidden_source_stance,
)
from evals.tasks.research_agent import load_golden

REPORTS = Path(__file__).parent / "reports"
BASELINE_GLOB = "research-agent-v1-claude-code-*-2026-09-23T*.json"
REPEATS = REPORTS / "repeats-2026-10-12"
READER = Path(__file__).parent / "judges" / "forbidden-source-2026-10-20" / "reader.json"
MODELS = ("haiku", "sonnet", "opus")
# Reader categories, one per mention. Only "critique" (names the source while finding
# fault with it, with no "not used") is lifted in the upper bound; support, a bare listing
# and a description with no verdict stay cited.
READER_CATEGORIES = ("rejection", "support", "bare", "described", "critique")
CITED = "cited forbidden source"


def _rate(passes: int, n: int) -> dict:
    return {"passed": passes, "rate": round(passes / n, 4), "ci95": wilson(passes, n)}


def mention_key(report_name: str, task_id: str, line_no: int) -> str:
    return f"{report_name}|{task_id}|L{line_no}"


def load_reader(path: Path = READER) -> dict[str, str]:
    if not path.exists():
        return {}
    labels = json.loads(path.read_text(encoding="utf-8"))["labels"]
    bad = {k: v for k, v in labels.items() if v not in READER_CATEGORIES}
    if bad:
        raise ValueError(f"{path.name}: unknown categories {bad}")
    return labels


def rescore_report(
    name: str,
    report: dict,
    golden: dict[str, dict],
    ground_truth: dict,
    stance: StanceFn | None = None,
    reader: dict[str, str] | None = None,
) -> dict:
    """Before = lexical forbidden-source rule, after = heuristic; `stance` applies to both."""
    rows = []
    for task in report["tasks"]:
        spec = golden[task["id"]]
        lexical = evaluate_outcome(task["answer"], spec["expected"], ground_truth)
        if lexical.passed != task["scores"]["outcome"]["passed"]:
            raise ValueError(f"{name} {task['id']}: stored outcome verdict does not match")
        before = evaluate_outcome(task["answer"], spec["expected"], ground_truth, stance=stance)
        after = evaluate_outcome(
            task["answer"],
            spec["expected"],
            ground_truth,
            stance=stance,
            source_use=forbidden_source_stance,
        )
        mentions = [
            (url, m)
            for url in spec["expected"].get("must_not_cite", [])
            for m in forbidden_source_mentions(task["answer"], url)
        ]
        residual = [
            mention_key(name, task["id"], m.line_no) for _u, m in mentions if m.stance == "ASSERTED"
        ]
        # Upper bound: lift this run's forbidden-source failure if every residual mention
        # was read as critique. Any other failure still fails it.
        others = [f for f in after.failures if not f.startswith(CITED)]
        lifted = (
            bool(reader)
            and any(f.startswith(CITED) for f in after.failures)
            and all(reader.get(k) == "critique" for k in residual)
        )
        upper = after.passed or (lifted and not others)
        rest = all(task["scores"][k]["passed"] for k in ("trajectory", "components"))
        rows.append(
            {
                "id": task["id"],
                "before": before.passed,
                "after": after.passed,
                "upper": upper,
                "all_before": before.passed and rest,
                "all_after": after.passed and rest,
                "all_upper": upper and rest,
                "cited_before": any(f.startswith(CITED) for f in before.failures),
                "cited_after": any(f.startswith(CITED) for f in after.failures),
                "sole_cited_after": bool(after.failures)
                and all(f.startswith(CITED) for f in after.failures),
                "mentions": Counter(m.stance for _u, m in mentions),
                "residual": residual,
                # What still fails a run this fix cleared: the reason the lift is small.
                "blocked_by": sorted({_category(f) for f in after.failures})
                if any(f.startswith(CITED) for f in before.failures)
                and not any(f.startswith(CITED) for f in after.failures)
                else [],
            }
        )
    n = len(rows)
    if any(r["before"] and not r["after"] for r in rows):
        raise AssertionError(f"{name}: the heuristic failed a run the lexical rule passed")
    mentions = sum((r["mentions"] for r in rows), Counter())
    return {
        "report": name,
        "n": n,
        "outcome_before": _rate(sum(r["before"] for r in rows), n),
        "outcome_after": _rate(sum(r["after"] for r in rows), n),
        "outcome_upper": _rate(sum(r["upper"] for r in rows), n),
        "all_before": _rate(sum(r["all_before"] for r in rows), n),
        "all_after": _rate(sum(r["all_after"] for r in rows), n),
        "all_upper": _rate(sum(r["all_upper"] for r in rows), n),
        "cited_runs_before": sum(r["cited_before"] for r in rows),
        "cited_runs_after": sum(r["cited_after"] for r in rows),
        "sole_cited_after": sum(r["sole_cited_after"] for r in rows),
        "flipped_outcome": [r["id"] for r in rows if r["after"] and not r["before"]],
        "flipped_all": [r["id"] for r in rows if r["all_after"] and not r["all_before"]],
        "mentions": {"REFUTED": mentions["REFUTED"], "ASSERTED": mentions["ASSERTED"]},
        "cleared_but_still_failing": sum(bool(r["blocked_by"]) for r in rows),
        "cleared_blocked_by": dict(Counter(c for r in rows for c in r["blocked_by"])),
        "residual": [k for r in rows for k in r["residual"]],
        "residual_runs": {
            r["id"]: sorted({(reader or {}).get(k, "unread") for k in r["residual"]})
            for r in rows
            if r["cited_after"]
        },
        "per_task": {r["id"]: {k: r[k] for k in ("before", "after", "upper")} for r in rows},
        "per_task_all": {
            r["id"]: {"before": r["all_before"], "after": r["all_after"], "upper": r["all_upper"]}
            for r in rows
        },
    }


def _load(paths: list[Path]) -> list[tuple[str, dict]]:
    return [(p.name, json.loads(p.read_text(encoding="utf-8"))) for p in paths]


def pass_k(results: list[dict], layer: str = "per_task") -> dict:
    """pass^k before/after/upper over k repeat runs of one series."""
    ids = sorted(results[0][layer])
    out = {}
    for when in ("before", "after", "upper"):
        out[when] = sum(all(r[layer][i][when] for r in results) for i in ids)
    out["n"] = len(ids)
    return out


def rescore_all(reports_dir: Path = REPORTS, repeats_dir: Path = REPEATS) -> dict:
    ground_truth = load_corpus().ground_truth
    golden = {t["id"]: t for t in load_golden()}
    reader = load_reader()
    by_passage = labels_by_passage()
    out: dict = {"baseline": {}, "repeats": {}}
    for name, report in _load(sorted(reports_dir.glob(BASELINE_GLOB))):
        model = report["model_alias"]
        out["baseline"][model] = {
            "models_seen": report.get("models_seen"),
            "alone": rescore_report(name, report, golden, ground_truth, reader=reader),
            **{
                f"stance_{bound}": rescore_report(
                    name,
                    report,
                    golden,
                    ground_truth,
                    stance=label_stance(by_passage, policy),
                    reader=reader,
                )
                for bound, policy in (("strict", "fail"), ("lenient", "pass"))
            },
        }
    for name, report in _load(sorted(repeats_dir.glob("research-agent-v1-claude-code-*.json"))):
        series = f"{report['model_alias']} ({'+'.join(report.get('models_seen') or [])})"
        out["repeats"].setdefault(series, []).append(
            rescore_report(name, report, golden, ground_truth, reader=reader)
        )
    out["repeats_passk"] = {
        s: {"outcome": pass_k(runs), "all_layers": pass_k(runs, "per_task_all")}
        for s, runs in out["repeats"].items()
    }
    return out


def _pct(cell: dict) -> str:
    lo, hi = cell["ci95"]
    return f"{cell['passed']}/40 = {cell['rate']:.0%} ({lo:.0%}-{hi:.0%})"


def render(results: dict) -> str:
    lines = [
        "Baseline 2026-09-23, forbidden-source fix alone (lexical unsupported-claims rule):",
        "",
        (
            "| Model | Outcome before | Outcome after | All layers before | All layers after "
            "| Runs failing the check (before -> after) | Tasks flipped (outcome / all layers) |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    for model in MODELS:
        r = results["baseline"][model]["alone"]
        lines.append(
            f"| {model} | {_pct(r['outcome_before'])} | {_pct(r['outcome_after'])} | "
            f"{_pct(r['all_before'])} | {_pct(r['all_after'])} | "
            f"{r['cited_runs_before']} -> {r['cited_runs_after']} | "
            f"{len(r['flipped_outcome'])} / {len(r['flipped_all'])} |"
        )
    lines += [
        "",
        "Baseline with the human stance labels as well (strict / lenient, see evals.rescore):",
        "",
        (
            "| Model | Outcome, stance labels only | Outcome, stance labels + this fix "
            "| All layers, stance labels only | All layers, stance labels + this fix |"
        ),
        "|---|---|---|---|---|",
    ]
    for model in MODELS:
        s, ll = (
            results["baseline"][model]["stance_strict"],
            results["baseline"][model]["stance_lenient"],
        )

        def pair(key: str, s=s, ll=ll) -> str:
            a, b = s[key]["passed"], ll[key]["passed"]
            return f"{a}/40 = {a / 40:.0%}" if a == b else f"{a}-{b}/40 = {a / 40:.0%}-{b / 40:.0%}"

        lines.append(
            f"| {model} | {pair('outcome_before')} | {pair('outcome_after')} | "
            f"{pair('all_before')} | {pair('all_after')} |"
        )
    lines += [
        "",
        "Repeats 2026-10-12, forbidden-source fix alone:",
        "",
        (
            "| Series | Run | Outcome before | Outcome after | All layers before | All layers after "
            "| Runs failing the check | Tasks flipped (outcome / all layers) |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    for series, runs in results["repeats"].items():
        for i, r in enumerate(runs, 1):
            lines.append(
                f"| {series} | {i} | {_pct(r['outcome_before'])} | {_pct(r['outcome_after'])} | "
                f"{_pct(r['all_before'])} | {_pct(r['all_after'])} | "
                f"{r['cited_runs_before']} -> {r['cited_runs_after']} | "
                f"{len(r['flipped_outcome'])} / {len(r['flipped_all'])} |"
            )
    lines += ["", "| Series | Layer | pass^3 before | pass^3 after |", "|---|---|---|---|"]
    for series, layers in results["repeats_passk"].items():
        for layer, p in layers.items():
            lines.append(f"| {series} | {layer} | {p['before']}/{p['n']} | {p['after']}/{p['n']} |")
    return "\n".join(lines) + "\n"


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
