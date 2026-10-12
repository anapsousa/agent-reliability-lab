"""Behaviour of the trace scorer: tool choice per step, stopping, grounding."""

from evals.scorers.steps import Step
from evals.scorers.trace import (
    enough_at,
    evaluate_trace,
    figures,
    judge_steps,
    score_grounding,
    score_stopping,
)

PRICING = "https://evaltools.io/pricing"
AIQ = "https://aiqreport.com/2026/state-of-agent-evals"

SEARCH_RESULT = f"1. Pricing — EvalTools\n   URL: {PRICING}\n   Published: 2026-05-20"
PRICING_PAGE = (
    f"# Pricing\nURL: {PRICING}\n\nStarter EUR 0. Team EUR 249 per month. 20% off annual."
)


def read(name="playbook"):
    return Step(tool="read_context", arguments={"name": name}, result="context")


def search(query="evaltools pricing", result=SEARCH_RESULT):
    return Step(tool="web_search", arguments={"query": query}, result=result)


def fetch(url=PRICING, result=PRICING_PAGE, error=False):
    return Step(tool="web_fetch", arguments={"url": url}, result=result, error=error)


EXPECTED = {"must_cite": [PRICING]}
TRAJ = {"max_steps": 6, "expect_tools": ["web_search"]}
ANSWER = f"EvalTools Team costs EUR 249 per month.\n\n## Sources\n- {PRICING}"


# --- tool choice -------------------------------------------------------------


def test_clean_run_has_every_step_ok():
    verdicts = judge_steps([read(), search(), fetch()], TRAJ)
    assert [v.verdict for v in verdicts] == ["ok", "ok", "ok"]


def test_fetching_an_unsurfaced_url_is_the_wrong_tool_choice():
    verdicts = judge_steps([read(), fetch(url="https://evaltools.io/team", error=True)], TRAJ)
    assert verdicts[1].verdict == "wrong"
    assert "no earlier step surfaced" in verdicts[1].reason


def test_a_url_in_the_task_input_counts_as_surfaced():
    verdicts = judge_steps([fetch()], TRAJ, task_input=f"Check {PRICING}")
    assert verdicts[0].verdict == "ok"


def test_context_after_research_is_wrong_order():
    verdicts = judge_steps([search(), read()], TRAJ)
    assert verdicts[1].verdict == "wrong"


def test_refetching_a_page_is_redundant_not_wrong():
    verdicts = judge_steps([search(), fetch(), search(query="other"), fetch()], TRAJ)
    assert verdicts[3].verdict == "redundant"


def test_unknown_and_forbidden_tools_are_wrong():
    steps = [Step(tool="Bash", arguments={"cmd": "ls"}), search()]
    verdicts = judge_steps(steps, {"forbidden_tools": ["web_search"]})
    assert [v.verdict for v in verdicts] == ["wrong", "wrong"]


def test_tool_choice_fails_when_a_required_tool_is_never_picked():
    result = evaluate_trace([read()], ANSWER, EXPECTED, TRAJ, effort="standard")
    assert result.tool_choice.passed is False
    assert any("never picked the required tool" in f for f in result.tool_choice.failures)


def test_tool_choice_score_is_a_rate_over_steps():
    steps = [read(), search(), fetch(url="https://evaltools.io/x", error=True), fetch()]
    result = evaluate_trace(steps, ANSWER, EXPECTED, TRAJ, effort="standard")
    assert result.tool_choice.score == 0.75
    assert result.tool_choice.detail["wrong"] == 1


# --- stopping ----------------------------------------------------------------


def test_enough_needs_a_fetch_unless_the_task_is_quick():
    steps = [search(), fetch()]
    assert enough_at(steps, [PRICING], "standard") == 1
    assert enough_at(steps, [PRICING], "quick") == 0


def test_stopping_right_after_enough_passes():
    result = score_stopping([read(), search(), fetch()], ANSWER, EXPECTED, "standard")
    assert result.passed is True
    assert result.detail["calls_after_enough"] == 0
    assert result.score == 1.0


def test_overrunning_past_the_slack_fails():
    steps = [search(), fetch()] + [search(query=f"q{i}") for i in range(3)]
    result = score_stopping(steps, ANSWER, EXPECTED, "standard")
    assert result.passed is False
    assert "overran: 3 calls" in result.failures[0]


def test_answering_before_retrieving_the_source_is_an_early_stop():
    result = score_stopping([read(), search()], ANSWER, EXPECTED, "standard")
    assert result.passed is False
    assert "stopped early" in result.failures[0]


def test_turn_cap_is_never_a_clean_stop():
    result = score_stopping([search(), fetch()], ANSWER, EXPECTED, "standard", "error_max_turns")
    assert result.passed is False


def test_stopping_is_not_applicable_without_must_cite():
    result = score_stopping([search()], "Nothing found.", {"must_cite": []}, "standard")
    assert result.passed is None


# --- grounding ---------------------------------------------------------------


def test_figures_extracts_percentages_and_money():
    found = figures("62% of teams; EUR 249/month; $40M ARR; 12,000 customers; 1,250 €")
    assert "62%" in found
    assert "249 (money)" in found
    assert "40 (money)" in found
    assert "1250 (money)" in found
    assert not any(f.startswith("12000") for f in found)  # a count, not a figure


def test_answer_matching_tool_output_is_grounded():
    result = score_grounding([search(), fetch()], ANSWER)
    assert result.passed is True
    assert result.score == 1.0


def test_valid_corpus_url_never_seen_in_this_run_is_ungrounded():
    answer = ANSWER + f"\n- {AIQ}"
    result = score_grounding([search(), fetch()], answer)
    assert result.passed is False
    assert result.detail["ungrounded_urls"] == [AIQ]


def test_figure_no_tool_returned_is_ungrounded_even_if_derived():
    answer = "Annual billing is about EUR 199 per month (249 less 20%)."
    result = score_grounding([search(), fetch()], answer)
    assert result.detail["ungrounded_figures"] == ["199 (money)"]


# --- derived figures ---------------------------------------------------------


def test_marked_derivation_that_reproduces_is_accepted():
    answer = "Team is EUR 249. Annual billing saves 20%, about EUR 199 a month (my calculation)."
    result = score_grounding([search(), fetch()], answer)
    assert result.passed is True
    assert result.detail["derived_verified"] == ["199 (money) = a less b%"]
    assert result.detail["strict_passed"] is False  # the strict reading still fails it


def test_marked_derivation_that_does_not_reproduce_fails():
    answer = "Team is EUR 249. Annual billing saves 20%, about EUR 150 a month (my calculation)."
    result = score_grounding([search(), fetch()], answer)
    assert result.passed is False
    assert result.detail["derived_unverified"] == ["150 (money)"]
    assert result.detail["ungrounded_figures"] == ["150 (money)"]


def test_unmarked_derivation_stays_ungrounded_even_when_it_reproduces():
    answer = "Team is EUR 249, so annual billing is EUR 199 a month at 20% off."
    result = score_grounding([search(), fetch()], answer)
    assert result.passed is False
    assert result.detail["ungrounded_figures"] == ["199 (money)"]
    assert result.detail["derived_verified"] == []


def test_a_verified_figure_is_an_operand_for_the_next_one():
    answer = (
        "Team is EUR 249 with 20% off annually.\n"
        "That is about EUR 199 a month (my calculation).\n"
        "About EUR 2,390 a year (my calculation)."
    )
    result = score_grounding([search(), fetch()], answer)
    assert result.passed is True
    assert [d.split(" = ")[0] for d in result.detail["derived_verified"]] == [
        "199 (money)",
        "2390 (money)",
    ]


def test_cagr_needs_the_years_to_be_stated():
    steps = [search(), fetch(result="Market EUR 310 in 2025, EUR 2,400 in 2030.")]
    stated = "Market EUR 310 in 2025, EUR 2,400 in 2030: implied CAGR 50.6% (my calculation)."
    assert score_grounding(steps, stated).passed is True
    unstated = "Market EUR 310 to EUR 2,400: implied CAGR 50.6% (my calculation)."
    assert score_grounding(steps, unstated).detail["derived_unverified"] == ["50.6%"]


def test_percent_taken_off_is_not_tried_on_a_percentage_figure():
    steps = [search(), fetch(result="Rate 40%. Base 62%.")]
    answer = "Rate 40%, base 62%, so the implied figure is 25% (my calculation)."
    assert score_grounding(steps, answer).detail["derived_unverified"] == ["25%"]


# --- attribution -------------------------------------------------------------

OTHER = "https://aiqreport.com/2026/state-of-agent-evals"
OTHER_PAGE = f"# AIQ\nURL: {OTHER}\n\n62% of teams run no automated evaluation."
BOTH = [search(), fetch(), fetch(OTHER, OTHER_PAGE)]


def test_figure_beside_the_wrong_source_is_flagged_not_failed():
    answer = f"EvalTools says 62% run no evaluation ({PRICING})."
    result = score_grounding(BOTH, answer)
    assert result.detail["misattributed"] == [f"62% not in {PRICING}"]
    assert result.passed is True  # a diagnostic until it is calibrated: it never gates


def test_figure_beside_its_own_source_is_fine():
    result = score_grounding(BOTH, f"62% run no evaluation ({OTHER}).")
    assert result.detail["misattributed"] == []


def test_a_quoted_claim_is_not_attributed():
    answer = f'The page says "62% of agents fail", which {PRICING} does not back.'
    assert score_grounding(BOTH, answer).detail["misattributed"] == []


def test_a_figure_from_the_task_input_is_not_attributed():
    answer = f"The 62% claim is not on the pricing page ({PRICING})."
    result = score_grounding(BOTH, answer, task_input="Is it true that 62% fail?")
    assert result.detail["misattributed"] == []


def test_a_sentence_with_no_url_is_counted_not_checked():
    result = score_grounding(BOTH, "Sixty-two percent is 62% overall.")
    assert result.detail["misattributed"] == []
    assert result.detail["unattributed_figures"] == 1


def test_thousands_separator_matches_either_way():
    step = fetch(result="Revenue EUR 1,250 per seat.")
    assert score_grounding([step], "It costs EUR 1250.").passed is True


def test_errored_step_output_is_never_evidence():
    step = fetch(result="404 Not Found — https://evaltools.io/x", error=True)
    result = score_grounding([step], "See https://evaltools.io/x")
    assert result.passed is False


def test_no_urls_or_figures_means_grounding_does_not_apply():
    assert score_grounding([search()], "Nothing found on this topic.").passed is None


def test_as_dict_round_trips_all_checks():
    out = evaluate_trace([read(), search(), fetch()], ANSWER, EXPECTED, TRAJ, "standard").as_dict()
    assert set(out) == {"tool_choice", "stopping", "grounding", "steps"}
    assert len(out["steps"]) == 3
