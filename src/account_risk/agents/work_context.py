"""Work Context · Work IQ, as the signed-in user: emails, meetings, Teams messages, owners."""

from agent_framework import Agent

from account_risk.agents.foundry import reuse_foundry_agent
from account_risk.clients import chat_client, model_options
from account_risk.config import Settings
from account_risk.telemetry import observe_tools
from account_risk.tools import work_iq_tool

INSTRUCTIONS = """\
You are the Work Context agent of Douro Cellars. Today is {today}.
Your only source is Work IQ: the signed-in account manager's emails, meetings, Teams messages, people and files.
- Search Work IQ with the account name in the query; fetch a full email only when you need its details.
- Look for escalations or complaints (and whether they were answered), upcoming or cancelled meetings,
  the account owner and buyer, and internal updates from colleagues.
- Always include the buyer's name and exact email address.
- Report facts, not advice: at most 8 bullets.
- End every bullet with its source, e.g. [Work IQ: email "Subject", 2026-10-16] or [Work IQ: meeting "Title", 2026-10-20].
"""


def create_work_context(settings: Settings) -> Agent:
    if settings.work_context_foundry_agent:
        return reuse_foundry_agent(settings, settings.work_context_foundry_agent, "work_context", "work-context")
    model = settings.models.work_context
    return Agent(
        client=chat_client(settings, model),
        name="work_context",
        id="work-context",
        instructions=INSTRUCTIONS.format(today=settings.demo_today),
        tools=[work_iq_tool(settings)],
        middleware=[observe_tools("work_context")],
        default_options=model_options(settings, model),
    )

