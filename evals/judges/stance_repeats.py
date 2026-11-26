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
    uv run python -m evals.judges.stance_repeats score    # ASSERTED share per model
    uv run python -m evals.judges.stance_repeats reread   # blind four-option sheet, reread/
    uv run python -m evals.judges.stance_repeats apply    # reread/labels.json -> adjudicated.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from evals.fixtures.corpus import load_corpus
from evals.judges.stance import CAL_DIR, PASSING, STANCES, load_labels
from evals.rescore import labels_by_passage
from evals.runners.claude_code import wilson
from evals.scorers.outcome import _compile, passage_around
from evals.tasks.research_agent import load_golden

HERE = Path(__file__).parent
REPORTS = HERE.parent / "reports"
REPEAT_DIRS = (REPORTS / "repeats-2026-10-12", REPORTS / "repeats-2026-11-02")
OUT_DIR = HERE / "stance-repeats-2026-11-07"
TEMPLATE = CAL_DIR / "label.html"
SEED = 20261107
SAMPLE = 48
REREAD_SEED = 20261124
DECOYS_PER_CONTESTED = 2
REREAD_TEMPLATE = HERE / "annotator2_label.template.html"


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


def score(out_dir: Path = OUT_DIR) -> dict:
    """ASSERTED share of the labelled sample per model, with `adjudicated.json` laid over."""
    labels = load_labels(out_dir)
    key = json.loads((out_dir / "key.json").read_text(encoding="utf-8"))
    rows = {}
    for model in sorted({_model(v) for v in key.values()}) + ["all"]:
        got = [labels[k] for k, v in key.items() if model in ("all", _model(v))]
        low, high = wilson(got.count("ASSERTED"), len(got))
        rows[model] = {
            "n": len(got),
            **{s: got.count(s) for s in STANCES},
            "asserted_share": round(got.count("ASSERTED") / len(got), 4),
            "wilson95": [round(low, 4), round(high, 4)],
        }
    return rows


def judge_runs(out_dir: Path = OUT_DIR) -> list[dict]:
    """Every committed judge run over this set that kept its per-item verdicts."""
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("judge-*.json"))]
    return [r for r in runs if "verdicts" in r]


def contested(out_dir: Path = OUT_DIR) -> tuple[list[str], list[str]]:
    """(items to re-read, agreed-REFUTED pool for decoys).

    Re-read: every item on which any judge run differs from the owner's label, plus every
    item labelled ASSERTED or NEUTRAL (the sheet had no UNRELATED option to give them).
    """
    labels = json.loads((out_dir / "labels.json").read_text(encoding="utf-8"))
    runs = judge_runs(out_dir)
    if not runs:
        raise SystemExit("no judge-*.json with verdicts here: run stance calibrate first")
    differ = {k for k in labels for r in runs if r["verdicts"][k] != labels[k]}
    again = sorted(differ | {k for k, v in labels.items() if v not in PASSING})
    pool = sorted(k for k, v in labels.items() if v == "REFUTED" and k not in differ)
    return again, pool


def reread(out_dir: Path = OUT_DIR) -> dict:
    """Write `reread/`: the contested items among twice as many decoys, renamed and shuffled.

    Blind to the first label and to the judge. The key is committed (the passages are
    public), so blinding rests on not opening it, as with annotator 2.
    """
    again, pool = contested(out_dir)
    rng = random.Random(REREAD_SEED)
    chosen = again + rng.sample(pool, k=min(len(pool), DECOYS_PER_CONTESTED * len(again)))
    rng.shuffle(chosen)
    source = {
        json.loads(line)["item"]: json.loads(line)
        for line in (out_dir / "items.jsonl").open(encoding="utf-8")
    }
    key = {f"J{n:02d}": item for n, item in enumerate(chosen, 1)}
    blind = [
        {"item": j, "claim": source[r]["claim"], "passage": source[r]["passage"]}
        for j, r in key.items()
    ]
    target = out_dir / "reread"
    if (target / "labels.json").exists():
        raise SystemExit("reread/labels.json exists: the set is labelled, not rebuilding it.")
    target.mkdir(parents=True, exist_ok=True)
    (target / "items.jsonl").write_text(
        "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in blind), encoding="utf-8"
    )
    (target / "key.json").write_text(json.dumps(key, indent=1) + "\n", encoding="utf-8")
    html = (
        REREAD_TEMPLATE.read_text(encoding="utf-8")
        .replace("Stance labelling, annotator 2", "Stance re-read, repeat-run sample")
        .replace("ral-annotator2-labels", "ral-stance-repeats-reread-2026-11-24")
        .replace("/*ITEMS*/[]", json.dumps(blind, ensure_ascii=False).replace("</", "<\\/"))
    )
    (target / "label.html").write_text(html, encoding="utf-8")
    return {"contested": len(again), "decoys": len(chosen) - len(again), "items": len(chosen)}


def apply(out_dir: Path = OUT_DIR) -> dict:
    """Map the re-read's labels back to sample ids and write `adjudicated.json`.

    Every re-read item is written, decoys included, so a decoy that changes is on record.
    """
    key = json.loads((out_dir / "reread" / "key.json").read_text(encoding="utf-8"))
    second = json.loads((out_dir / "reread" / "labels.json").read_text(encoding="utf-8"))
    unknown, missing = sorted(set(second) - set(key)), sorted(set(key) - set(second))
    bad = {k: v for k, v in second.items() if v not in STANCES}
    if unknown or missing or bad:
        raise ValueError(f"reread/labels.json: unknown {unknown}, missing {missing}, bad {bad}")
    first = json.loads((out_dir / "labels.json").read_text(encoding="utf-8"))
    adjudicated = {key[j]: second[j] for j in sorted(key)}
    (out_dir / "adjudicated.json").write_text(
        json.dumps(dict(sorted(adjudicated.items())), indent=1) + "\n", encoding="utf-8"
    )
    return {
        "reread": len(adjudicated),
        "changed": {k: [first[k], v] for k, v in sorted(adjudicated.items()) if first[k] != v},
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["build", "count", "score", "reread", "apply"])
    parser.add_argument("--all", action="store_true", help="every passage, not the sample")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    if args.command == "build":
        print(json.dumps(build(args.out, None if args.all else SAMPLE), indent=1))
    elif args.command in ("score", "reread", "apply"):
        print(
            json.dumps({"score": score, "reread": reread, "apply": apply}[args.command](args.out))
        )
    else:
        found = collect()
        print(json.dumps({k: found[k] for k in ("hits", "distinct", "already_labelled")}))
        print("fresh:", len(found["fresh"]))


if __name__ == "__main__":
    main()
