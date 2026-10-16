"""Demo 2 · The Account Risk workflow.

    Orchestrator ──► Data Analyst (Fabric IQ) ──┐
         (plan)  └─► Work Context (Work IQ) ────┴─► merge_findings ──► Action (briefing + approval)

Concurrent fan-out to the two specialists (they don't depend on each other, so we don't wait twice),
then a sequential hand-off to the Action agent, whose side-effect tools need human approval.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from agent_framework import (
    Agent,
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    AgentSession,
    Executor,
    Message,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    handler,
)

from account_risk.agents import (
    create_action_agent,
    create_data_analyst,
    create_orchestrator,
    create_work_context,
)
from account_risk.config import Settings


# What each specialist must do. Sent with the request because agents reused from Foundry keep their own
# instructions in the portal (the service rejects instructions sent from code for an existing agent).
SPECIALIST_BRIEFS = {
    "data_analyst": "You are the Data Analyst: answer only with business facts (orders, shipments, stock) "
                    "from Fabric IQ, at most 8 bullets, each with its source.",
    "work_context": "You are the Work Context agent: answer only with people facts (emails, meetings, Teams "
                    "messages, owners) from Work IQ, at most 8 bullets, each citing the subject or title and the "
                    "date, and include the buyer's email address. Tool rules: when you search mail or calendar "
                    "use $top=5 and $select=id,subject,from,receivedDateTime,bodyPreview.",
}


class Orchestrator(Executor):
    """Builds the plan, shows it, then sends the request + plan to both specialists at once."""

    def __init__(self, planner: Agent) -> None:
        super().__init__(id="orchestrator")
        self.planner = planner

    @handler
    async def plan(self, request: str, ctx: WorkflowContext[AgentExecutorRequest, str]) -> None:
        plan = await self.planner.run(request)
        await ctx.yield_output(plan.text)  # shown on screen as "the plan"
        for specialist, role in SPECIALIST_BRIEFS.items():  # fan-out: both start at the same time
            brief = f"{role}\n\nRequest: {request}\n\nPlan from the Orchestrator:\n{plan.text}"
            message = Message("user", [brief])
            await ctx.send_message(AgentExecutorRequest(messages=[message], should_respond=True), target_id=specialist)


@executor(id="merge_findings")
async def merge_findings(results: list[AgentExecutorResponse], ctx: WorkflowContext[AgentExecutorRequest]) -> None:
    """Fan-in: wait for both specialists, then hand their findings to the Action agent."""
    findings = {r.executor_id: r.agent_response.text for r in results}
    first = next(m.text for m in results[0].full_conversation if m.role == "user")
    request = first.split("Request: ", 1)[-1].split("\n\nPlan from")[0]
    brief = (
        f"Account manager request: {request}\n\n"
        f"## Data Analyst findings (Fabric IQ)\n{findings.get('data_analyst', '(none)')}\n\n"
        f"## Work Context findings (Work IQ)\n{findings.get('work_context', '(none)')}"
    )
    await ctx.send_message(AgentExecutorRequest(messages=[Message("user", [brief])], should_respond=True))


@dataclass
class AccountRiskWorkflow:
    workflow: Workflow
    agents: list[Agent]
    action_agent: Agent
    action_session: AgentSession  # the Action agent's memory, reused for follow-up questions

    @asynccontextmanager
    async def running(self) -> AsyncIterator[AccountRiskWorkflow]:
        """Open every agent (model clients and MCP connections) for the duration of the block."""
        async with AsyncExitStack() as stack:
            for agent in self.agents:
                await stack.enter_async_context(agent)
            yield self


def build_workflow(settings: Settings) -> AccountRiskWorkflow:
    planner = create_orchestrator(settings)
    data_analyst = create_data_analyst(settings)
    work_context = create_work_context(settings)
    action_agent = create_action_agent(settings)
    action_session = action_agent.create_session()

    orchestrator = Orchestrator(planner)
    action = AgentExecutor(action_agent, session=action_session, id="action")

    workflow = (
        WorkflowBuilder(
            name="account-risk-workflow",
            start_executor=orchestrator,
            output_from=[action],
            intermediate_output_from="all_other",
        )
        .add_fan_out_edges(orchestrator, [data_analyst, work_context])  # concurrent
        .add_fan_in_edges([data_analyst, work_context], merge_findings)  # wait for both
        .add_edge(merge_findings, action)  # then sequential hand-off
        .build()
    )
    return AccountRiskWorkflow(workflow, [planner, data_analyst, work_context, action_agent], action_agent, action_session)
