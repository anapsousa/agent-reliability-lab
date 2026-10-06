"""fixture-web — the research-agent's web, served over MCP.

Lets the *real* Claude Code research-agent run against the frozen fixture corpus,
instead of the Inspect port. Same three tools, same descriptions, and the same text
for every result (it comes from `evals/fixtures/tools.py`, shared with the port), so
the only thing that differs between the two harnesses is the harness.

Read-only and side-effect free: every tool is idempotent by construction, there is no
auth to scope, and nothing leaves the process. Run over stdio:

    uv run python mcp/fixture-web/server.py

The directory is deliberately not a Python package: a `mcp/__init__.py` at the repo
root would shadow the `mcp` SDK this server is built on.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `evals`

from evals.fixtures.corpus import load_corpus
from evals.fixtures.tools import (
    ToolFailure,
    read_context_text,
    web_fetch_text,
    web_search_text,
)

server = MCPServer("fixture-web", log_level="WARNING")


# Plain text out, not structured output: the Inspect port returns plain text, and the
# two harnesses must hand the model the same bytes.
def _mcp_error(fn, *args):
    """Surface a ToolFailure as an MCP tool error, with its text intact.

    MCP SDK 2.x treats any other exception as a server crash and sends the model a
    generic "Error executing tool" in its place. The agent would never see the 404,
    and the invented-URL check would be scoring a message the agent never received.
    """
    try:
        return fn(*args)
    except ToolFailure as exc:
        raise ToolError(str(exc)) from exc


READ_ONLY = {
    "annotations": ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False),
    "structured_output": False,
}


@server.tool(**READ_ONLY)
def read_context(name: str) -> str:
    """Read one of your context files.

    Args:
        name: One of "role", "research-memory", "playbook", "company-context".

    Returns:
        The full contents of that context file.
    """
    return _mcp_error(read_context_text, name)


@server.tool(**READ_ONLY)
def web_search(query: str) -> str:
    """Search the web for pages relevant to a query.

    Args:
        query: The search terms.

    Returns:
        Ranked results, each with URL, title, publication date and a snippet.
    """
    return web_search_text(load_corpus(), query)


@server.tool(**READ_ONLY)
def web_fetch(url: str) -> str:
    """Fetch the full contents of a web page.

    Args:
        url: The URL to fetch.

    Returns:
        The page contents. Paywalled pages return their public abstract only.
    """
    return _mcp_error(web_fetch_text, load_corpus(), url)


if __name__ == "__main__":
    server.run()
