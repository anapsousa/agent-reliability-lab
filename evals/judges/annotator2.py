"""Second annotator on the stance positives: export a blind set, then measure agreement.

Every stance number in this repo rests on one annotator. The judge's bar (ASSERTED recall
>= 90%) is measured against 8 positives (9 on the 6 Oct adjudication, before S010 moved),
all labelled by the same person who wrote the bar. Before those labels gate anything,
a second person labels the same positives blind.

Blinding: a set of positives only would tell the annotator the answer. So the 9 items
ever labelled ASSERTED are mixed with twice as many REFUTED decoys, shuffled with a fixed
seed and renamed (A2-01 ...). The annotator gets `items.jsonl` and `label.html`, and is
asked not to open the rest of the repo until done. The key is committed: the passages
are public anyway, so blinding rests on the instruction, and a committed key makes the
comparison reproducible.

    uv run python -m evals.judges.annotator2 export     # writes annotator-2/ (idempotent)
    uv run python -m evals.judges.annotator2 compare    # needs annotator-2/labels.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from evals.judges.stance import CAL_DIR, PASSING, STANCES, cohen_kappa, load_labels

OUT_DIR = CAL_DIR / "annotator-2"
SEED = 20261008
DECOYS_PER_POSITIVE = 2

# Pre-registered before any second label exists. PROPOSED, not yet confirmed by the
# owner: change these before the second annotator's labels are opened, never after.
BAR_POSITIVE_AGREEMENT = 8  # of the 9 positives, on the pass/fail split the scorer uses
BAR_KAPPA = 0.6  # Cohen's kappa over the whole blind set, four stances


def positives(cal_dir: Path = CAL_DIR) -> list[str]:
    """Items labelled ASSERTED in either adjudication round: the current 8, plus S010."""
    current = load_labels(cal_dir)
    earlier = json.loads((cal_dir / "labels.json").read_text())
    round2_06oct = cal_dir / "adjudicated.round2-06oct.json"
    if round2_06oct.exists():
        earlier = {**earlier, **json.loads(round2_06oct.read_text())}
    return sorted(k for k in current if current[k] == "ASSERTED" or earlier.get(k) == "ASSERTED")


def build(cal_dir: Path = CAL_DIR, seed: int = SEED) -> tuple[list[dict], dict[str, str]]:
    """(blind items, key A2-id -> S-id). Deterministic for a given seed and label set."""
    items = {
        json.loads(line)["item"]: json.loads(line)
        for line in (cal_dir / "items.jsonl").open(encoding="utf-8")
    }
    labels = load_labels(cal_dir)
    pos = positives(cal_dir)
    rng = random.Random(seed)
    pool = sorted(k for k, v in labels.items() if v == "REFUTED" and k not in pos)
    decoys = rng.sample(pool, k=min(len(pool), DECOYS_PER_POSITIVE * len(pos)))
    chosen = pos + decoys
    rng.shuffle(chosen)
    key: dict[str, str] = {}
    blind: list[dict] = []
    for n, source_id in enumerate(chosen, start=1):
        blind_id = f"A2-{n:02d}"
        key[blind_id] = source_id
        it = items[source_id]
        blind.append({"item": blind_id, "claim": it["claim"], "passage": it["passage"]})
    return blind, key


def export(out_dir: Path = OUT_DIR) -> Path:
    """Write items.jsonl, key.json and label.html. Refuses to overwrite a different set."""
    blind, key = build()
    out_dir.mkdir(parents=True, exist_ok=True)
    key_path = out_dir / "key.json"
    if key_path.exists() and json.loads(key_path.read_text()) != key:
        raise SystemExit(
            f"{key_path} exists and differs from a fresh build. The blind set changed "
            "(labels or seed). Move the old folder aside before exporting again."
        )
    if (out_dir / "labels.json").exists():
        raise SystemExit("labels.json already exists: the set is labelled, not re-exporting.")
    (out_dir / "items.jsonl").write_text(
        "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in blind), encoding="utf-8"
    )
    key_path.write_text(json.dumps(key, indent=1) + "\n", encoding="utf-8")
    template = (Path(__file__).parent / "annotator2_label.template.html").read_text()
    html = template.replace("/*ITEMS*/[]", json.dumps(blind, ensure_ascii=False))
    (out_dir / "label.html").write_text(html, encoding="utf-8")
    return out_dir


def compare(out_dir: Path = OUT_DIR, cal_dir: Path = CAL_DIR) -> dict:
    """Annotator 2 against annotator 1 (adjudicated labels). Writes agreement.json."""
    key = json.loads((out_dir / "key.json").read_text())
    second = json.loads((out_dir / "labels.json").read_text())
    unknown = sorted(set(second) - set(key))
    missing = sorted(set(key) - set(second))
    bad = {k: v for k, v in second.items() if v not in STANCES}
    if unknown or missing or bad:
        raise ValueError(f"labels.json: unknown {unknown}, missing {missing}, invalid {bad}")

    first = load_labels(cal_dir)
    pos = set(positives(cal_dir))
    ids = sorted(key)
    a = [first[key[i]] for i in ids]
    b = [second[i] for i in ids]
    on_pos = [(first[key[i]], second[i]) for i in ids if key[i] in pos]
    # Binary = the split the outcome scorer acts on: fail (ASSERTED, NEUTRAL) or pass.
    pos_binary = sum((x in PASSING) == (y in PASSING) for x, y in on_pos)
    second_asserted_on_pos = sum(y == "ASSERTED" for _, y in on_pos)
    kappa = round(cohen_kappa(a, b), 4)
    result = {
        "n": len(ids),
        "positives": len(on_pos),
        "agreement": round(sum(x == y for x, y in zip(a, b, strict=True)) / len(ids), 4),
        "binary_agreement": round(
            sum((x in PASSING) == (y in PASSING) for x, y in zip(a, b, strict=True)) / len(ids),
            4,
        ),
        "kappa": kappa,
        "positive_binary_agreement": pos_binary,
        "positive_asserted_by_second": second_asserted_on_pos,
        "second_asserted_on_decoys": sum(second[i] == "ASSERTED" for i in ids if key[i] not in pos),
        "bar": {"positive_agreement": BAR_POSITIVE_AGREEMENT, "kappa": BAR_KAPPA},
        "bar_met": pos_binary >= BAR_POSITIVE_AGREEMENT and kappa >= BAR_KAPPA,
        "disagreements": [
            {"blind": i, "item": key[i], "first": first[key[i]], "second": second[i]}
            for i in ids
            if first[key[i]] != second[i]
        ],
    }
    (out_dir / "agreement.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["export", "compare"])
    args = parser.parse_args(argv)
    if args.command == "export":
        print(f"wrote {export()}")
    else:
        r = compare()
        print(json.dumps({k: v for k, v in r.items() if k != "disagreements"}, indent=1))


if __name__ == "__main__":
    main()
