"""Host the Demo 1 agent with the Foundry Hosted Agents Responses protocol (2.0.0).

    uv run --extra hosting python -m account_risk.hosting      # http://localhost:8088/responses

The same entry point runs in Foundry Agent Service (scripts/deploy_hosted_agent.py uploads it).
`agent-framework-foundry-hosting` is a prerelease package (October 2026).
"""

from agent_framework_foundry_hosting import ResponsesHostServer

from account_risk.agents import create_risk_agent
from account_risk.config import get_settings
from account_risk.telemetry import setup_telemetry


def main() -> None:
    settings = get_settings()
    setup_telemetry(settings)
    # A fresh agent per request: each conversation gets its own session and MCP connections.
    server = ResponsesHostServer(agent=lambda: create_risk_agent(settings), history_source="agent_server")
    server.run()


if __name__ == "__main__":
    main()
