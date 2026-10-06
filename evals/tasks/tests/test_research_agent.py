"""End-to-end wiring for the research-agent task.

The unit tests in evals/scorers prove the checks are correct in isolation. These
prove the checks are actually reachable through Inspect — that the task metadata
arrives at the scorer, and that a good answer can score CORRECT.

Without this, a suite reporting 0.000 is indistinguishable from a suite where
nothing can ever pass, and the second is far worse than the agent being bad.
"""

from __future__ import annotations

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model
from inspect_ai.scorer import CORRECT, INCORRECT

from evals.fixtures.corpus import load_corpus
from evals.scorers.steps import steps_from_messages
from evals.tasks.research_agent import load_golden, research_agent

GOOD_RSCH_001 = """\
## Executive Summary
The claim holds. It originates in the AIQ Report's 2026 survey of 1,204 teams.

## Key Findings
- 62% of surveyed teams run no automated evaluation of their agents.

## Sources
- https://aiqreport.com/2026/state-of-agent-evals — published 12 March 2026
"""

BAD_RSCH_001 = """\
## Executive Summary
Confirmed by industry analysis.

## Sources
- https://top-ai-tools-daily.example/best-agent-eval-platforms-2026
"""


def run_one(sample_id: str, answer: str):
    """Run a single golden task against a model that always returns `answer`."""
    model = get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content(model="mockllm/model", content=answer)],
    )
    logs = inspect_eval(
        research_agent(),
        model=model,
        sample_id=sample_id,
        log_dir="/tmp/inspect-pytest-logs",
        display="none",
    )
    assert logs[0].status == "success", logs[0].error
    assert logs[0].samples, "no samples were run"
    return logs[0].samples[0].scores["outcome"]


def test_a_correct_answer_scores_correct():
    score = run_one("rsch-001", GOOD_RSCH_001)
    assert score.value == CORRECT, score.explanation


def test_an_answer_citing_a_tier_four_source_scores_incorrect():
    score = run_one("rsch-001", BAD_RSCH_001)
    assert score.value == INCORRECT
    assert "cited forbidden source" in score.explanation


def test_a_real_tool_call_is_extracted_into_steps():
    """The seam between the pure scorers and Inspect's message objects.

    Every trajectory and component check reads `steps_from_messages`. If that
    silently returns [] against real Inspect messages, both layers score every
    run on an empty list — trajectory would fail everything with "no tool
    calls" and component would pass everything vacuously. Unit tests on the
    scorers cannot catch that; only driving a genuine tool call can.
    """
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call(
                model="mockllm/model",
                tool_name="web_search",
                tool_arguments={"query": "state of agent evals"},
            ),
            ModelOutput.from_content(model="mockllm/model", content=GOOD_RSCH_001),
        ],
    )
    logs = inspect_eval(
        research_agent(),
        model=model,
        sample_id="rsch-001",
        log_dir="/tmp/inspect-pytest-logs",
        display="none",
    )
    sample = logs[0].samples[0]

    steps = steps_from_messages(sample.messages)
    assert [s.tool for s in steps] == ["web_search"]
    assert steps[0].arguments == {"query": "state of agent evals"}
    assert steps[0].error is False
    assert "aiqreport.com" in steps[0].result, "tool result was not paired back onto the step"

    assert sample.scores["trajectory"].value == CORRECT, sample.scores["trajectory"].explanation
    assert sample.scores["components"].value == CORRECT, sample.scores["components"].explanation


def test_a_failed_tool_call_is_marked_as_an_error_on_the_step():
    """The consecutive-error check is dead weight if errors never reach the step."""
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call(
                model="mockllm/model",
                tool_name="web_fetch",
                tool_arguments={"url": "https://invented.example/page"},
            ),
            ModelOutput.from_content(model="mockllm/model", content=GOOD_RSCH_001),
        ],
    )
    logs = inspect_eval(
        research_agent(),
        model=model,
        sample_id="rsch-001",
        log_dir="/tmp/inspect-pytest-logs",
        display="none",
    )
    sample = logs[0].samples[0]

    steps = steps_from_messages(sample.messages)
    assert [s.error for s in steps] == [True], "the 404 did not surface as a step error"

    # The invented URL is caught by the component layer, not by outcome.
    assert sample.scores["components"].value == INCORRECT
    assert "unsourced URL" in sample.scores["components"].explanation


def test_all_three_scorer_layers_report_independently():
    """A run that answers correctly with no research at all.

    Outcome passes — the text satisfies every declared check. Trajectory fails —
    the answer came from nowhere. That divergence is the entire argument for
    scoring the layers separately rather than collapsing them into one number.
    """
    score = run_one("rsch-001", GOOD_RSCH_001)
    assert score.value == CORRECT

    logs = inspect_eval(
        research_agent(),
        model=get_model(
            "mockllm/model",
            custom_outputs=[ModelOutput.from_content(model="mockllm/model", content=GOOD_RSCH_001)],
        ),
        sample_id="rsch-001",
        log_dir="/tmp/inspect-pytest-logs",
        display="none",
    )
    scores = logs[0].samples[0].scores
    assert scores["outcome"].value == CORRECT
    assert scores["trajectory"].value == INCORRECT
    assert "no tool calls" in scores["trajectory"].explanation


def test_the_scorer_receives_task_metadata():
    """A scorer silently reading the wrong metadata key fails open, not closed."""
    score = run_one("rsch-001", GOOD_RSCH_001)
    assert score.metadata["difficulty"] == "easy"
    assert score.metadata["category"] == "fact-check"
    assert score.metadata["checks_run"] > 0


@pytest.mark.parametrize("spec", load_golden(), ids=lambda s: s["id"])
def test_every_golden_task_declares_a_compilable_regex(spec):
    """A typo in a golden task must surface here, not as a mystery failure mid-run."""
    import re

    for key in ("must_mention", "must_not_mention"):
        for item in spec["expected"].get(key) or []:
            re.compile(item["pattern"])


@pytest.mark.parametrize("spec", load_golden(), ids=lambda s: s["id"])
def test_every_golden_task_references_urls_that_exist_in_the_corpus(spec):
    """must_cite pointing at a URL the corpus does not serve is an unpassable task."""
    valid = set(load_corpus().ground_truth["valid_urls"])
    for key in ("must_cite", "must_not_cite"):
        for url in spec["expected"].get(key) or []:
            assert url in valid, f"{spec['id']} references {url}, which is not in the corpus"


@pytest.mark.parametrize("spec", load_golden(), ids=lambda s: s["id"])
def test_no_golden_task_is_unpassable_by_its_own_always_on_checks(spec):
    """A task requiring a figure that the always-on check forbids can never pass.

    rsch-002 is the live example: it asks the agent to fact-check the 91% claim,
    so it must be allowed to name it. Catching this class of contradiction here
    is the difference between a hard task and a broken one.
    """
    import re

    ground_truth = load_corpus().ground_truth
    allowed = set(spec["expected"].get("allow_unsupported_mention") or [])
    required = [item["pattern"] for item in spec["expected"].get("must_mention") or []]

    for claim in ground_truth["unsupported_claims"]:
        if claim["claim"] in allowed:
            continue
        for pattern in required:
            assert not re.fullmatch(claim["pattern"], pattern), (
                f"{spec['id']} requires {pattern!r} but the always-on check forbids "
                f"{claim['claim']!r} — the task cannot pass"
            )
