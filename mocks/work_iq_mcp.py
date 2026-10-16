"""Mock Work IQ MCP server for Douro Cellars (synthetic Microsoft 365 data).

It mirrors a read-only subset of the real Work IQ MCP tools (`retrieve`, `ask`, `fetch`) and acts
as the signed-in account manager, Ana Ribeiro: she only sees mail, meetings and chats she is part of.

    uv run python -m mocks.work_iq_mcp           # stdio (what the agents use)
    uv run python -m mocks.work_iq_mcp --http    # http://127.0.0.1:8702/mcp
"""

import sys
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mocks import douro_data

server = FastMCP(
    name="work-iq-mock",
    host="127.0.0.1",
    log_level="WARNING",  # keep the presenter's console clean
    port=8702,
    instructions="Emails, meetings, Teams messages, people and files of the signed-in user (synthetic).",
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
Capability = Literal["Email", "Meetings", "TeamsMessages", "People", "OneDriveAndSharePoint"]


@server.tool(annotations=READ_ONLY)
def retrieve(
    query: str,
    strategy: Literal["grounding", "copilot"] = "grounding",
    capabilities: list[Capability] | None = None,
) -> dict[str, Any]:
    """Retrieve Microsoft 365 items (emails, meetings, Teams messages, people, files) relevant to a query.

    Mention an account name to focus on it (e.g. 'Zava Lisboa'). Each result has a `citation`
    (subject/title and date) that answers must quote.
    """
    return douro_data.retrieve(query, capabilities)


@server.tool(annotations=READ_ONLY)
def ask(question: str) -> dict[str, Any]:
    """Ask a natural-language question about the user's Microsoft 365 work context; returns an answer with citations."""
    return douro_data.ask(question)


@server.tool(annotations=READ_ONLY)
def fetch(entityUrls: list[str]) -> dict[str, Any]:  # noqa: N803 - same parameter name as Work IQ
    """Fetch full items by Graph-style path, e.g. /me/messages/MSG-1001 or /me/events/EVT-2001."""
    return douro_data.fetch(entityUrls)


if __name__ == "__main__":
    if "--http" in sys.argv:
        server.run("streamable-http")
    else:
        server.run()
