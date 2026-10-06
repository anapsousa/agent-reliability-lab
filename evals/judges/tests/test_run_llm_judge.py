"""Pins the tool lock-down on the judge's `claude -p` call.

The judge grades text it did not write. If a future edit drops a flag, or the CLI grows
a tool this list does not name, the judge regains the ability to act on that text.
"""

from __future__ import annotations

from evals.judges.run_llm_judge import JUDGE_DISALLOWED_TOOLS, judge_argv


def test_every_builtin_tool_is_disallowed_by_name() -> None:
    # Keep in sync with `claude --help`. Same list as a Discord bot in another project.
    assert JUDGE_DISALLOWED_TOOLS == (
        "Agent",
        "Bash",
        "Edit",
        "Glob",
        "Grep",
        "NotebookEdit",
        "PowerShell",
        "Read",
        "Skill",
        "Task",
        "TodoWrite",
        "WebFetch",
        "WebSearch",
        "Write",
    )


def test_argv_carries_all_three_layers() -> None:
    argv = judge_argv()
    assert argv[:2] == ["claude", "-p"]
    # Layer 1: an empty --tools list.
    assert argv[argv.index("--tools") + 1] == ""
    # Layer 2 (load-bearing): every tool disallowed by name.
    assert argv[argv.index("--disallowedTools") + 1] == ",".join(JUDGE_DISALLOWED_TOOLS)
    # Layer 3: no MCP server from Ana's user or project config.
    assert "--strict-mcp-config" in argv
    # And nothing that would widen permissions back out.
    assert "--dangerously-skip-permissions" not in argv
    assert "--allowedTools" not in argv


def test_prompt_is_never_an_argument() -> None:
    # The prompt goes on stdin; a prompt in argv would show in `ps` and hit ARG_MAX.
    argv = judge_argv(model="sonnet", effort="low")
    assert "--model" in argv and argv[argv.index("--model") + 1] == "sonnet"
    assert all(not a.startswith("You are grading") for a in argv)
