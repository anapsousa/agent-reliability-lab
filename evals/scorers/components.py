"""Component scorer — tool-call correctness.

The diagnostic layer. Outcome tells you the run failed; this tells you whether
it failed because the agent never searched, blew the step budget, or fetched a
URL it invented. A pass rate without this layer is a number you cannot act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from evals.scorers.steps import Step

# The argument each tool cannot meaningfully be called without.
REQUIRED_ARGUMENT = {"web_search": "query", "web_fetch": "url", "read_context": "name"}


@dataclass(frozen=True)
class ComponentResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checks_run: int = 0


def evaluate_components(
    steps: list[Step],
    spec: dict,
    context_names: list[str],
    task_input: str = "",
) -> ComponentResult:
    """Score tool selection, arguments and step count for one run."""
    failures: list[str] = []
    checks = 0
    called = {step.tool for step in steps}

    for tool in spec.get("expect_tools") or []:
        checks += 1
        if tool not in called:
            failures.append(f"never called required tool: {tool}")

    for tool in spec.get("forbidden_tools") or []:
        checks += 1
        if tool in called:
            failures.append(f"called forbidden tool: {tool}")

    max_steps = spec.get("max_steps")
    if max_steps is not None:
        checks += 1
        if len(steps) > max_steps:
            failures.append(
                f"step budget exceeded: {len(steps)} calls against a budget of {max_steps}"
            )

    # A URL is legitimately known only if it was surfaced by an earlier step or
    # handed over in the task itself. Anything else the agent produced from its
    # own weights — caught here, one layer before it reaches the answer.
    known = task_input
    for step in steps:
        if step.tool == "web_fetch":
            checks += 1
            url = str(step.arguments.get("url", "")).strip()
            if url and url not in known:
                failures.append(f"unsourced URL: {url} was not surfaced by any earlier step")
        if step.tool == "read_context":
            checks += 1
            name = str(step.arguments.get("name", "")).strip()
            if name and name not in context_names:
                failures.append(f"invalid read_context argument: {name!r}")

        argument = REQUIRED_ARGUMENT.get(step.tool)
        if argument is not None:
            checks += 1
            if not str(step.arguments.get(argument, "")).strip():
                failures.append(f"empty required argument: {step.tool}.{argument}")

        known += "\n" + step.result

    return ComponentResult(passed=not failures, failures=failures, checks_run=checks)
