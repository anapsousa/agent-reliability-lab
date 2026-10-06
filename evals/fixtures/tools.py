"""The research-agent's tool surface, as plain functions.

Two harnesses expose these tools: the Inspect port (`evals/tasks/research_agent.py`)
and the MCP server that the real Claude Code agent calls (`mcp/fixture-web/`). Both
must return byte-identical text, or a pass-rate difference between harnesses could
be a formatting artefact rather than a real difference in the agent. So the text is
produced here, once, and each harness only translates `ToolFailure` into its own
error type.
"""

from __future__ import annotations

from pathlib import Path

from evals.fixtures.corpus import Corpus

REPO = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO / "agent" / "research-agent"

CONTEXT_FILES = {
    "role": "role.md",
    "research-memory": "research-memory.md",
    "playbook": "playbook.md",
    "company-context": "company-context.md",
}


class ToolFailure(Exception):
    """A tool call the agent made that cannot succeed. Surfaced to it as an error."""


def read_context_text(name: str, context_dir: Path = AGENT_DIR / "context") -> str:
    filename = CONTEXT_FILES.get(name)
    if filename is None:
        raise ToolFailure(f"no context file named {name!r}. Available: {', '.join(CONTEXT_FILES)}")
    path = context_dir / filename
    if not path.exists():
        raise ToolFailure(
            f"{filename} is not present. Populate the vendored context files first "
            "— see agent/research-agent/context/README.md."
        )
    return path.read_text(encoding="utf-8")


def web_search_text(corpus: Corpus, query: str) -> str:
    results = corpus.search(query)
    if not results:
        return f"No results for {query!r}."
    return "\n\n".join(
        f"{i}. {p.title}\n   URL: {p.url}\n   Published: {p.published}\n   {p.snippet()}"
        for i, p in enumerate(results, start=1)
    )


def web_fetch_text(corpus: Corpus, url: str) -> str:
    page = corpus.by_url(url)
    if page is None:
        # A 404 rather than a silent empty string: the agent has to learn
        # that a URL it invented does not resolve.
        raise ToolFailure(f"404 Not Found — {url} could not be retrieved.")
    body = page.public_body()
    if page.paywalled:
        body += "\n\n[Remaining content requires a subscription and was not retrieved.]"
    return f"# {page.title}\nURL: {page.url}\nPublished: {page.published}\n\n{body}"
