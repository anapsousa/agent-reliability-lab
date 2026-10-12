"""Second-annotator scaffolding: blind export and agreement maths."""

import json
import shutil

import pytest

from evals.judges import annotator2
from evals.judges.stance import CAL_DIR


def test_positives_are_the_nine_ever_asserted_items():
    pos = annotator2.positives()
    assert len(pos) == 9
    assert "S010" in pos  # moved to REFUTED on 7 Oct, kept: it is the contested one


def test_build_is_deterministic_blind_and_mixed():
    blind, key = annotator2.build()
    again, key_again = annotator2.build()
    assert blind == again and key == key_again
    assert len(blind) == 27  # 9 positives + 18 decoys
    assert set(key.values()) >= set(annotator2.positives())
    assert all(not b["item"].startswith("S") for b in blind)
    assert all(set(b) == {"item", "claim", "passage"} for b in blind)


@pytest.fixture
def workspace(tmp_path):
    cal = tmp_path / "cal"
    shutil.copytree(CAL_DIR, cal, ignore=shutil.ignore_patterns("annotator-2"))
    out = cal / "annotator-2"
    _, key = annotator2.build(cal)
    out.mkdir()
    (out / "key.json").write_text(json.dumps(key))
    return cal, out, key


def test_perfect_second_annotator_meets_the_bar(workspace):
    cal, out, key = workspace
    first = annotator2.load_labels(cal)
    (out / "labels.json").write_text(json.dumps({b: first[s] for b, s in key.items()}))
    r = annotator2.compare(out, cal)
    assert r["agreement"] == 1.0 and r["kappa"] == 1.0
    assert r["positive_binary_agreement"] == 9
    assert r["bar_met"] is True


def test_second_annotator_calling_everything_refuted_fails_the_bar(workspace):
    cal, out, key = workspace
    (out / "labels.json").write_text(json.dumps({b: "REFUTED" for b in key}))
    r = annotator2.compare(out, cal)
    assert r["positive_asserted_by_second"] == 0
    assert r["bar_met"] is False
    assert len(r["disagreements"]) == 8


def test_compare_rejects_incomplete_or_invalid_labels(workspace):
    cal, out, key = workspace
    first_id = min(key)
    (out / "labels.json").write_text(json.dumps({first_id: "MAYBE"}))
    with pytest.raises(ValueError):
        annotator2.compare(out, cal)
