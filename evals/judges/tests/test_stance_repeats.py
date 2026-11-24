"""The repeat-run stance set: blind, stratified, reproducible, and consistent with the key."""

from __future__ import annotations

import json
import shutil

import pytest

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


def test_score_reproduces_the_committed_first_reading():
    first = json.loads((sr.OUT_DIR / "labels.json").read_text(encoding="utf-8"))
    rows = sr.score()
    assert rows["all"]["n"] == sr.SAMPLE
    if not (sr.OUT_DIR / "adjudicated.json").exists():
        assert rows["all"]["ASSERTED"] == list(first.values()).count("ASSERTED") == 4
        assert rows["claude-sonnet-5-5"]["ASSERTED"] == 2


def _copy_set(tmp_path):
    for name in ("items.jsonl", "key.json", "labels.json"):
        shutil.copy(sr.OUT_DIR / name, tmp_path / name)
    for path in sr.OUT_DIR.glob("judge-*.json"):
        shutil.copy(path, tmp_path / path.name)


def test_the_reread_holds_every_contested_item_among_agreed_decoys(tmp_path):
    _copy_set(tmp_path)
    labels = json.loads((tmp_path / "labels.json").read_text(encoding="utf-8"))
    again, pool = sr.contested(tmp_path)
    assert {k for k, v in labels.items() if v in ("ASSERTED", "NEUTRAL")} <= set(again)
    assert all(labels[k] == "REFUTED" for k in pool) and not set(pool) & set(again)
    info = sr.reread(tmp_path)
    key = json.loads((tmp_path / "reread" / "key.json").read_text(encoding="utf-8"))
    assert info["decoys"] == sr.DECOYS_PER_CONTESTED * info["contested"]
    assert set(again) <= set(key.values()) and len(set(key.values())) == info["items"]
    blind = (tmp_path / "reread" / "items.jsonl").read_text(encoding="utf-8").splitlines()
    assert all(set(json.loads(line)) == {"item", "claim", "passage"} for line in blind)
    html = (tmp_path / "reread" / "label.html").read_text(encoding="utf-8")
    assert "ral-stance-repeats-reread-2026-11-24" in html and "4 UNRELATED" in html
    assert not any(real in html for real in key.values())


def test_the_committed_reread_rebuilds_byte_for_byte(tmp_path):
    _copy_set(tmp_path)
    sr.reread(tmp_path)
    for name in ("items.jsonl", "key.json", "label.html"):
        built = (tmp_path / "reread" / name).read_bytes()
        assert built == (sr.OUT_DIR / "reread" / name).read_bytes(), name


def test_apply_maps_the_reread_back_and_refuses_a_partial_one(tmp_path):
    _copy_set(tmp_path)
    sr.reread(tmp_path)
    key = json.loads((tmp_path / "reread" / "key.json").read_text(encoding="utf-8"))
    first = json.loads((tmp_path / "labels.json").read_text(encoding="utf-8"))
    flipped = next(j for j, r in key.items() if first[r] == "ASSERTED")
    second = {j: ("UNRELATED" if j == flipped else first[r]) for j, r in key.items()}
    (tmp_path / "reread" / "labels.json").write_text(json.dumps(second))
    out = sr.apply(tmp_path)
    assert out["changed"] == {key[flipped]: ["ASSERTED", "UNRELATED"]}
    assert sr.score(tmp_path)["all"]["ASSERTED"] == 3
    with pytest.raises(SystemExit):
        sr.reread(tmp_path)
    second.pop(flipped)
    (tmp_path / "reread" / "labels.json").write_text(json.dumps(second))
    with pytest.raises(ValueError):
        sr.apply(tmp_path)
