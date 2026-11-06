"""pass^k over repeat runs of one series."""

import json

import pytest

from evals import passk


def task(tid, outcome=True, category="market", tool_choice=True):
    ok = {"passed": True}
    return {
        "id": tid,
        "category": category,
        "scores": {
            "outcome": {"passed": outcome},
            "trajectory": ok,
            "components": ok,
        },
        "trace_scores": {"tool_choice": {"passed": tool_choice}},
    }


def report(tasks, alias="haiku", models=("m-1",)):
    return {"model_alias": alias, "models_seen": list(models), "tasks": tasks}


def test_pass_all_pass_any_and_flips():
    runs = [
        report([task("a"), task("b", outcome=False), task("c")]),
        report([task("a"), task("b", outcome=False), task("c", outcome=False)]),
        report([task("a"), task("b"), task("c", outcome=False)]),
    ]
    out = passk.analyse(runs)["layers"]["outcome"]
    assert out["n"] == 3
    assert out["pass_all"] == 1  # a
    assert out["pass_any"] == 3
    assert out["flips"] == ["b", "c"]
    assert out["per_run"] == [pytest.approx(2 / 3), pytest.approx(1 / 3), pytest.approx(2 / 3)]
    assert out["gap"] == pytest.approx(1 / 3)


def test_all_layers_needs_every_gated_layer():
    t = task("a")
    t["scores"]["components"] = {"passed": False}
    assert passk.task_passed(t, "all_layers") is False
    assert passk.task_passed(task("a"), "all_layers") is True


def test_trace_check_that_does_not_apply_is_left_out():
    t = task("a")
    t["trace_scores"] = {"stopping": {"passed": None}}
    assert passk.task_passed(t, "stopping") is None
    runs = [report([t]), report([t])]
    assert "stopping" not in passk.analyse(runs)["layers"]


def test_flips_are_counted_by_category():
    runs = [
        report([task("a", category="lead"), task("b", category="market")]),
        report([task("a", outcome=False, category="lead"), task("b", category="market")]),
    ]
    assert passk.analyse(runs)["flips_by_category"] == {"lead": (1, 2 - 1), "market": (0, 1)}


def test_groups_refuse_to_pool_different_models_under_one_alias(tmp_path):
    for i, model in enumerate(("haiku-4-5", "haiku-5-5")):
        (tmp_path / f"research-agent-{i}.json").write_text(
            json.dumps(report([task("a")], models=(model,)))
        )
    with pytest.raises(SystemExit, match="different models"):
        passk.load_groups(tmp_path)


def test_gate_note_says_which_side_of_the_tolerance_the_gap_falls():
    runs = [
        report([task("a"), task("b")]),
        report([task("a", outcome=False), task("b", outcome=False)]),
    ]
    results = {("haiku", ("m-1",)): passk.analyse(runs)}
    assert "above the tolerance" in passk.gate_note(results)
