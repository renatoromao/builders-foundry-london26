"""Side-effect tools of the Action agent. Both require human approval before they run.

On stage they write to a local demo outbox (.demo_state/outbox.jsonl) in both modes, so nothing real is
ever sent. In production you would call Microsoft Graph (or a Work IQ action) here instead.
"""

import json
from datetime import datetime
from typing import Annotated, Any

from agent_framework import tool
from pydantic import Field

from account_risk.config import STATE_DIR

OUTBOX = STATE_DIR / "outbox.jsonl"


def _record(kind: str, payload: dict[str, Any]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    entry = {"kind": kind, "at": datetime.now().isoformat(timespec="seconds"), **payload}
    with OUTBOX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@tool(approval_mode="always_require")
def send_email(
    to: Annotated[str, Field(description="Recipient email address.")],
    subject: Annotated[str, Field(description="Email subject.")],
    body: Annotated[str, Field(description="Plain-text email body.")],
) -> str:
    """Send an email on behalf of the account manager. Requires the account manager's approval."""
    _record("email", {"to": to, "subject": subject, "body": body})
    return f"Email sent to {to}."


@tool(approval_mode="always_require")
def create_follow_up_task(
    title: Annotated[str, Field(description="Short task title.")],
    owner: Annotated[str, Field(description="Person responsible for the task.")],
    due_date: Annotated[str, Field(description="Due date, YYYY-MM-DD.")],
) -> str:
    """Create a follow-up task for the recovery plan. Requires the account manager's approval."""
    _record("task", {"title": title, "owner": owner, "due_date": due_date})
    return f"Task '{title}' created for {owner}, due {due_date}."


def outbox_entries() -> list[dict[str, Any]]:
    if not OUTBOX.exists():
        return []
    return [json.loads(line) for line in OUTBOX.read_text(encoding="utf-8").splitlines() if line.strip()]
