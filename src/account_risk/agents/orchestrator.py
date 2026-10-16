"""Orchestrator · turns the request into a short plan for the specialists. It has no tools."""

from agent_framework import Agent

from account_risk.clients import chat_client, model_options
from account_risk.config import Settings

INSTRUCTIONS = """\
You are the Orchestrator of the Douro Cellars account risk team. Today is {today}.
Turn the key account manager's request into a plan for three specialists:
- Data Analyst: business facts from Fabric IQ (orders, shipments, stock, order trends).
- Work Context: people facts from Work IQ (emails, meetings, Teams messages, owners).
- Action: the QBR risk briefing, the recovery plan and a draft reply.
Reply with a numbered plan of at most 5 short lines that names the account(s) in scope.
Do not answer the request yourself.
"""


def create_orchestrator(settings: Settings) -> Agent:
    model = settings.models.orchestrator
    return Agent(
        client=chat_client(settings, model),
        name="orchestrator",
        id="orchestrator",
        instructions=INSTRUCTIONS.format(today=settings.demo_today),
        default_options=model_options(settings, model),
    )
