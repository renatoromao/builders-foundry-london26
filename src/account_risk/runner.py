"""Run an agent or the workflow on stage: spinners, tool-call lines, approvals, timeouts."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from agent_framework import Agent, AgentResponse, AgentResponseUpdate, AgentSession, Content, Message, Workflow

from account_risk import console as ui


class WorkflowFailed(Exception):
    pass


def _ask_approval(agent: str, request: Content) -> Content:
    call = request.function_call
    arguments = call.parse_arguments() or {}
    return request.to_function_approval_response(approved=ui.approval(agent, call.name, arguments))


def _show_hosted_tool_calls(agent: str, contents: Iterable[Content]) -> None:
    """Tools that run inside Foundry (live mode) don't pass through our middleware; show them here."""
    for content in contents:
        if content.type == "mcp_server_tool_call" and content.arguments:  # approved reads were already shown
            ui.tool_call(agent, content.tool_name or "tool", content.arguments, hosted=True, server=content.server_name)


def needs_human(agent: str) -> bool:
    """Only the Action agent's side effects wait for a person; the specialists' Foundry tool reads are
    approved automatically (better: set 'require approval: never' on read-only tools in the portal)."""
    return agent == "action"


def auto_approve(agent: str, request: Content) -> Content:
    call = request.function_call
    ui.tool_call(agent, call.name, call.arguments, hosted=True, server=getattr(call, "server_name", None))
    return request.to_function_approval_response(approved=True)


async def run_agent_turn(agent: Agent, label: str, message: str | Message, session: AgentSession,
                         timeout: int) -> AgentResponse:
    """One user turn: run the agent, show its answer, and loop while it waits for approvals."""
    pending: Any = message
    while True:
        with ui.working(label, "is thinking…"):
            async with asyncio.timeout(timeout):
                response = await agent.run(pending, session=session)
        _show_hosted_tool_calls(label, (c for m in response.messages for c in m.contents))
        if response.text:
            ui.agent_message(label, response.text)
        requests = [r for r in response.user_input_requests if r.function_call is not None]
        if not requests:
            return response
        pending = Message("user", [_ask_approval(label, r) if needs_human(label) else auto_approve(label, r)
                                   for r in requests])


async def run_workflow(workflow: Workflow, request: str, timeout: int) -> None:
    """Stream the workflow: each agent's output appears as soon as that agent finishes."""
    updates: dict[str, list[AgentResponseUpdate]] = defaultdict(list)
    started: set[str] = set()
    stream = workflow.run(request, stream=True)
    while True:
        approvals: dict[str, tuple[str, Content]] = {}
        with ui.working("orchestrator", "agents are working…"):
            async with asyncio.timeout(timeout):
                async for event in stream:
                    _handle_event(event, updates, started, approvals)
        if not approvals:
            return
        responses = {request_id: _ask_approval(agent, req) if needs_human(agent) else auto_approve(agent, req)
                     for request_id, (agent, req) in approvals.items()}
        stream = workflow.run(stream=True, responses=responses)


def _handle_event(event: Any, updates: dict[str, list[AgentResponseUpdate]], started: set[str],
                  approvals: dict[str, tuple[str, Content]]) -> None:
    agent = event.executor_id or ""
    if event.type == "executor_invoked" and agent in ui.AGENTS and agent not in started:
        started.add(agent)
        ui.info(f"   ▶ {ui.label(agent)} started")
    elif event.type in ("output", "intermediate"):
        if isinstance(event.data, AgentResponseUpdate):
            updates[agent].append(event.data)
            _show_hosted_tool_calls(agent, event.data.contents)
        elif isinstance(event.data, str) and agent == "orchestrator":
            ui.agent_message("orchestrator", event.data, title="Orchestrator · the plan")
    elif event.type == "executor_completed" and updates.get(agent):
        # from_updates merges streamed deltas (and the final 'done' event) into the real text.
        text = AgentResponse.from_updates(updates.pop(agent)).text
        if text:
            ui.agent_message(agent, text)
    elif event.type == "request_info" and isinstance(event.data, Content):
        if event.data.type == "function_approval_request":
            approvals[event.request_id] = (event.source_executor_id or agent, event.data)
    elif event.type == "failed":
        raise WorkflowFailed(str(event.details))
