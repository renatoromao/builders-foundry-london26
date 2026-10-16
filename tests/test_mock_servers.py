"""Start the real mock MCP servers through the same wiring the agents use."""

import json

from account_risk.tools import mock


def _json(result):
    text = result if isinstance(result, str) else " ".join(c.text or "" for c in result)
    return json.loads(text)


async def test_fabric_iq_mock_server_exposes_the_ontology_tools(settings):
    async with mock.fabric_iq(settings) as fabric_iq:
        assert {f.name for f in fabric_iq.functions} == {"list_ontology_entity_types", "search_ontology"}
        ontology = _json(await fabric_iq.call_tool("list_ontology_entity_types"))
        assert [e["name"] for e in ontology["entity_types"]] == ["Customer", "Order", "Shipment", "Inventory"]
        answer = _json(await fabric_iq.call_tool("search_ontology", question="late shipments for key accounts"))
        assert "Zava Lisboa: 3" in answer["answer"]


async def test_work_iq_mock_server_exposes_read_only_tools(settings):
    async with mock.work_iq(settings) as work_iq:
        assert {f.name for f in work_iq.functions} == {"retrieve", "ask", "fetch"}
        found = _json(await work_iq.call_tool("retrieve", query="Zava Lisboa"))
        assert any("URGENT" in r["citation"] for r in found["results"])
