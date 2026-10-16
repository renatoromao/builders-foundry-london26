"""Live wiring for the real Fabric IQ and Work IQ. Both Foundry tools are in preview (October 2026).

Each source supports two documented paths:
1. A Foundry project connection -> a Foundry tool that Foundry runs on behalf of the signed-in user (OBO).
   Fabric IQ: `fabric_iq_preview`  https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq
   Work IQ:   `work_iq_preview`    https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq
2. An MCP endpoint called directly with an Entra ID token, e.g. a Foundry toolbox MCP endpoint
   (https://<account>.services.ai.azure.com/api/projects/<project>/toolboxes/<name>/mcp?api-version=v1).
"""

from typing import Any

from agent_framework import MCPStreamableHTTPTool
from azure.ai.projects.models import FabricIQPreviewTool, WorkIQPreviewTool
from azure.identity import get_bearer_token_provider

from account_risk.clients import credential
from account_risk.config import ConfigError, Settings

WORK_IQ_READ_ONLY_TOOLS = ["retrieve", "ask", "fetch"]


def fabric_iq(settings: Settings) -> Any:
    if settings.fabric_iq_connection_id:
        _require_foundry(settings)
        return FabricIQPreviewTool(
            project_connection_id=settings.fabric_iq_connection_id,
            server_label="fabric_iq",
            server_url=settings.fabric_iq_mcp_url,  # optional: defaults to the connection's URL
            require_approval="never",  # read-only queries
        )
    if settings.fabric_iq_mcp_url:
        return _direct_mcp("fabric_iq", settings.fabric_iq_mcp_url, settings.fabric_iq_token_scope)
    raise ConfigError("Live mode needs FABRIC_IQ_CONNECTION_ID (Foundry connection) or FABRIC_IQ_MCP_URL.")


def work_iq(settings: Settings) -> Any:
    if settings.work_iq_connection_id:
        _require_foundry(settings)
        return WorkIQPreviewTool(project_connection_id=settings.work_iq_connection_id)
    if settings.work_iq_mcp_url:
        return _direct_mcp("work_iq", settings.work_iq_mcp_url, settings.work_iq_token_scope,
                           allowed_tools=WORK_IQ_READ_ONLY_TOOLS)
    raise ConfigError("Live mode needs WORK_IQ_CONNECTION_ID (Foundry connection) or WORK_IQ_MCP_URL.")


def _direct_mcp(name: str, url: str, scope: str, allowed_tools: list[str] | None = None) -> MCPStreamableHTTPTool:
    get_token = get_bearer_token_provider(credential(), scope)
    return MCPStreamableHTTPTool(
        name=name,
        url=url,
        header_provider=lambda _kwargs: {"Authorization": f"Bearer {get_token()}"},
        allowed_tools=allowed_tools,
        load_prompts=False,
    )


def _require_foundry(settings: Settings) -> None:
    if settings.model_provider != "foundry":
        raise ConfigError("Foundry tool connections need MODEL_PROVIDER=foundry (they run inside Foundry Agent Service).")
