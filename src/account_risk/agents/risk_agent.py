"""Demo 1 · One agent, two sources of truth: Fabric IQ + Work IQ."""

from agent_framework import Agent

from account_risk.clients import chat_client, model_options
from account_risk.config import Settings
from account_risk.telemetry import observe_tools
from account_risk.tools import fabric_iq_tool, work_iq_tool

INSTRUCTIONS = """\
You are the Account Risk Agent of Douro Cellars, a Porto wine exporter.
Today is {today}. Find which key accounts are at risk this week, why, and what to do.
Always use both sources, in this order:
1. Fabric IQ (the business): late shipments, top-SKU stock, order volume trends.
2. Work IQ (the people): emails, meetings, Teams messages and owner of every
   flagged or named account.
Only key accounts matter: check the segment; a Standard account is never "at risk".
Cite every reason: [Fabric IQ: SHP-24131] or [Work IQ: email "Subject", date].
Recommend actions with the concrete options colleagues mention (costs, dates).
Be brief: a short section per at-risk account, then one line for the healthy ones.
"""


def create_risk_agent(settings: Settings) -> Agent:
    model = settings.models.orchestrator
    return Agent(
        client=chat_client(settings, model),  # a model from the Foundry catalog
        name="risk_agent",
        id="account-risk-agent",
        instructions=INSTRUCTIONS.format(today=settings.demo_today),
        tools=[fabric_iq_tool(settings), work_iq_tool(settings)],  # two MCP tools
        middleware=[observe_tools("risk_agent")],  # a span + a console line per call
        default_options=model_options(settings, model),
    )
