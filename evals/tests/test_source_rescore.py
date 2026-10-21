"""The forbidden-source re-score: reproduces the stored verdicts, only lifts, meets its bar."""

import json
from collections import Counter

import pytest

from evals.scorers.outcome import forbidden_source_mentions
from evals.source_rescore import (
    BASELINE_GLOB,
    READER,
    REPEATS,
    REPORTS,
    load_reader,
    mention_key,
    rescore_all,
)

FORBIDDEN = "https://top-ai-tools-daily.example/best-agent-eval-platforms-2026"


@pytest.fixture(scope="module")
def results():
    return rescore_all()


def _stored_mentions():
    paths = sorted(REPORTS.glob(BASELINE_GLOB)) + sorted(REPEATS.glob("*.json"))
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        for task in report["tasks"]:
            for m in forbidden_source_mentions(task["answer"], FORBIDDEN):
                yield mention_key(path.name, task["id"], m.line_no), m


def test_the_bar_no_mention_read_as_anything_but_a_rejection_is_passed():
    # Bar (outcome.py, written 2026-10-20): the heuristic may pass no mention a reader marks
    # as support, a bare listing, or a description with no verdict. Critique without a "not
    # used" is also kept as cited, so the heuristic must not pass it either.
    reader = load_reader()
    mentions = dict(_stored_mentions())
    assert set(mentions) == set(reader), "every stored mention is read exactly once"
    passed_wrongly = [
        k for k, m in mentions.items() if m.stance == "REFUTED" and reader[k] != "rejection"
    ]
    assert passed_wrongly == []


SECOND_READER = READER.with_name("second-reader.json")


def test_the_bar_holds_under_the_second_reading_too():
    # The second reading (2026-10-21) was blind to the heuristic's verdicts. It reads more
    # context, so it may pass more than the heuristic does; the heuristic must never pass a
    # mention it did not read as a rejection.
    second = json.loads(SECOND_READER.read_text(encoding="utf-8"))["labels"]
    mentions = dict(_stored_mentions())
    assert set(mentions) == set(second), "every stored mention is read exactly once"
    assert Counter(second.values()) == {"REJECT": 185, "UNMARKED": 14, "SUPPORT": 2, "OTHER": 2}
    passed_wrongly = [
        k for k, m in mentions.items() if m.stance == "REFUTED" and second[k] != "REJECT"
    ]
    assert passed_wrongly == []


def test_reader_counts_are_the_committed_ones():
    assert Counter(load_reader().values()) == {
        "rejection": 167,
        "critique": 19,
        "described": 10,
        "bare": 5,
        "support": 2,
    }
    assert READER.exists()


def test_the_lexical_baseline_is_reproduced(results):
    before = {m: r["alone"]["outcome_before"]["passed"] for m, r in results["baseline"].items()}
    assert before == {"haiku": 21, "sonnet": 16, "opus": 5}
    cited = {m: r["alone"]["cited_runs_before"] for m, r in results["baseline"].items()}
    assert cited == {"haiku": 4, "sonnet": 18, "opus": 18}


def test_the_stance_rescore_is_reproduced_before_this_fix(results):
    strict = {
        m: r["stance_strict"]["outcome_before"]["passed"] for m, r in results["baseline"].items()
    }
    assert strict == {"haiku": 22, "sonnet": 17, "opus": 10}


def test_the_fix_only_ever_lifts_and_the_bounds_are_ordered(results):
    cells = [
        r[k]
        for r in results["baseline"].values()
        for k in ("alone", "stance_strict", "stance_lenient")
    ]
    cells += [r for runs in results["repeats"].values() for r in runs]
    for c in cells:
        for layer in ("outcome", "all"):
            b, a, u = (c[f"{layer}_{w}"]["passed"] for w in ("before", "after", "upper"))
            assert b <= a <= u
        assert c["cited_runs_after"] <= c["cited_runs_before"]


def test_repeats_cover_both_series_three_runs_each(results):
    assert {s: len(r) for s, r in results["repeats"].items()} == {
        "haiku (claude-haiku-5-5)": 3,
        "sonnet (claude-sonnet-5-5)": 3,
    }
