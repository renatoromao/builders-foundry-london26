"""Reuse agents that already exist in Microsoft Foundry (built in the portal) inside our workflow."""

from agent_framework.foundry import FoundryAgent

from account_risk.clients import credential
from account_risk.config import Settings
from account_risk.telemetry import observe_tools


def reuse_foundry_agent(settings: Settings, agent_name: str, label: str, agent_id: str) -> FoundryAgent:
    """Use an agent that already exists in Foundry: its instructions, model and tools live in the portal."""
    return FoundryAgent(
        project_endpoint=settings.foundry_project_endpoint,
        agent_name=agent_name,
        credential=credential(),
        allow_preview=True,
        name=label,  # keeps the workflow node id stable
        id=agent_id,
        middleware=[observe_tools(label)],
    )
