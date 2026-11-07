"""The repeat-run stance set: blind, stratified, reproducible, and consistent with the key."""

from __future__ import annotations

import json

from evals.judges import stance_repeats as sr


def test_the_committed_set_rebuilds_byte_for_byte(tmp_path):
    sr.build(tmp_path)
    for name in ("items.jsonl", "key.json", "label.html"):
        assert (tmp_path / name).read_bytes() == (sr.OUT_DIR / name).read_bytes(), name


def test_items_carry_no_model_task_or_run():
    for line in (sr.OUT_DIR / "items.jsonl").read_text(encoding="utf-8").splitlines():
        assert set(json.loads(line)) == {"item", "claim", "passage"}


def test_the_sample_is_split_evenly_across_the_models_and_is_all_fresh():
    key = json.loads((sr.OUT_DIR / "key.json").read_text(encoding="utf-8"))
    models = [sr._model(v) for v in key.values()]
    assert len(key) == sr.SAMPLE
    assert {m: models.count(m) for m in set(models)} == {m: sr.SAMPLE // 3 for m in set(models)}
    assert len(set(models)) == 3


def test_the_sheet_has_its_own_storage_key_and_every_item():
    html = (sr.OUT_DIR / "label.html").read_text(encoding="utf-8")
    items = (sr.OUT_DIR / "items.jsonl").read_text(encoding="utf-8").splitlines()
    assert 'const KEY="stance-repeats-2026-11-07"' in html
    assert all(json.loads(line)["item"] in html for line in items)
    assert 'KEY="stance-2026-09-23"' not in html


def test_the_full_set_is_every_hit_and_none_is_covered_by_a_baseline_label():
    found = sr.collect()
    assert found["already_labelled"] == 0
    assert len(sr.pick(found["fresh"], None)) == len(found["fresh"]) == found["distinct"]
