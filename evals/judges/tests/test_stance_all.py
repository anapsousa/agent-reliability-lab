"""The full-set stance run: chunking, resumability, and the join back to the 48 labels."""

from __future__ import annotations

import json

from evals.judges import stance_all as sa
from evals.judges import stance_repeats as sr


def test_chunks_cover_every_item_once_in_order():
    items = [{"item": f"R{n:03d}"} for n in range(467)]
    parts = sa.chunks(items)
    assert len(parts) == sa.CHUNKS
    assert [len(p) for p in parts] == [47] * 7 + [46] * 3
    assert [it for p in parts for it in p] == items


def test_the_committed_all_set_is_the_full_build():
    items = (sa.ALL_DIR / "items.jsonl").read_text("utf-8").splitlines()
    assert len(items) == sr.collect()["distinct"] == 467


def test_every_labelled_sample_passage_is_in_the_full_set_exactly_once():
    full = [json.loads(x) for x in (sa.ALL_DIR / "items.jsonl").read_text("utf-8").splitlines()]
    texts = [(it["claim"], it["passage"]) for it in full]
    sample = [json.loads(x) for x in (sr.OUT_DIR / "items.jsonl").read_text("utf-8").splitlines()]
    for it in sample:
        assert texts.count((it["claim"], it["passage"])) == 1


def test_run_writes_one_file_per_chunk_and_never_redoes_a_finished_one(tmp_path):
    items = [{"item": f"R{n:03d}", "claim": "c", "passage": f"p{n}"} for n in range(25)]
    (tmp_path / "items.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
    calls = []

    def fake(pairs, model, fresh):
        assert fresh is True
        calls.append(len(pairs))
        return [{"stance": "REFUTED", "reason": "r", "models_used": [model]} for _ in pairs]

    sa.run("m", tmp_path, judge_many=fake)
    assert sum(calls) == 25 and len(calls) == sa.CHUNKS
    first = len(calls)
    sa.run("m", tmp_path, judge_many=fake)
    assert len(calls) == first
    verdicts, used = sa.load_verdicts("m", tmp_path)
    assert len(verdicts) == 25 and used == ["m"]
