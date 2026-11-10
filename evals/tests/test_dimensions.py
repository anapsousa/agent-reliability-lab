"""Five-dimension view over repeat runs."""

import pytest

from evals import dimensions


def task(tid, ok=True, wall=10.0, cost=0.1):
    s = {"passed": True}
    return {
        "id": tid,
        "category": "market",
        "wall_s": wall,
        "cost_usd": cost,
        "scores": {"outcome": {"passed": ok}, "trajectory": s, "components": s},
    }


def report(tasks, models=("m-1",)):
    return {"model_alias": "m", "models_seen": list(models), "tasks": tasks}


def test_latency_cost_and_reliability_from_pooled_runs():
    runs = [
        report([task("a", wall=10, cost=0.1), task("b", ok=False, wall=30, cost=0.3)]),
        report([task("a", wall=20, cost=0.2), task("b", ok=True, wall=40, cost=0.4)]),
    ]
    d = dimensions.dimensions(runs)
    assert d["latency_s"]["p50"] == 20  # nearest rank of [10, 20, 30, 40]
    assert d["latency_s"]["max"] == 40
    assert d["cost_usd"]["per_run"] == [pytest.approx(0.4), pytest.approx(0.6)]
    assert d["cost_usd"]["total"] == pytest.approx(1.0)
    assert d["cost_usd"]["per_task"] == pytest.approx(0.25)
    assert d["reliability"]["all_layers"] == (1, 2, 2)  # a always; b flips
    assert d["cost_usd"]["all_layers_passes"] == 3
    assert d["cost_usd"]["per_all_layers_pass"] == pytest.approx(1.0 / 3)


def test_no_passes_gives_no_cost_per_pass():
    runs = [report([task("a", ok=False)]), report([task("a", ok=False)])]
    assert dimensions.dimensions(runs)["cost_usd"]["per_all_layers_pass"] is None


def test_safety_is_declared_unmeasured():
    d = dimensions.dimensions([report([task("a")]), report([task("a")])])
    assert "not measured" in d["safety"]


def test_render_has_a_row_per_series_and_says_safety_not_measured():
    runs = [report([task("a")]), report([task("a")])]
    text = dimensions.render({("m", ("m-1",)): dimensions.dimensions(runs)})
    assert "m-1 (k = 2)" in text
    assert text.count("not measured") == 1
    assert "$0.10 ($0.10-$0.10)" in text  # each run is one $0.10 task
