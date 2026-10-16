"""Mock wiring: local MCP servers (stdio) that serve the synthetic Douro Cellars data. No tenant needed."""

import sys

from agent_framework import MCPStdioTool

from account_risk.config import ROOT, Settings


def _local_server(name: str, module: str, description: str, settings: Settings) -> MCPStdioTool:
    return MCPStdioTool(
        name=name,
        description=description,
        command=sys.executable,
        args=["-m", module],
        cwd=str(ROOT),
        env={"DEMO_TODAY": settings.demo_today.isoformat()},
        load_prompts=False,
    )


def fabric_iq(settings: Settings) -> MCPStdioTool:
    return _local_server(
        "fabric_iq", "mocks.fabric_iq_mcp",
        "Fabric IQ ontology (mock): customers, orders, shipments and inventory.", settings,
    )


def work_iq(settings: Settings) -> MCPStdioTool:
    return _local_server(
        "work_iq", "mocks.work_iq_mcp",
        "Work IQ (mock): the signed-in user's emails, meetings, Teams messages, people and files.", settings,
    )
