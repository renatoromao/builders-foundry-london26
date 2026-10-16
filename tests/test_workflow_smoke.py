"""Smoke tests in mock mode with a scripted model: tools, approvals and memory end to end."""

from account_risk.agents import create_risk_agent
from account_risk.runner import run_agent_turn, run_workflow
from account_risk.tools.actions import outbox_entries
from account_risk.workflow import build_workflow


REQUEST = "Prepare my QBR with Zava Lisboa"


async def test_risk_agent_calls_fabric_iq_and_work_iq(settings, scripted_models, tool_calls):
    agent = create_risk_agent(settings)
    async with agent:
        response = await run_agent_turn(agent, "risk_agent", "Which key accounts are at risk?",
                                        agent.create_session(), timeout=60)
    assert ("risk_agent", "search_ontology") in tool_calls
    assert ("risk_agent", "retrieve") in tool_calls
    assert "Zava Lisboa" in response.text


async def test_workflow_asks_approval_before_sending(settings, scripted_models, tool_calls, approve):
    decisions = approve(True)
    async with build_workflow(settings).running() as app:
        await run_workflow(app.workflow, REQUEST, timeout=60)
    assert [tool for tool, _ in decisions] == ["send_email", "create_follow_up_task"]
    assert ("data_analyst", "search_ontology") in tool_calls
    assert ("work_context", "retrieve") in tool_calls
    assert sorted(e["kind"] for e in outbox_entries()) == ["email", "task"]  # approved calls run in parallel


async def test_rejecting_stops_the_send(settings, scripted_models, approve):
    approve(False)
    async with build_workflow(settings).running() as app:
        await run_workflow(app.workflow, REQUEST, timeout=60)
    assert outbox_entries() == []


async def test_follow_up_uses_the_action_agents_memory(settings, scripted_models, approve):
    approve(True)
    async with build_workflow(settings).running() as app:
        await run_workflow(app.workflow, REQUEST, timeout=60)
        scripted_models.seen.clear()
        await run_agent_turn(app.action_agent, "action", "Make the email shorter", app.action_session, timeout=60)
    first_call = scripted_models.seen[0]
    assert any("Account manager request" in text for text in first_call)  # earlier context is remembered
    assert first_call[-1] == "Make the email shorter"
