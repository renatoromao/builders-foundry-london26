"""Chat clients: one per agent, so every agent can use a different model from the Foundry catalog."""

from __future__ import annotations

import os
from functools import cache
from typing import Any

from azure.identity import DefaultAzureCredential

from account_risk.config import Settings

# Only the classic chat models take `temperature`; reasoning models (o-series, gpt-5, gpt-6…) reject it
# and take a reasoning effort instead.
TEMPERATURE_MODEL_PREFIXES = ("gpt-4", "gpt-35", "gpt-3.5")


@cache
def credential() -> DefaultAzureCredential:
    """Entra ID only: `az login` on the laptop, the agent's managed identity when hosted. No keys in code."""
    return DefaultAzureCredential(managed_identity_client_id=os.environ.get("FOUNDRY_AGENT_INSTANCE_CLIENT_ID"))


def chat_client(settings: Settings, model: str) -> Any:
    """Return a chat client for `model` using the configured provider."""
    if settings.model_provider == "foundry":
        from agent_framework.foundry import FoundryChatClient

        return FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=model,
            credential=credential(),
        )

    if settings.model_provider == "azure_openai":
        from agent_framework.openai import OpenAIChatClient

        return OpenAIChatClient(model=model, azure_endpoint=settings.azure_openai_endpoint, credential=credential())

    if settings.model_provider == "openai_compatible":
        # Offline fallback: Foundry Local, Ollama, LM Studio... anything with /v1/chat/completions.
        from agent_framework.openai import OpenAIChatCompletionClient

        return OpenAIChatCompletionClient(
            model=model, base_url=settings.openai_base_url, api_key=settings.openai_api_key or "local"
        )

    raise ValueError(f"Unknown MODEL_PROVIDER '{settings.model_provider}'.")


def model_options(settings: Settings, model: str) -> dict[str, Any]:
    """Default chat options: low temperature, or low reasoning effort for reasoning models (fast enough for stage)."""
    if model.lower().startswith(TEMPERATURE_MODEL_PREFIXES):
        return {} if settings.temperature is None else {"temperature": settings.temperature}
    return {"reasoning": {"effort": os.environ.get("REASONING_EFFORT", "low")}}
