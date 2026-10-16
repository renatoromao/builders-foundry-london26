"""Data Analyst · read-only questions to Fabric IQ: orders, shipments, stock."""

from agent_framework import Agent

from account_risk.agents.foundry import reuse_foundry_agent
from account_risk.clients import chat_client, model_options
from account_risk.config import Settings
from account_risk.telemetry import observe_tools
from account_risk.tools import fabric_iq_tool

INSTRUCTIONS = """\
You are the Data Analyst of Douro Cellars. Today is {today}. Your only source is Fabric IQ, the business ontology.
- Ask Fabric IQ one focused question at a time: late shipments, stock for the top SKU, order volume trend, open orders.
- Only key accounts matter; leave Standard accounts out.
- Report facts, not advice: at most 8 bullets with numbers, dates and IDs.
- End every bullet with its source, e.g. [Fabric IQ: SHP-24131] or [Fabric IQ: inventory SKU-TW10].
"""


def create_data_analyst(settings: Settings, model: str | None = None) -> Agent:
    if settings.data_analyst_foundry_agent and not model:
        return reuse_foundry_agent(settings, settings.data_analyst_foundry_agent, "data_analyst", "data-analyst")
    model = model or settings.models.data_analyst  # Demo 3 swaps this to compare models
    return Agent(
        client=chat_client(settings, model),
        name="data_analyst",
        id="data-analyst",
        instructions=INSTRUCTIONS.format(today=settings.demo_today),
        tools=[fabric_iq_tool(settings)],
        middleware=[observe_tools("data_analyst")],
        default_options=model_options(settings, model),
    )

