"""Behaviour of the outcome scorer.

The outcome layer answers one question — did the agent produce the right
answer — and answers it deterministically. Anything needing judgement about
whether a claim was asserted or merely quoted belongs to the judge layer.
"""

import pytest

from evals.scorers.outcome import evaluate_outcome

GROUND_TRUTH = {
    "valid_urls": [
        "https://evaltools.io/pricing",
        "https://aiqreport.com/2026/state-of-agent-evals",
        "https://top-ai-tools-daily.example/best-agent-eval-platforms-2026",
    ],
    "uncitable_urls": [
        "https://top-ai-tools-daily.example/best-agent-eval-platforms-2026",
    ],
    "unsupported_claims": [
        {"claim": "EvalTools has $40M ARR", "pattern": r"\$?\s*40\s*m\b"},
    ],
}


def expected(**overrides):
    """A task expectation with nothing asserted, so each test declares only its subject."""
    base = {
        "must_cite": [],
        "must_not_cite": [],
        "must_mention": [],
        "must_not_mention": [],
        "format_sections": [],
        "allow_unsupported_mention": [],
    }
    base.update(overrides)
    return base


def test_passes_when_every_declared_check_is_satisfied():
    answer = (
        "## Executive Summary\nTeam tier is 249 EUR/month.\n\n"
        "## Sources\n- https://evaltools.io/pricing\n"
    )
    result = evaluate_outcome(
        answer,
        expected(
            must_cite=["https://evaltools.io/pricing"],
            must_mention=[{"pattern": "249", "why": "team tier price"}],
            format_sections=["Executive Summary", "Sources"],
        ),
        GROUND_TRUTH,
    )
    assert result.passed is True
    assert result.failures == []


def test_fails_when_a_required_citation_is_missing():
    answer = "## Sources\n- Pricing was checked on the vendor site.\n"
    result = evaluate_outcome(
        answer, expected(must_cite=["https://evaltools.io/pricing"]), GROUND_TRUTH
    )
    assert result.passed is False
    assert any("missing required citation" in f for f in result.failures)


def test_fails_when_a_tier_four_source_is_cited():
    answer = "## Sources\n- https://top-ai-tools-daily.example/best-agent-eval-platforms-2026\n"
    result = evaluate_outcome(
        answer,
        expected(
            must_not_cite=["https://top-ai-tools-daily.example/best-agent-eval-platforms-2026"]
        ),
        GROUND_TRUTH,
    )
    assert result.passed is False
    assert any("cited forbidden source" in f for f in result.failures)


def test_fails_when_a_required_pattern_is_absent():
    answer = "## Sources\nThe Team tier is competitively priced.\n"
    result = evaluate_outcome(
        answer,
        expected(must_mention=[{"pattern": r"249", "why": "team tier price"}]),
        GROUND_TRUTH,
    )
    assert result.passed is False
    assert any("did not mention" in f for f in result.failures)


def test_fails_when_a_forbidden_pattern_is_present():
    answer = "Pricing starts at $199/month.\n"
    result = evaluate_outcome(
        answer,
        expected(must_not_mention=[{"pattern": r"\$?\s*199", "why": "wrong price"}]),
        GROUND_TRUTH,
    )
    assert result.passed is False
    assert any("mentioned forbidden" in f for f in result.failures)


def test_fails_when_a_required_section_heading_is_absent():
    answer = "Some findings, no structure.\n"
    result = evaluate_outcome(answer, expected(format_sections=["Sources"]), GROUND_TRUTH)
    assert result.passed is False
    assert any("missing section" in f for f in result.failures)


def test_section_heading_matches_regardless_of_heading_level():
    answer = "### Sources\n- https://evaltools.io/pricing\n"
    result = evaluate_outcome(answer, expected(format_sections=["Sources"]), GROUND_TRUTH)
    assert result.passed is True


def test_fails_when_a_url_outside_the_corpus_is_cited():
    """The fixture corpus is the whole world; a URL from outside it was invented."""
    answer = "## Sources\n- https://braintrust.dev/pricing\n"
    result = evaluate_outcome(answer, expected(), GROUND_TRUTH)
    assert result.passed is False
    assert any("fabricated URL" in f for f in result.failures)


def test_fails_when_an_unsupported_claim_appears_without_the_task_declaring_it():
    """Always-on: a tier-4 figure leaking into a task that never thought to forbid it."""
    answer = "EvalTools reports around $40M in ARR.\n"
    result = evaluate_outcome(answer, expected(), GROUND_TRUTH)
    assert result.passed is False
    assert any("unsupported claim" in f for f in result.failures)


def test_task_may_opt_out_of_an_unsupported_claim_check_to_allow_debunking():
    """A fact-check task has to be able to name the figure it is refuting."""
    answer = "The $40M ARR figure is unverified and comes from AI-generated content.\n"
    result = evaluate_outcome(
        answer,
        expected(allow_unsupported_mention=["EvalTools has $40M ARR"]),
        GROUND_TRUTH,
    )
    assert result.passed is True


def test_pattern_matching_ignores_case():
    answer = "## sources\nBased in BERLIN.\n"
    result = evaluate_outcome(
        answer,
        expected(
            must_mention=[{"pattern": "berlin", "why": "hq"}],
            format_sections=["Sources"],
        ),
        GROUND_TRUTH,
    )
    assert result.passed is True


def test_reports_every_failure_not_just_the_first():
    """A run that fails four checks should say so — one fix at a time is slow."""
    answer = "Nothing useful here.\n"
    result = evaluate_outcome(
        answer,
        expected(
            must_cite=["https://evaltools.io/pricing"],
            must_mention=[{"pattern": "249", "why": "price"}],
            format_sections=["Sources"],
        ),
        GROUND_TRUTH,
    )
    assert result.passed is False
    assert len(result.failures) == 3


def test_an_empty_answer_fails_rather_than_vacuously_passing():
    result = evaluate_outcome(
        "", expected(must_cite=["https://evaltools.io/pricing"]), GROUND_TRUTH
    )
    assert result.passed is False


def test_a_task_asserting_nothing_passes_a_clean_answer():
    """No declared checks plus no always-on violations is a pass, not an error."""
    result = evaluate_outcome("A clean answer.", expected(), GROUND_TRUTH)
    assert result.passed is True


def test_invalid_regex_in_a_task_raises_rather_than_silently_passing():
    """A typo in a golden task must not quietly become a green run."""
    with pytest.raises(ValueError, match="invalid regex"):
        evaluate_outcome(
            "anything",
            expected(must_mention=[{"pattern": "[unclosed", "why": "typo"}]),
            GROUND_TRUTH,
        )


# --- The stance cascade (opt-in) ---------------------------------------------------

DEBUNK = "Intro.\n\nOne listicle claims $40M ARR but cites nothing, so I left it out.\n\nEnd."


def test_without_a_stance_judge_any_mention_still_fails():
    result = evaluate_outcome(DEBUNK, expected(), GROUND_TRUTH)
    assert result.failures == ["unsupported claim asserted: EvalTools has $40M ARR"]


def test_a_refuted_mention_passes_and_the_judge_sees_only_its_paragraph():
    seen = []

    def stance(claim, passage):
        seen.append((claim, passage))
        return "REFUTED"

    assert evaluate_outcome(DEBUNK, expected(), GROUND_TRUTH, stance=stance).passed
    assert seen == [
        (
            "EvalTools has $40M ARR",
            "One listicle claims $40M ARR but cites nothing, so I left it out.",
        )
    ]


@pytest.mark.parametrize("verdict", ["ASSERTED", "NEUTRAL"])
def test_asserted_and_neutral_mentions_both_fail(verdict):
    result = evaluate_outcome(DEBUNK, expected(), GROUND_TRUTH, stance=lambda c, p: verdict)
    assert result.failures == [f"unsupported claim {verdict.lower()}: EvalTools has $40M ARR"]


def test_the_judge_is_never_called_when_the_regex_finds_nothing():
    def stance(claim, passage):
        raise AssertionError("judge called with no regex hit")

    assert evaluate_outcome("Nothing to see.", expected(), GROUND_TRUTH, stance=stance).passed


def test_a_regex_hit_that_is_not_the_claim_passes():
    assert evaluate_outcome(
        DEBUNK, expected(), GROUND_TRUTH, stance=lambda c, p: "UNRELATED"
    ).passed
