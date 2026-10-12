"""The trace re-score prefers a kept transcript to a replay, and says which it used."""

import json

from evals.fixtures.corpus import load_corpus
from evals.tasks.research_agent import load_golden
from evals.trace_rescore import load_raw, score_report

URL = "https://evaltools.io/pricing"


def transcript(answer: str, page: str) -> str:
    events = [
        {"type": "system", "subtype": "init", "tools": [], "model": "m"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "mcp__fixture-web__web_fetch",
                        "input": {"url": URL},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": page, "is_error": False}
                ]
            },
        },
        {"type": "result", "subtype": "success", "result": answer},
    ]
    return "\n".join(json.dumps(e) for e in events)


def test_load_raw_returns_none_without_a_transcript(tmp_path):
    assert load_raw("run-1", "rsch-001", tmp_path) is None
    assert load_raw("run-1", "rsch-001", None) is None


def test_load_raw_reads_tool_output_exactly(tmp_path):
    (tmp_path / "run-1").mkdir()
    (tmp_path / "run-1" / "rsch-001.jsonl").write_text(transcript("ok", "Team EUR 249"))
    raw = load_raw("run-1", "rsch-001", tmp_path)
    assert raw.steps[0].result == "Team EUR 249"
    assert raw.steps[0].tool == "web_fetch"


def test_score_report_uses_the_transcript_and_labels_the_source(tmp_path):
    golden = {t["id"]: t for t in load_golden()}
    task_id = next(iter(golden))
    report = {
        "run_id": "run-1",
        "tasks": [
            {
                "id": task_id,
                "answer": "replay answer",
                "stop": "success",
                "steps": [],
                "scores": {"outcome": {"passed": True}},
            }
        ],
    }
    (tmp_path / "run-1").mkdir()
    (tmp_path / "run-1" / f"{task_id}.jsonl").write_text(
        transcript(f"Team costs EUR 249. {URL}", "Team EUR 249")
    )
    corpus = load_corpus()
    raw_rows = score_report(report, golden, corpus, False, tmp_path)
    replay_rows = score_report(report, golden, corpus, False, None)
    assert raw_rows[0]["source"] == "raw"
    assert replay_rows[0]["source"] == "replay"
    assert raw_rows[0]["grounding"]["detail"]["figures"] == 1  # read from the transcript answer
