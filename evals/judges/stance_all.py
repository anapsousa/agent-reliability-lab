"""The stance judge over every regex hit in the repeat runs (all 467), scored on the 48 labels.

No instruction is changed and nothing is re-scored here. `stance.py` holds the judge and its
instructions (unchanged since October); this module only feeds it the full set in ten chunks
(`stance_repeats build --all`), keeps every verdict, and reads the result.

    uv run python -m evals.judges.stance_repeats build --all --out evals/judges/stance-all-2026-11-27
    uv run python -m evals.judges.stance_all run --model claude-sonnet-5-5
    uv run python -m evals.judges.stance_all analyse
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evals.judges import stance
from evals.judges.stance import PASSING, STANCES, calibration, load_labels
from evals.judges.stance_repeats import OUT_DIR as SAMPLE_DIR
from evals.judges.stance_repeats import _model
from evals.runners.claude_code import wilson

HERE = Path(__file__).parent
ALL_DIR = HERE / "stance-all-2026-11-27"
MODEL = "claude-sonnet-5-5"
CHUNKS = 10


def chunks(items: list[dict], n: int = CHUNKS) -> list[list[dict]]:
    """`n` contiguous chunks of near-equal size, in item order (467 -> 47 x 7 + 46 x 3)."""
    size, extra = divmod(len(items), n)
    out, at = [], 0
    for i in range(n):
        step = size + (1 if i < extra else 0)
        out.append(items[at : at + step])
        at += step
    return out


def run_file(model: str, n: int, out_dir: Path = ALL_DIR) -> Path:
    return out_dir / f"judge-{model}-run{n:02d}.json"


def run(model: str = MODEL, out_dir: Path = ALL_DIR, judge_many=stance.judge_many) -> list[Path]:
    """Judge every chunk with `--fresh` semantics; a finished chunk file is never redone."""
    items = [json.loads(x) for x in (out_dir / "items.jsonl").read_text("utf-8").splitlines()]
    written = []
    for n, part in enumerate(chunks(items), 1):
        path = run_file(model, n, out_dir)
        if path.exists():
            continue
        verdicts = judge_many([(it["claim"], it["passage"]) for it in part], model, fresh=True)
        result = {
            "model": model,
            "models_used": sorted({m for v in verdicts for m in v.get("models_used", [])}),
            "effort": "low",
            "fresh": True,
            "chunk": n,
            "n": len(part),
            "verdicts": {
                it["item"]: {"stance": v["stance"], "reason": v.get("reason", "")}
                for it, v in zip(part, verdicts, strict=True)
            },
        }
        path.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
        print(f"chunk {n:02d}/{CHUNKS}: {len(part)} verdicts", flush=True)
    return written


def load_verdicts(model: str = MODEL, out_dir: Path = ALL_DIR) -> tuple[dict[str, dict], list[str]]:
    """item -> {stance, reason, chunk} over every chunk file, and the model ids billed."""
    verdicts, used = {}, set()
    for path in sorted(out_dir.glob(f"judge-{model}-run*.json")):
        r = json.loads(path.read_text("utf-8"))
        used.update(r.get("models_used", []))
        for item, v in r["verdicts"].items():
            verdicts[item] = {**v, "chunk": r["chunk"]}
    return verdicts, sorted(used)


def _share(stances: list[str], which: str = "ASSERTED") -> dict:
    n = len(stances)
    low, high = wilson(stances.count(which), n)
    return {
        "n": n,
        **{s: stances.count(s) for s in STANCES},
        "asserted_share": round(stances.count("ASSERTED") / n, 4) if n else None,
        "wilson95": [low, high],
    }


def analyse(model: str = MODEL, out_dir: Path = ALL_DIR, sample_dir: Path = SAMPLE_DIR) -> dict:
    """Score on the labelled 48, then read the other passages.

    The 48 live in the all-467 set under different item numbers (the full set is shuffled as
    a whole), so they are matched on the exact (claim, passage) text.
    """
    verdicts, used = load_verdicts(model, out_dir)
    items = {
        it["item"]: it
        for it in map(json.loads, (out_dir / "items.jsonl").read_text("utf-8").splitlines())
    }
    key = json.loads((out_dir / "key.json").read_text("utf-8"))
    missing = sorted(set(items) - set(verdicts))
    if missing:
        raise SystemExit(f"{len(missing)} items have no verdict yet: {missing[:5]}...")
    by_text = {(it["claim"], it["passage"]): name for name, it in items.items()}

    labels = load_labels(sample_dir)
    sample = [json.loads(x) for x in (sample_dir / "items.jsonl").read_text("utf-8").splitlines()]
    matched = {}
    for it in sample:
        name = by_text.get((it["claim"], it["passage"]))
        if name is None:
            raise SystemExit(f"sample item {it['item']} is not in the all-467 set")
        matched[it["item"]] = name
    human = [labels[it["item"]] for it in sample]
    judged = [verdicts[matched[it["item"]]]["stance"] for it in sample]
    scored = calibration(human, judged)
    positives = human.count("ASSERTED")
    caught = sum(1 for h, j in zip(human, judged, strict=True) if h == "ASSERTED" == j)
    scored["asserted_positives"] = positives
    scored["asserted_caught"] = caught
    scored["asserted_recall_wilson95"] = list(wilson(caught, positives))
    scored["refuted_called_failure"] = sum(
        1 for h, j in zip(human, judged, strict=True) if h == "REFUTED" and j not in PASSING
    )
    scored["refuted_n"] = human.count("REFUTED")
    scored["disagreements"] = [
        {
            "sample_item": it["item"],
            "all_item": matched[it["item"]],
            "human": h,
            "judge": j,
            "reason": verdicts[matched[it["item"]]]["reason"],
        }
        for it, h, j in zip(sample, human, judged, strict=True)
        if h != j
    ]

    inside = set(matched.values())
    rest = sorted(set(items) - inside)

    def where(name: str) -> tuple[str, str]:
        return _model(key[name]), key[name][0]["report"]

    def block(names: list[str]) -> dict:
        per_model, per_run = {}, {}
        for model_id in sorted({where(n)[0] for n in names}):
            per_model[model_id] = _share(
                [verdicts[n]["stance"] for n in names if where(n)[0] == model_id]
            )
        for report in sorted({where(n)[1] for n in names}):
            per_run[report] = {
                "model": next(where(n)[0] for n in names if where(n)[1] == report),
                **_share([verdicts[n]["stance"] for n in names if where(n)[1] == report]),
            }
        return {
            "all": _share([verdicts[n]["stance"] for n in names]),
            "per_model": per_model,
            "per_run": per_run,
        }

    return {
        "model": model,
        "models_used": used,
        "effort": "low",
        "items": len(items),
        "scored_on_the_labelled_sample": scored,
        "the_other_passages": {"n": len(rest), **block(rest)},
        "every_passage": block(sorted(items)),
        "asserted_items": [
            {
                "item": n,
                "model": where(n)[0],
                "report": where(n)[1],
                "task": key[n][0]["task"],
                "labelled": n in inside,
                "reason": verdicts[n]["reason"],
            }
            for n in sorted(items)
            if verdicts[n]["stance"] == "ASSERTED"
        ],
        "chunk_stance_counts": {
            c: dict(Counter(v["stance"] for v in verdicts.values() if v["chunk"] == c))
            for c in sorted({v["chunk"] for v in verdicts.values()})
        },
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["run", "analyse"])
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--dir", type=Path, default=ALL_DIR)
    args = parser.parse_args(argv)
    if args.command == "run":
        run(args.model, args.dir)
    else:
        result = analyse(args.model, args.dir)
        (args.dir / "summary.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps({k: result[k] for k in ("model", "models_used", "items")}, indent=1))


if __name__ == "__main__":
    main()
