from collections import Counter

import pytest

from evals.judges.stance import load_labels
from evals.rescore import label_stance, labels_by_passage, rescore_all


def test_committed_labels_after_adjudication():
    # Round 1 was 71 REFUTED / 19 ASSERTED / 4 NEUTRAL. The adjudication moved 11 slips
    # and 4 NEUTRALs to REFUTED and one REFUTED to ASSERTED.
    assert Counter(load_labels().values()) == {"REFUTED": 85, "ASSERTED": 9}


def test_every_labelled_passage_has_one_stance():
    by_passage = labels_by_passage()
    assert by_passage and set(by_passage.values()) <= {"ASSERTED", "REFUTED"}


@pytest.mark.parametrize(("policy", "verdict"), [("fail", "ASSERTED"), ("pass", "REFUTED")])
def test_a_hit_no_human_saw_follows_the_policy(policy, verdict):
    stance = label_stance({"seen": "REFUTED"}, policy)
    assert stance("claim", "seen") == "REFUTED"
    assert stance("claim", "never labelled") == verdict


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        label_stance({}, "maybe")


def test_rescoring_only_ever_lifts_pass_rates_and_brackets_the_unlabelled_hits():
    results = rescore_all()
    for model in ("haiku", "sonnet", "opus"):
        strict, lenient = results["strict"][model], results["lenient"][model]
        assert strict["outcome_before"] == lenient["outcome_before"]
        assert strict["outcome_before"]["passed"] <= strict["outcome_after"]["passed"]
        assert strict["outcome_after"]["passed"] <= lenient["outcome_after"]["passed"]
        assert strict["all_after"]["passed"] <= lenient["all_after"]["passed"]


def test_the_baseline_is_reproduced_before_the_labels_are_applied():
    before = {m: r["outcome_before"]["passed"] for m, r in rescore_all()["strict"].items()}
    assert before == {"haiku": 21, "sonnet": 16, "opus": 5}
