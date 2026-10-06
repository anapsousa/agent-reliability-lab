"""Behaviour of the trajectory scorer.

Trajectory asks whether the path was sane, not whether the answer was right — a
run can reach the correct answer through a loop, and a run can fail the task
while moving perfectly sensibly. Keeping the two separate is the whole reason
for having more than one scorer layer.
"""

import pytest

from evals.scorers.steps import Step
from evals.scorers.trajectory import evaluate_trajectory

ANSWER = "## Sources\n- https://evaltools.io/pricing\n"


def search(query="agent evals", error=False):
    return Step(tool="web_search", arguments={"query": query}, error=error)


def fetch(url="https://evaltools.io/pricing", error=False):
    return Step(tool="web_fetch", arguments={"url": url}, error=error)


def read(name="playbook"):
    return Step(tool="read_context", arguments={"name": name})


def test_a_direct_path_passes():
    result = evaluate_trajectory([read(), search(), fetch()], ANSWER, {})
    assert result.passed is True
    assert result.failures == []


def test_fails_when_the_same_call_is_issued_twice():
    """Identical call, identical arguments — the second one cannot learn anything new."""
    result = evaluate_trajectory([search("agent evals"), search("agent evals")], ANSWER, {})
    assert result.passed is False
    assert any("repeated identical call" in f for f in result.failures)


def test_a_repeated_tool_with_different_arguments_is_not_a_loop():
    """Two different searches are research; two identical searches are a loop."""
    result = evaluate_trajectory(
        [search("evaltools pricing"), search("evaltools news")], ANSWER, {}
    )
    assert result.passed is True


def test_fails_on_a_run_of_consecutive_errors():
    """Three failures in a row is thrashing, not persistence."""
    steps = [
        fetch("https://a.example", error=True),
        fetch("https://b.example", error=True),
        fetch("https://c.example", error=True),
    ]
    result = evaluate_trajectory(steps, ANSWER, {})
    assert result.passed is False
    assert any("consecutive failed" in f for f in result.failures)


def test_two_consecutive_errors_are_tolerated():
    """Recovering from a bad URL is normal; the agent's own playbook expects fallback."""
    steps = [
        fetch("https://a.example", error=True),
        fetch("https://b.example", error=True),
        fetch(),
    ]
    result = evaluate_trajectory(steps, ANSWER, {})
    assert result.passed is True


def test_fails_when_context_is_read_only_after_researching():
    """The playbook says read context first; reading it afterwards is out of order."""
    result = evaluate_trajectory([search(), read()], ANSWER, {})
    assert result.passed is False
    assert any("read context after" in f for f in result.failures)


def test_not_reading_context_at_all_is_not_a_trajectory_failure():
    """Whether context was required is a component-layer question, not a path question."""
    result = evaluate_trajectory([search(), fetch()], ANSWER, {})
    assert result.passed is True


def test_fails_when_the_run_ends_without_an_answer():
    """A dangling tool call means the run was abandoned, however sane the path looked."""
    result = evaluate_trajectory([search(), fetch()], "", {})
    assert result.passed is False
    assert any("no answer" in f for f in result.failures)


def test_a_run_with_no_tool_calls_at_all_fails():
    """Answering a research task from parametric memory is not a sane path."""
    result = evaluate_trajectory([], ANSWER, {})
    assert result.passed is False
    assert any("no tool calls" in f for f in result.failures)


def test_reports_every_failure_not_just_the_first():
    result = evaluate_trajectory([search("q"), search("q")], "", {})
    assert result.passed is False
    assert len(result.failures) == 2


@pytest.mark.parametrize("steps", [[read(), search()], [read(), read("role"), search()]])
def test_context_reads_before_the_first_web_call_are_in_order(steps):
    assert evaluate_trajectory(steps, ANSWER, {}).passed is True
