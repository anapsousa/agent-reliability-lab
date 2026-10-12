"""The trace labelling set: stratified sample, vocabulary mapping, agreement."""

import pytest

from evals.judges import trace_labels as tl


def row(tool=True, stop=True, ground=True, stop_failures=()):
    return {
        "tool_choice": {"passed": tool},
        "stopping": {"passed": stop, "failures": list(stop_failures)},
        "grounding": {"passed": ground},
    }


def run(model, task, **kw):
    return (model, {"id": task}, row(**kw))


def test_scorer_labels_use_the_human_vocabulary():
    assert tl.scorer_labels(row()) == {"tool": "ok", "stop": "right", "ground": "grounded"}
    got = tl.scorer_labels(
        row(tool=False, stop=False, ground=False, stop_failures=["overran: 9 calls after"])
    )
    assert got == {"tool": "bad", "stop": "overran", "ground": "ungrounded"}


def test_early_and_abandoned_are_early_a_turn_cap_is_an_overrun():
    early = tl.scorer_labels(row(stop=False, stop_failures=["stopped early: answered without"]))
    cap = tl.scorer_labels(
        row(stop=False, stop_failures=["never stopped: run ended on the turn cap"])
    )
    assert early["stop"] == "early" and cap["stop"] == "overran"


def test_a_check_that_does_not_apply_is_none():
    got = tl.scorer_labels(row(stop=None, ground=None))
    assert got["stop"] is None and got["ground"] is None


def test_sample_is_stratified_per_model_and_deterministic():
    runs = []
    for model in tl.MODELS:
        runs += [run(model, f"{model}-f{i}", tool=False) for i in range(20)]
        runs += [run(model, f"{model}-c{i}") for i in range(20)]
    a, b = tl.sample(runs), tl.sample(runs)
    assert a == b
    assert [e["item"] for e in a] == [f"T-{i:02d}" for i in range(1, 31)]
    for model in tl.MODELS:
        mine = [e for e in a if e["model"] == model]
        assert len(mine) == 10
        assert sum("-f" in e["task"] for e in mine) == 5


def test_sample_tops_up_when_one_stratum_is_short():
    runs = [run("haiku", f"h-f{i}", tool=False) for i in range(2)]
    runs += [run("haiku", f"h-c{i}") for i in range(20)]
    picked = [e for e in tl.sample(runs) if e["model"] == "haiku"]
    assert len(picked) == 10 and sum("-f" in e["task"] for e in picked) == 2


def test_compare_counts_agreement_failures_caught_and_false_alarms():
    key = [{"item": f"T-0{i}", "model": "haiku", "task": f"t{i}"} for i in range(1, 5)]
    runs = [
        run("haiku", "t1"),  # scorer: all good
        run("haiku", "t2", tool=False),  # scorer: tool bad
        run("haiku", "t3", tool=False),  # scorer: tool bad
        run("haiku", "t4"),  # scorer: all good
    ]
    full = {"stop": "right", "ground": "grounded"}
    human = {
        "T-01": {"tool": "ok", **full},
        "T-02": {"tool": "bad", **full},  # caught
        "T-03": {"tool": "ok", **full},  # false alarm
        "T-04": {"tool": "bad", **full},  # missed
    }
    got = tl.compare(human, runs, key)["checks"]["tool"]
    assert (got["n"], got["agree"], got["human_failures"], got["caught"], got["false_alarms"]) == (
        4,
        2,
        2,
        1,
        1,
    )
    assert got["meets_bar"] is False


def test_incomplete_items_are_left_out():
    key = [{"item": "T-01", "model": "haiku", "task": "t1"}]
    got = tl.compare({"T-01": {"tool": "ok"}}, [run("haiku", "t1")], key)
    assert got["n_items"] == 0


def test_export_refuses_a_path_inside_the_repo(tmp_path):
    with pytest.raises(SystemExit):
        tl.export(tl.CAL_DIR / "page.html", runs=[])


def test_bars_are_fixed_numbers():
    assert (tl.BAR_AGREEMENT, tl.BAR_FAIL_RECALL) == (0.8, 0.8)
