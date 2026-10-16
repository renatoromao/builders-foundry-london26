"""The run-of-show for Demo 1 and Demo 2. Each step pauses so the presenter controls the pace."""

from __future__ import annotations

import json
from typing import Any

from agent_framework import Agent, WorkflowViz

from account_risk import console as ui
from account_risk.agents import create_risk_agent
from account_risk.config import ROOT, Settings
from account_risk.runner import run_agent_turn, run_workflow
from account_risk.telemetry import trace_id, tracer
from account_risk.tools.actions import outbox_entries
from account_risk.workflow import build_workflow

DEMO1_QUESTION = "Which key accounts are at risk this week and why?"
DEMO2_REQUEST = "Prepare my QBR with Zava Lisboa tomorrow: how big is the risk, why, and what should I do?"


def _subtitle(settings: Settings, model: str, tracing: str) -> str:
    return f"mode: {settings.demo_mode} · model: {model} · tracing: {tracing}"


# ============================================================================ Demo 1


async def demo1(settings: Settings, tracing: str, question: str | None) -> None:
    ui.banner("Demo 1 · Fabric IQ + Work IQ Agent", _subtitle(settings, settings.models.orchestrator, tracing))
    agent = create_risk_agent(settings)
    async with agent:  # connects both MCP tools
        ui.step(1, "Fabric IQ — the business (ontology over OneLake)")
        await _show_fabric_iq(settings, agent)
        ui.pause()

        ui.step(2, "Work IQ — the people (Microsoft 365, as the signed-in user)")
        _show_tools(agent, "work_iq", settings)
        ui.pause()

        ui.step(3, "The agent: Microsoft Agent Framework + a Foundry model + both MCP tools")
        ui.code(str(ROOT / "src/account_risk/agents/risk_agent.py"), "src/account_risk/agents/risk_agent.py")
        ui.pause()

        ui.step(4, "Ask the question")
        session = agent.create_session()
        await _ask_with_followups(settings, agent, "risk_agent", question or DEMO1_QUESTION, session,
                                  hint="Try: “And what about the second account?”")


async def _show_fabric_iq(settings: Settings, agent: Agent) -> None:
    tool = _mcp_tool(agent, "fabric_iq")
    if tool is None:
        ui.info(f"Fabric IQ runs inside Foundry (connection {settings.fabric_iq_connection_id}).")
        return
    ui.info(f"MCP endpoint: {'local mock server (stdio) · mocks/fabric_iq_mcp.py' if settings.is_mock else settings.fabric_iq_mcp_url}")
    if any(f.name == "list_ontology_entity_types" for f in tool.functions):
        ontology = _json(await tool.call_tool("list_ontology_entity_types"))
        rows = [[e["name"], e["key"], ", ".join(list(e["properties"])[:6]) + " …", "\n".join(e["relationships"])]
                for e in ontology.get("entity_types", [])]
        ui.table(f"Ontology · {ontology.get('ontology', '')}", ["Entity", "Key", "Properties", "Relationships"], rows)
    _show_tools(agent, "fabric_iq", settings)


def _show_tools(agent: Agent, name: str, settings: Settings) -> None:
    tool = _mcp_tool(agent, name)
    if tool is None:
        ui.info(f"{name} is a Foundry tool (runs in Foundry Agent Service, on behalf of the signed-in user).")
        return
    rows = [[f.name, (f.description or "").split("\n")[0]] for f in tool.functions]
    where = "mock MCP server" if settings.is_mock else "MCP server"
    ui.table(f"{name} · tools exposed by the {where}", ["Tool", "Description"], rows)


def _mcp_tool(agent: Agent, name: str) -> Any:
    """The client-side MCP tool with this name (None when the tool runs inside Foundry)."""
    return next((t for t in agent.mcp_tools if t.name == name), None)


def _json(result: Any) -> dict[str, Any]:
    text = result if isinstance(result, str) else " ".join(getattr(c, "text", "") or "" for c in result)
    return json.loads(text)


# ============================================================================ Demo 2


async def demo2(settings: Settings, tracing: str, request: str | None) -> None:
    ui.banner("Demo 2 · Multi-Agent + Human Approval", _subtitle(settings, "per agent (see .env)", tracing))
    app = build_workflow(settings)
    async with app.running():
        ui.step(1, "The workflow: plan → concurrent specialists → Action agent (with approval)")
        ui.console.print(WorkflowViz(app.workflow).to_mermaid(), style="dim")
        _show_models(settings)
        ui.pause()

        ui.step(2, "Run it for Zava Lisboa")
        before = len(outbox_entries())
        with tracer.start_as_current_span("account_risk.demo2") as span:
            span.set_attribute("account_risk.request", request or DEMO2_REQUEST)
            await run_workflow(app.workflow, request or DEMO2_REQUEST, settings.run_timeout_seconds)
            _print_trace_id(span)
        _show_outbox(before)

        ui.step(3, "Follow-up questions use the Action agent's memory (same session)")
        await _ask_with_followups(settings, app.action_agent, "action", None, app.action_session,
                                  hint="Try: “Make the email shorter and mention the express delivery option.”")


def _show_models(settings: Settings) -> None:
    m = settings.models
    ui.table("One model per agent", ["Agent", "Model"], [
        ["🧭 Orchestrator", m.orchestrator], ["📊 Data Analyst", m.data_analyst],
        ["💬 Work Context", m.work_context], ["📝 Action", m.action],
    ])


def _show_outbox(before: int) -> None:
    new = outbox_entries()[before:]
    if not new:
        ui.warn("Outbox: nothing was sent.")
    for entry in new:
        what = f"email to {entry['to']} · {entry['subject']}" if entry["kind"] == "email" else f"task · {entry['title']}"
        ui.success(f"Outbox: {what}")


# ============================================================================ shared


async def _ask_with_followups(settings: Settings, agent: Agent, label: str, first: str | None,
                              session: Any, hint: str) -> None:
    message = first
    if message:
        ui.console.print(f"\n[bold]You ›[/] {message}")
    while True:
        if message:
            before = len(outbox_entries())
            with tracer.start_as_current_span(f"account_risk.{label}.turn") as span:
                span.set_attribute("account_risk.question", message)
                await run_agent_turn(agent, label, message, session, settings.run_timeout_seconds)
                _print_trace_id(span)
            if label == "action":
                _show_outbox(before)
        message = ui.ask(f"Follow-up (Enter to finish) · {hint}")
        if not message:
            return


def _print_trace_id(span: Any) -> None:
    if tid := trace_id(span):
        ui.info(f"Trace id: {tid} · Foundry → Observability → Traces (or App Insights → Transaction search)")
