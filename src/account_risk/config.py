"""All configuration comes from environment variables (.env). DEMO_MODE switches mock vs live tools."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

# The folder that holds mocks/: the repo root locally, the bundle root when hosted in Foundry.
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "mocks").is_dir())
STATE_DIR = ROOT / ".demo_state"
LOG_DIR = ROOT / "logs"

load_dotenv(ROOT / ".env")

MOCK_DEMO_TODAY = "2026-10-19"  # fixed date that the synthetic data is built around


class ConfigError(Exception):
    """A setting is missing or invalid; the message tells the presenter how to fix it."""


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or default


@dataclass(frozen=True)
class Models:
    orchestrator: str
    data_analyst: str
    data_analyst_alt: str | None
    work_context: str
    action: str
    eval_judge: str  # LLM judge for the Foundry evaluators


@dataclass(frozen=True)
class Settings:
    demo_mode: str  # "mock" | "live"
    fabric_iq_mode: str  # per source, defaults to DEMO_MODE (e.g. Work IQ live + Fabric IQ mock)
    work_iq_mode: str
    # agents that already exist in Foundry and are reused instead of defined in code
    data_analyst_foundry_agent: str | None
    work_context_foundry_agent: str | None
    model_provider: str  # "foundry" | "azure_openai" | "openai_compatible"
    foundry_project_endpoint: str | None
    models: Models
    temperature: float | None
    # live tools
    fabric_iq_mcp_url: str | None
    fabric_iq_connection_id: str | None
    fabric_iq_token_scope: str
    work_iq_mcp_url: str | None
    work_iq_connection_id: str | None
    work_iq_token_scope: str
    # fallback model endpoints
    azure_openai_endpoint: str | None
    openai_base_url: str | None
    openai_api_key: str | None
    # observability
    tracing: str  # "auto" | "foundry" | "console" | "off"
    appinsights_connection_string: str | None
    enable_sensitive_data: bool
    # stage behaviour
    demo_today: date
    run_timeout_seconds: int

    @property
    def is_mock(self) -> bool:
        return self.demo_mode == "mock"

    @property
    def fabric_iq_is_mock(self) -> bool:
        return self.fabric_iq_mode == "mock"

    @property
    def work_iq_is_mock(self) -> bool:
        return self.work_iq_mode == "mock"


@cache
def get_settings() -> Settings:
    mode = (_env("DEMO_MODE", "mock") or "mock").lower()
    if mode not in ("mock", "live"):
        raise ConfigError(f"DEMO_MODE must be 'mock' or 'live', not '{mode}'.")

    default_model = _env("FOUNDRY_MODEL", _env("AZURE_AI_MODEL_DEPLOYMENT_NAME"))  # the latter is set when hosted
    models = Models(
        orchestrator=_env("ORCHESTRATOR_MODEL", default_model) or "",
        data_analyst=_env("DATA_ANALYST_MODEL", default_model) or "",
        data_analyst_alt=_env("DATA_ANALYST_MODEL_ALT"),
        work_context=_env("WORK_CONTEXT_MODEL", default_model) or "",
        action=_env("ACTION_MODEL", default_model) or "",
        eval_judge=_env("EVAL_JUDGE_MODEL", _env("ORCHESTRATOR_MODEL", default_model)) or "",
    )
    if not all([models.orchestrator, models.data_analyst, models.work_context, models.action]):
        raise ConfigError("Set FOUNDRY_MODEL (or ORCHESTRATOR_MODEL, DATA_ANALYST_MODEL, WORK_CONTEXT_MODEL, "
                          "ACTION_MODEL) in .env to your model deployment names.")

    provider = (_env("MODEL_PROVIDER", "foundry") or "foundry").lower()
    endpoint = _env("FOUNDRY_PROJECT_ENDPOINT")
    if provider == "foundry" and not endpoint:
        raise ConfigError("Set FOUNDRY_PROJECT_ENDPOINT in .env "
                          "(https://<account>.services.ai.azure.com/api/projects/<project>).")

    temperature = _env("AGENT_TEMPERATURE", "0.1")

    source_modes = {name: (_env(f"{name}_MODE", mode) or mode).lower() for name in ("FABRIC_IQ", "WORK_IQ")}
    for name, value in source_modes.items():
        if value not in ("mock", "live"):
            raise ConfigError(f"{name}_MODE must be 'mock' or 'live', not '{value}'.")
    # The synthetic business data is built around a fixed date; real data uses today.
    today = _env("DEMO_TODAY") or (MOCK_DEMO_TODAY if source_modes["FABRIC_IQ"] == "mock" else date.today().isoformat())

    return Settings(
        demo_mode=mode,
        fabric_iq_mode=source_modes["FABRIC_IQ"],
        work_iq_mode=source_modes["WORK_IQ"],
        data_analyst_foundry_agent=_env("DATA_ANALYST_FOUNDRY_AGENT"),
        work_context_foundry_agent=_env("WORK_CONTEXT_FOUNDRY_AGENT"),
        model_provider=provider,
        foundry_project_endpoint=endpoint,
        models=models,
        temperature=float(temperature) if temperature not in (None, "none") else None,
        fabric_iq_mcp_url=_env("FABRIC_IQ_MCP_URL"),
        fabric_iq_connection_id=_env("FABRIC_IQ_CONNECTION_ID"),
        fabric_iq_token_scope=_env("FABRIC_IQ_TOKEN_SCOPE", "https://ai.azure.com/.default") or "",
        work_iq_mcp_url=_env("WORK_IQ_MCP_URL"),
        work_iq_connection_id=_env("WORK_IQ_CONNECTION_ID"),
        work_iq_token_scope=_env("WORK_IQ_TOKEN_SCOPE", "https://ai.azure.com/.default") or "",
        azure_openai_endpoint=_env("AZURE_OPENAI_ENDPOINT"),
        openai_base_url=_env("OPENAI_BASE_URL"),
        openai_api_key=_env("OPENAI_API_KEY"),
        tracing=(_env("TRACING", "auto") or "auto").lower(),
        appinsights_connection_string=_env("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        enable_sensitive_data=(_env("ENABLE_SENSITIVE_DATA", "true") or "").lower() == "true",
        demo_today=date.fromisoformat(today),
        run_timeout_seconds=int(_env("RUN_TIMEOUT_SECONDS", "120") or 120),
    )
