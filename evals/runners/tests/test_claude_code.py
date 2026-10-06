import json

from evals.runners.claude_code import (
    TOOL_PREFIX,
    agent_argv,
    parse_stream,
    percentile,
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
