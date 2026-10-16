"""Optional: browse the Demo 1 agent and the Demo 2 workflow in Agent Framework DevUI (preview)."""

from account_risk.agents import create_risk_agent
from account_risk.config import Settings
from account_risk.workflow import build_workflow


def serve(settings: Settings, port: int) -> None:
    from agent_framework.devui import serve as devui_serve

    entities = [create_risk_agent(settings), build_workflow(settings).workflow]
    # Bound to localhost only, so the auth token is turned off to keep the stage flow simple.
    devui_serve(entities=entities, port=port, host="127.0.0.1", auto_open=True, auth_enabled=False,
                instrumentation_enabled=settings.tracing != "off")
