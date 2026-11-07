"""A blind stance-label set for the repeat runs. No model is called.

The baseline's stance labels (`stance-2026-09-23/`) are keyed to the baseline's passages, so
they do not clear the `unsupported_claims` regex on the repeat runs: 125 of the 126 runs
the forbidden-source fix clears still fail it (`reports/forbidden-source-rescore-2026-11-06.md`).
This module collects every distinct (claim, passage) the regex hits across the nine repeat
runs, drops the ones a baseline label already covers, samples and shuffles
them with a fixed seed and writes the items without model, task or run attached. The key (item -> where it
occurred) is written beside them for scoring, not for the labeller.

    uv run python -m evals.judges.stance_repeats build    # 48-passage sample under OUT_DIR
    uv run python -m evals.judges.stance_repeats build --all --out /tmp/x   # every passage
    uv run python -m evals.judges.stance_repeats count    # prints the numbers only
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from evals.fixtures.corpus import load_corpus
from evals.judges.stance import CAL_DIR
from evals.rescore import labels_by_passage
from evals.scorers.outcome import _compile, passage_around
from evals.tasks.research_agent import load_golden

HERE = Path(__file__).parent
REPORTS = HERE.parent / "reports"
REPEAT_DIRS = (REPORTS / "repeats-2026-10-12", REPORTS / "repeats-2026-11-02")
OUT_DIR = HERE / "stance-repeats-2026-11-07"
TEMPLATE = CAL_DIR / "label.html"
SEED = 20261107
SAMPLE = 48


def hits(report: dict, golden: dict[str, dict], ground_truth: dict) -> list[tuple[str, str, str]]:
    """(task id, claim, passage) for every unsupported-claim regex hit in one report."""
    out = []
    for task in report["tasks"]:
        allowed = set(golden[task["id"]]["expected"].get("allow_unsupported_mention") or [])
        for claim in ground_truth.get("unsupported_claims", []):
            if claim["claim"] in allowed:
                continue
            match = _compile(claim["pattern"], "ground truth unsupported_claims").search(
                task["answer"]
            )
            if match:
                out.append((task["id"], claim["claim"], passage_around(task["answer"], match)))
    return out


def collect() -> dict:
    ground_truth = load_corpus().ground_truth
    golden = {t["id"]: t for t in load_golden()}
    baseline = labels_by_passage()
    seen: dict[tuple[str, str], list[dict]] = {}
    total = 0
    for directory in REPEAT_DIRS:
        for path in sorted(directory.glob("research-agent-v1-claude-code-*.json")):
            report = json.loads(path.read_text(encoding="utf-8"))
            for task_id, claim, passage in hits(report, golden, ground_truth):
                total += 1
                seen.setdefault((claim, passage), []).append(
                    {"report": path.name, "model": report["models_seen"], "task": task_id}
                )
    fresh = {k: v for k, v in seen.items() if k[1] not in baseline}
    return {
        "hits": total,
        "distinct": len(seen),
        "already_labelled": len(seen) - len(fresh),
        "fresh": fresh,
    }


def _model(entries: list[dict]) -> str:
    models = entries[0]["model"]
    return models[0] if isinstance(models, list) else str(models)


def pick(fresh: dict, size: int | None) -> list[tuple[str, str]]:
    """The passages to label: all of them, or `size` split evenly across the models.

    Every regex hit is its own passage (467 of 467 distinct), too many to read by hand, and
    what the rescore needs is the share of hits that are assertions, which a sample
    estimates. Stratified so no model's hits are over-read; seeded so the set rebuilds.
    """
    rng = random.Random(SEED)
    if size is None:
        keys = sorted(fresh)
        rng.shuffle(keys)
        return keys
    by_model: dict[str, list[tuple[str, str]]] = {}
    for k in sorted(fresh):
        by_model.setdefault(_model(fresh[k]), []).append(k)
    per = size // len(by_model)
    keys = []
    for model in sorted(by_model):
        rng.shuffle(by_model[model])
        keys += by_model[model][:per]
    rng.shuffle(keys)
    return keys


def build(out_dir: Path = OUT_DIR, size: int | None = SAMPLE) -> dict:
    found = collect()
    keys = pick(found["fresh"], size)
    items, key = [], {}
    for n, (claim, passage) in enumerate(keys, 1):
        name = f"R{n:03d}"
        items.append({"item": name, "claim": claim, "passage": passage})
        key[name] = found["fresh"][(claim, passage)]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "items.jsonl").write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8"
    )
    (out_dir / "key.json").write_text(
        json.dumps(key, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "label.html").write_text(render_html(items), encoding="utf-8")
    return {k: found[k] for k in ("hits", "distinct", "already_labelled")} | {"items": len(items)}


def render_html(items: list[dict]) -> str:
    """The baseline's label sheet with the items swapped and its own storage key."""
    lines = TEMPLATE.read_text(encoding="utf-8").split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("const ITEMS="))
    lines[at] = (
        'const KEY="stance-repeats-2026-11-07";const ITEMS='
        + json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
        + ";"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["build", "count"])
    parser.add_argument("--all", action="store_true", help="every passage, not the sample")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    if args.command == "build":
        print(json.dumps(build(args.out, None if args.all else SAMPLE), indent=1))
    else:
        found = collect()
        print(json.dumps({k: found[k] for k in ("hits", "distinct", "already_labelled")}))
        print("fresh:", len(found["fresh"]))


if __name__ == "__main__":
    main()
