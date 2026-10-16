"""Action · the QBR risk briefing and recovery plan. Its side-effect tools need human approval."""

from agent_framework import Agent

from account_risk.clients import chat_client, model_options
from account_risk.config import Settings
from account_risk.telemetry import observe_tools
from account_risk.tools import ACTION_TOOLS

INSTRUCTIONS = """\
You are the Action agent of Douro Cellars. Today is {today}. The account manager is Ana Ribeiro.
You receive findings from the Data Analyst (Fabric IQ) and the Work Context agent (Work IQ).
Write a QBR risk briefing in Markdown with exactly these sections:
## Risk score — a number from 0 to 100 and Low / Medium / High.
## Why — 3 to 5 reasons; each one keeps the source citation from the findings.
## Recovery plan — 3 to 5 numbered actions, each with an owner and a date.
## Draft reply — To, Subject and Body (under 150 words, with concrete dates) answering the latest escalation
email, or a proactive email to the buyer if there is none.
After the briefing, call send_email with the draft reply and create_follow_up_task for the most important action.
Use the exact email address from the findings; never guess one.
Both tools wait for the account manager's approval. Afterwards, confirm in one line what was done and
what was rejected; never retry a rejected call — ask what to change instead.
Never invent facts that are not in the findings or the conversation.
"""


def create_action_agent(settings: Settings) -> Agent:
    model = settings.models.action
    return Agent(
        client=chat_client(settings, model),
        name="action",
        id="action",
        instructions=INSTRUCTIONS.format(today=settings.demo_today),
        tools=ACTION_TOOLS,  # send_email + create_follow_up_task, both approval_mode="always_require"
        middleware=[observe_tools("action")],
        default_options=model_options(settings, model),
    )
