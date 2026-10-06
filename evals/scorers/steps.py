"""One tool call, normalised.

Both the trajectory and component scorers read a run as a flat list of steps
rather than as Inspect message objects. That keeps the scoring logic testable
without constructing a whole conversation, and it means the same scorers work
if the agent is later executed through a different harness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Step:
    """A single tool call and what came back."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    error: bool = False
    result: str = ""

    def signature(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        """Identity for repeat detection — same tool, same arguments."""
        return (self.tool, tuple(sorted((k, str(v)) for k, v in self.arguments.items())))


def steps_from_messages(messages: list[Any]) -> list[Step]:
    """Flatten an Inspect message list into steps, in call order.

    Tool calls live on assistant messages; their results arrive as separate tool
    messages keyed by call id. Pairing them here means a scorer never has to know
    that, and an unmatched call (the run ended mid-flight) still shows up as a
    step rather than vanishing.
    """
    results: dict[str, Any] = {}
    for message in messages:
        if getattr(message, "role", None) == "tool":
            call_id = getattr(message, "tool_call_id", None)
            if call_id is not None:
                results[call_id] = message

    steps: list[Step] = []
    for message in messages:
        if getattr(message, "role", None) != "assistant":
            continue
        for call in getattr(message, "tool_calls", None) or []:
            result = results.get(call.id)
            error = getattr(result, "error", None) if result is not None else None
            steps.append(
                Step(
                    tool=call.function,
                    arguments=dict(call.arguments or {}),
                    error=error is not None,
                    result=str(getattr(result, "text", "") or "") if result is not None else "",
                )
            )
    return steps
