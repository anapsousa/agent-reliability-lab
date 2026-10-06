"""Behaviour of the component scorer.

The diagnostic layer: right tool, right arguments, step count within budget.
When outcome fails and this layer says why, you have a bug report. When outcome
fails and every component check passes, the problem is reasoning, not plumbing.
"""

from evals.scorers.components import evaluate_components
from evals.scorers.steps import Step

CONTEXT_NAMES = ["role", "research-memory", "playbook", "company-context"]

SEARCH_RESULT = (
    "1. Pricing — EvalTools\n   URL: https://evaltools.io/pricing\n   Published: 2026-05-20"
)


def search(query="evaltools pricing", result=SEARCH_RESULT):
    return Step(tool="web_search", arguments={"query": query}, result=result)


def fetch(url="https://evaltools.io/pricing"):
    return Step(tool="web_fetch", arguments={"url": url})


def read(name="playbook"):
    return Step(tool="read_context", arguments={"name": name})


def spec(**overrides):
    base = {"max_steps": 6, "expect_tools": [], "forbidden_tools": []}
    base.update(overrides)
    return base


def test_a_well_formed_run_passes():
    result = evaluate_components([read(), search(), fetch()], spec(), CONTEXT_NAMES)
    assert result.passed is True
    assert result.failures == []


def test_fails_when_a_required_tool_was_never_called():
    result = evaluate_components([read()], spec(expect_tools=["web_search"]), CONTEXT_NAMES)
    assert result.passed is False
    assert any("never called required tool: web_search" in f for f in result.failures)


def test_fails_when_a_forbidden_tool_was_called():
    result = evaluate_components([search()], spec(forbidden_tools=["web_search"]), CONTEXT_NAMES)
    assert result.passed is False
    assert any("called forbidden tool: web_search" in f for f in result.failures)


def test_fails_when_the_step_budget_is_exceeded():
    steps = [search(f"query {i}") for i in range(7)]
    result = evaluate_components(steps, spec(max_steps=6), CONTEXT_NAMES)
    assert result.passed is False
    assert any("step budget" in f for f in result.failures)


def test_exactly_the_step_budget_is_within_budget():
    """Off-by-one here silently fails every task that used its whole budget."""
    steps = [search(f"query {i}") for i in range(6)]
    result = evaluate_components(steps, spec(max_steps=6), CONTEXT_NAMES)
    assert result.passed is True


def test_fetching_a_url_that_a_prior_search_returned_is_sourced():
    result = evaluate_components([search(), fetch()], spec(), CONTEXT_NAMES)
    assert result.passed is True


def test_fails_when_fetching_a_url_no_prior_step_surfaced():
    """An invented URL is caught here one layer before it reaches the answer."""
    result = evaluate_components(
        [search(), fetch("https://braintrust.dev/pricing")], spec(), CONTEXT_NAMES
    )
    assert result.passed is False
    assert any("unsourced URL" in f for f in result.failures)


def test_a_url_given_in_the_task_input_is_sourced():
    """'Summarise https://evaltools.io/about' must not count as invention."""
    result = evaluate_components(
        [fetch("https://evaltools.io/about")],
        spec(),
        CONTEXT_NAMES,
        task_input="Summarise https://evaltools.io/about for me.",
    )
    assert result.passed is True


def test_fails_when_read_context_is_given_an_unknown_name():
    result = evaluate_components([read("memory")], spec(), CONTEXT_NAMES)
    assert result.passed is False
    assert any("invalid read_context argument" in f for f in result.failures)


def test_fails_when_a_required_argument_is_empty():
    result = evaluate_components(
        [Step(tool="web_search", arguments={"query": "   "})], spec(), CONTEXT_NAMES
    )
    assert result.passed is False
    assert any("empty required argument" in f for f in result.failures)


def test_fails_when_a_required_argument_is_missing_entirely():
    result = evaluate_components([Step(tool="web_fetch", arguments={})], spec(), CONTEXT_NAMES)
    assert result.passed is False
    assert any("empty required argument" in f for f in result.failures)


def test_reports_every_failure_not_just_the_first():
    result = evaluate_components(
        [read("nope"), fetch("https://invented.example")],
        spec(expect_tools=["web_search"]),
        CONTEXT_NAMES,
    )
    assert result.passed is False
    assert len(result.failures) == 3


def test_an_empty_run_fails_a_required_tool_check_rather_than_passing_vacuously():
    result = evaluate_components([], spec(expect_tools=["web_search"]), CONTEXT_NAMES)
    assert result.passed is False
