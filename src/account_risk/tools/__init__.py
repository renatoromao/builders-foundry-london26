"""Tool wiring. The agents never know whether they talk to the mocks or to the real Fabric IQ and Work IQ:
only this module looks at DEMO_MODE (or FABRIC_IQ_MODE / WORK_IQ_MODE)."""

from typing import Any

from account_risk.config import Settings
from account_risk.tools import live, mock
from account_risk.tools.actions import create_follow_up_task, send_email


def fabric_iq_tool(settings: Settings) -> Any:
    """The business: Customer, Order, Shipment and Inventory from the Fabric IQ ontology."""
    return mock.fabric_iq(settings) if settings.fabric_iq_is_mock else live.fabric_iq(settings)


def work_iq_tool(settings: Settings) -> Any:
    """The people: emails, meetings, chats and owners from Microsoft 365, as the signed-in user."""
    return mock.work_iq(settings) if settings.work_iq_is_mock else live.work_iq(settings)


ACTION_TOOLS = [send_email, create_follow_up_task]

__all__ = ["ACTION_TOOLS", "fabric_iq_tool", "work_iq_tool"]
