from evals.gate import TOLERANCE, compare
from evals.runners.claude_code import wilson


def _report(model: str, all_layers: float, outcome: float, agent: str = "research-agent") -> dict:
    return {
        "agent": agent,
        "harness": "claude-code-cli",
        "model_alias": model,
        "summary": {"all_layers": {"rate": all_layers}, "outcome": {"rate": outcome}},
    }


BASE = {"r-sonnet-2026-09-23T08-00-00Z.json": _report("sonnet", 0.70, 0.80)}


def test_tolerance_is_not_tighter_than_what_40_tasks_can_resolve():
    # A series of 40 tasks at its widest (p = 0.5) has a Wilson half-width of about 15
    # points. A gate tighter than that flags noise; see the module docstring.
    lo, hi = wilson(20, 40)
    assert TOLERANCE >= (hi - lo) / 2 - 0.005


def test_a_drop_within_tolerance_passes():
    head = {**BASE, "r-sonnet-2026-09-24T08-00-00Z.json": _report("sonnet", 0.58, 0.80)}
    assert compare(BASE, head, agent_changed=True) == []


def test_a_drop_beyond_tolerance_fails_and_names_the_layer():
    head = {**BASE, "r-sonnet-2026-09-24T08-00-00Z.json": _report("sonnet", 0.50, 0.80)}
    (failure,) = compare(BASE, head, agent_changed=True)
    assert "all_layers" in failure and "70%" in failure and "50%" in failure


def test_outcome_is_gated_on_its_own():
    head = {**BASE, "r-sonnet-2026-09-24T08-00-00Z.json": _report("sonnet", 0.70, 0.60)}
    (failure,) = compare(BASE, head, agent_changed=True)
    assert "outcome" in failure


def test_changing_the_agent_without_a_new_report_fails():
    assert compare(BASE, dict(BASE), agent_changed=True)


def test_a_pr_that_touches_neither_agent_nor_reports_passes():
    assert compare(BASE, dict(BASE), agent_changed=False) == []


def test_series_are_compared_only_with_themselves():
    head = {**BASE, "r-haiku-2026-09-24T08-00-00Z.json": _report("haiku", 0.20, 0.30)}
    assert compare(BASE, head, agent_changed=True) == []


def test_only_the_newest_report_in_a_series_counts():
    head = {
        **BASE,
        "r-sonnet-2026-09-24T08-00-00Z.json": _report("sonnet", 0.40, 0.40),
        "r-sonnet-2026-09-25T08-00-00Z.json": _report("sonnet", 0.72, 0.82),
    }
    assert compare(BASE, head, agent_changed=True) == []
