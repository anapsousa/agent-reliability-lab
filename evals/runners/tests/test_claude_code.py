import json

import pytest

from evals.runners.claude_code import (
    TOOL_PREFIX,
    agent_argv,
    is_full_model_id,
    main,
    parse_stream,
    percentile,
    pin_status,
    redact,
    wilson,
)


def _stream(*events):
    return [json.dumps(e) for e in events]


def _init(tools):
    return {"type": "system", "subtype": "init", "tools": tools, "model": "claude-sonnet-5"}


def test_pairs_calls_with_results_and_strips_the_mcp_prefix():
    lines = _stream(
        _init([TOOL_PREFIX + "web_search"]),
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "searching"},
                    {
                        "type": "tool_use",
                        "id": "a",
                        "name": TOOL_PREFIX + "web_search",
                        "input": {"query": "eval pricing"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "a",
                        "content": [{"type": "text", "text": "1. Pricing"}],
                    },
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "b",
                        "name": TOOL_PREFIX + "web_fetch",
                        "input": {"url": "https://invented.example"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "b",
                        "is_error": True,
                        "content": "404 Not Found",
                    },
                ]
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "result": "Answer.",
            "total_cost_usd": 0.12,
            "duration_ms": 4000,
            "num_turns": 3,
        },
    )
    trace = parse_stream(lines)
    assert [s.tool for s in trace.steps] == ["web_search", "web_fetch"]
    assert trace.steps[0].arguments == {"query": "eval pricing"}
    assert trace.steps[0].result == "1. Pricing" and not trace.steps[0].error
    assert trace.steps[1].error and trace.steps[1].result == "404 Not Found"
    assert (trace.answer, trace.cost_usd, trace.num_turns, trace.stop) == (
        "Answer.",
        0.12,
        3,
        "success",
    )


def test_a_call_cut_off_by_the_turn_cap_is_still_a_step():
    lines = _stream(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "x",
                        "name": TOOL_PREFIX + "web_search",
                        "input": {},
                    },
                ]
            },
        },
        {"type": "result", "subtype": "error_max_turns", "result": ""},
    )
    trace = parse_stream(lines)
    assert len(trace.steps) == 1 and trace.steps[0].result == ""
    assert trace.stop == "error_max_turns"


def test_a_non_fixture_tool_keeps_its_full_name_so_the_scorers_can_flag_it():
    lines = _stream(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "y", "name": "WebFetch", "input": {"url": "u"}}
                ]
            },
        }
    )
    assert parse_stream(lines).steps[0].tool == "WebFetch"


def test_argv_locks_the_agent_to_the_fixture_web():
    argv = agent_argv("PROMPT", "/tmp/mcp.json", "sonnet")
    joined = " ".join(argv)
    assert "--strict-mcp-config" in argv
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--system-prompt") + 1] == "PROMPT"
    for builtin in ("Bash", "Read", "WebFetch", "WebSearch", "Write"):
        assert builtin in argv[argv.index("--disallowedTools") + 1]
    assert argv[argv.index("--allowedTools") + 1].split(",") == [
        TOOL_PREFIX + t for t in ("read_context", "web_search", "web_fetch")
    ]
    assert "--dangerously-skip-permissions" not in joined


def test_redact_removes_the_injected_account_email():
    assert redact("contact someone+1@example.pt now") == "contact [email] now"


def test_wilson_is_wide_on_forty_tasks():
    lo, hi = wilson(30, 40)
    assert 0.59 < lo < 0.61 and 0.85 < hi < 0.87
    assert wilson(0, 0) == (0.0, 0.0)


def test_percentile_is_nearest_rank():
    values = list(range(1, 41))
    assert percentile(values, 95) == 38
    assert percentile(values, 50) == 20
    assert percentile([], 95) is None


@pytest.mark.parametrize(
    "model",
    ["claude-haiku-5-5", "claude-sonnet-5", "claude-opus-5-5", "claude-haiku-4-5-20251001"],
)
def test_full_ids_are_recognised(model):
    assert is_full_model_id(model)


@pytest.mark.parametrize("model", ["haiku", "sonnet", "opus", "sonnet[1m]", "", "claude-sonnet"])
def test_aliases_and_fragments_are_not_full_ids(model):
    assert not is_full_model_id(model)


def test_pin_status_accepts_the_requested_model_and_its_dated_snapshot():
    assert pin_status("claude-haiku-5-5", ["claude-haiku-5-5"]) == "pinned"
    assert pin_status("claude-haiku-4-5", ["claude-haiku-4-5-20251001"]) == "pinned"


def test_pin_status_does_not_confuse_a_shorter_id_with_a_longer_version():
    # claude-sonnet-5 is a prefix of claude-sonnet-5-5 and is a different model.
    assert pin_status("claude-sonnet-5", ["claude-sonnet-5-5"]) == "mismatch"


def test_pin_status_flags_a_run_that_saw_two_models_or_a_different_one():
    assert pin_status("claude-haiku-5-5", ["claude-haiku-4-5", "claude-haiku-5-5"]) == "mismatch"
    assert pin_status("claude-haiku-5-5", ["claude-sonnet-5-5"]) == "mismatch"


def test_pin_status_for_an_alias_and_for_a_run_that_reported_no_model():
    assert pin_status("haiku", ["claude-haiku-5-5"]) == "alias"
    assert pin_status("claude-haiku-5-5", []) == "unknown"


def test_the_runner_refuses_an_alias_before_it_loads_anything(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--model", "sonnet"])
    assert exit_info.value.code == 2
    assert "alias" in capsys.readouterr().err
