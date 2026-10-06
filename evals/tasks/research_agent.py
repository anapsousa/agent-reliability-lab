"""Inspect task for the pinned research-agent.

The agent under test is a Claude Code subagent. It is executed here as an
Inspect solver — the pinned `agent.md` becomes the system message, its four
context files become a `read_context` tool, and the web becomes the frozen
fixture corpus. That is a port, not the live agent, and the deviation is
recorded in `agent/research-agent/PINS.md`.

Run:
    uv run inspect eval evals/tasks/research_agent.py --model mockllm/model
    uv run inspect eval evals/tasks/research_agent.py --model anthropic/claude-sonnet-5
"""

from __future__ import annotations

from pathlib import Path

import yaml
from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer, stderr
from inspect_ai.solver import TaskState, generate, system_message, use_tools
from inspect_ai.tool import Tool, ToolError, tool

from evals.fixtures.corpus import Corpus, load_corpus
from evals.fixtures.tools import (
    CONTEXT_FILES,
    ToolFailure,
    read_context_text,
    web_fetch_text,
    web_search_text,
)
from evals.scorers.components import evaluate_components
from evals.scorers.outcome import evaluate_outcome
from evals.scorers.steps import steps_from_messages
from evals.scorers.trajectory import evaluate_trajectory

REPO = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO / "agent" / "research-agent"
GOLDEN_DIR = REPO / "evals" / "golden" / "research-agent"


# --------------------------------------------------------------------------- #
# Tools
#
# The text each tool returns lives in evals/fixtures/tools.py, shared with the MCP
# server the real Claude Code agent calls. These wrappers only own the docstrings
# (which Inspect turns into the tool descriptions the model sees) and the error type.
# --------------------------------------------------------------------------- #


def _inspect_error(fn, *args):
    try:
        return fn(*args)
    except ToolFailure as exc:
        raise ToolError(str(exc)) from exc


@tool
def read_context(version: str) -> Tool:
    """Read one of the agent's own context files."""

    async def execute(name: str) -> str:
        """Read one of your context files.

        Args:
            name: One of "role", "research-memory", "playbook", "company-context".

        Returns:
            The full contents of that context file.
        """
        return _inspect_error(read_context_text, name)

    return execute


@tool
def web_search(corpus: Corpus) -> Tool:
    """Search the frozen fixture corpus."""

    async def execute(query: str) -> str:
        """Search the web for pages relevant to a query.

        Args:
            query: The search terms.

        Returns:
            Ranked results, each with URL, title, publication date and a snippet.
        """
        return web_search_text(corpus, query)

    return execute


@tool
def web_fetch(corpus: Corpus) -> Tool:
    """Fetch one page from the frozen fixture corpus."""

    async def execute(url: str) -> str:
        """Fetch the full contents of a web page.

        Args:
            url: The URL to fetch.

        Returns:
            The page contents. Paywalled pages return their public abstract only.
        """
        return _inspect_error(web_fetch_text, corpus, url)

    return execute


# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #


def load_golden(directory: Path = GOLDEN_DIR) -> list[dict]:
    tasks = [
        yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("rsch-*.yaml"))
    ]
    if not tasks:
        raise ValueError(f"no golden tasks found in {directory}")
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate task ids in golden set: {ids}")
    return tasks


def golden_dataset(corpus_version: int) -> MemoryDataset:
    samples = []
    for spec in load_golden():
        if spec["corpus_version"] != corpus_version:
            raise ValueError(
                f"{spec['id']} was written against corpus v{spec['corpus_version']} "
                f"but the fixtures are v{corpus_version}. Re-validate the task or bump it."
            )
        samples.append(
            Sample(
                id=spec["id"],
                input=spec["input"].strip(),
                metadata={
                    "expected": spec["expected"],
                    "category": spec["category"],
                    "difficulty": spec["difficulty"],
                    "effort": spec["effort"],
                    "targets": spec.get("targets", []),
                    "trajectory": spec.get("trajectory", {}),
                },
            )
        )
    return MemoryDataset(samples)


# --------------------------------------------------------------------------- #
# Scorers
#
# Three layers, because "did it work" is three different questions. They are
# scored independently and never collapsed into one number: a run can reach the
# right answer through a loop, and a run can move sensibly and still be wrong.
# --------------------------------------------------------------------------- #


def _explain(result) -> str:
    if result.passed:
        return "all checks passed"
    return f"{len(result.failures)} failed: " + "; ".join(result.failures)


def _common_metadata(state: TaskState, result) -> dict:
    return {
        "checks_run": result.checks_run,
        "failures": result.failures,
        "difficulty": state.metadata["difficulty"],
        "category": state.metadata["category"],
        "targets": state.metadata["targets"],
    }


@scorer(metrics=[accuracy(), stderr()])
def outcome(ground_truth: dict):
    """Binary outcome layer. See evals/scorers/outcome.py for the checks."""

    async def score(state: TaskState, target: Target) -> Score:
        answer = state.output.completion or ""
        result = evaluate_outcome(answer, state.metadata["expected"], ground_truth)
        return Score(
            value=CORRECT if result.passed else INCORRECT,
            answer=answer,
            explanation=_explain(result),
            metadata=_common_metadata(state, result),
        )

    return score


@scorer(metrics=[accuracy(), stderr()])
def trajectory():
    """Was the path sane. See evals/scorers/trajectory.py."""

    async def score(state: TaskState, target: Target) -> Score:
        result = evaluate_trajectory(
            steps_from_messages(state.messages),
            state.output.completion or "",
            state.metadata.get("trajectory") or {},
        )
        return Score(
            value=CORRECT if result.passed else INCORRECT,
            explanation=_explain(result),
            metadata=_common_metadata(state, result),
        )

    return score


@scorer(metrics=[accuracy(), stderr()])
def components():
    """Right tool, right arguments, step count within budget. See evals/scorers/components.py."""

    async def score(state: TaskState, target: Target) -> Score:
        result = evaluate_components(
            steps_from_messages(state.messages),
            state.metadata.get("trajectory") or {},
            context_names=list(CONTEXT_FILES),
            task_input=state.input_text,
        )
        return Score(
            value=CORRECT if result.passed else INCORRECT,
            explanation=_explain(result),
            metadata=_common_metadata(state, result),
        )

    return score


# --------------------------------------------------------------------------- #
# Task
# --------------------------------------------------------------------------- #


def agent_system_prompt(version: str) -> str:
    """The pinned agent's system prompt, as the live agent receives it.

    Strips the YAML frontmatter and the maintainer comment: neither is part of what
    the live agent is sent. Shared by the Inspect port and the Claude Code runner.
    """
    agent_md = (AGENT_DIR / version / "agent.md").read_text(encoding="utf-8")
    body = agent_md.split("---", 2)[-1]
    return body.split("-->", 1)[-1].strip()


@task
def research_agent(version: str = "v1", message_limit: int = 25) -> Task:
    """Three-layer eval for the pinned research-agent: outcome, trajectory, component."""
    body = agent_system_prompt(version)

    corpus = load_corpus()

    return Task(
        dataset=golden_dataset(corpus_version=corpus.ground_truth["corpus_version"]),
        solver=[
            system_message(body),
            use_tools(read_context(version), web_search(corpus), web_fetch(corpus)),
            generate(),
        ],
        scorer=[outcome(corpus.ground_truth), trajectory(), components()],
        message_limit=message_limit,
        metadata={
            "agent_version": version,
            "corpus_version": corpus.ground_truth["corpus_version"],
        },
    )
