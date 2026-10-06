"""Trajectory scorer — was the path sane.

Deliberately says nothing about whether the answer was right. A run can reach a
correct answer through a loop, and a run can fail the task while moving
perfectly sensibly; collapsing those two into one number is what makes a single
pass rate impossible to debug.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from evals.scorers.steps import Step

WEB_TOOLS = frozenset({"web_search", "web_fetch"})
CONTEXT_TOOLS = frozenset({"read_context"})

# Two failures in a row is the fallback the agent's own error-handling table
# prescribes. Three is thrashing.
MAX_CONSECUTIVE_ERRORS = 2


@dataclass(frozen=True)
class TrajectoryResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    checks_run: int = 0


def evaluate_trajectory(steps: list[Step], answer: str, spec: dict) -> TrajectoryResult:
    """Score the shape of one run. `spec` is the task's `trajectory` block."""
    failures: list[str] = []
    checks = 0

    checks += 1
    if not steps:
        failures.append("no tool calls — the answer came from parametric memory, not research")

    checks += 1
    seen: set = set()
    for step in steps:
        signature = step.signature()
        if signature in seen:
            failures.append(f"repeated identical call: {step.tool}({step.arguments})")
            break
        seen.add(signature)

    checks += 1
    run = 0
    for step in steps:
        run = run + 1 if step.error else 0
        if run > MAX_CONSECUTIVE_ERRORS:
            failures.append(f"{run} consecutive failed tool calls — thrashing, not recovering")
            break

    # Only meaningful when the agent read context at all. Whether it *should*
    # have is a component-layer question about required tools, not a question
    # about the shape of the path.
    checks += 1
    first_web = next((i for i, s in enumerate(steps) if s.tool in WEB_TOOLS), None)
    late_context = next(
        (
            i
            for i, s in enumerate(steps)
            if s.tool in CONTEXT_TOOLS and first_web is not None and i > first_web
        ),
        None,
    )
    if late_context is not None:
        failures.append(
            f"read context after researching (step {late_context + 1}, first web call at "
            f"step {first_web + 1}) — the playbook orders it the other way"
        )

    checks += 1
    if not answer.strip():
        failures.append("run ended with no answer — abandoned mid-trajectory")

    return TrajectoryResult(passed=not failures, failures=failures, checks_run=checks)
