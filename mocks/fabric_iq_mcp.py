"""Mock Fabric IQ ontology MCP server for Douro Cellars (synthetic data).

It exposes the same tool names as the real Fabric IQ ontology MCP endpoint
(`list_ontology_entity_types`, `search_ontology`), so the agent code is identical in mock and live mode.

    uv run python -m mocks.fabric_iq_mcp           # stdio (what the agents use)
    uv run python -m mocks.fabric_iq_mcp --http    # http://127.0.0.1:8701/mcp (to show the endpoint on stage)
"""

import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mocks import douro_data

server = FastMCP(
    name="fabric-iq-mock",
    host="127.0.0.1",
    log_level="WARNING",  # keep the presenter's console clean
    port=8701,
    instructions="Douro Cellars business ontology: Customer, Order, Shipment, Inventory over OneLake (synthetic).",
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


@server.tool(annotations=READ_ONLY)
def list_ontology_entity_types() -> dict[str, Any]:
    """List the entity types of the Douro Cellars ontology with their properties, relationships and metrics."""
    return douro_data.list_entity_types()


@server.tool(annotations=READ_ONLY)
def search_ontology(question: str) -> dict[str, Any]:
    """Answer a natural-language question over the Douro Cellars ontology.

    Ask one focused question at a time, for example:
    'late shipments for key accounts', 'stock for the top SKU of Fabrikam',
    'order volume trend for key accounts', 'open orders for Zava Lisboa'.
    Returns raw rows per topic plus a short natural-language answer.
    """
    return douro_data.search_ontology(question)


if __name__ == "__main__":
    if "--http" in sys.argv:
        server.run("streamable-http")
    else:
        server.run()
