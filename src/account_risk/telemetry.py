"""OpenTelemetry → Application Insights → Foundry tracing.

Agent Framework is instrumented out of the box (invoke_agent / chat / execute_tool / workflow spans).
We only choose where traces go, and add business-named tool spans such as `data_analyst.search_ontology`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from agent_framework import FunctionInvocationContext, function_middleware
from agent_framework.observability import create_resource, enable_sensitive_telemetry, get_tracer
from opentelemetry.trace import Span, format_trace_id

from account_risk import console as ui
from account_risk.config import Settings

log = logging.getLogger(__name__)
SERVICE_NAME = "douro-cellars-account-risk"
tracer = get_tracer("account_risk")


def setup_telemetry(settings: Settings) -> str:
    """Configure exporters once per process. Returns a short description for the banner.

    TRACING=auto     Application Insights if APPLICATIONINSIGHTS_CONNECTION_STRING is set
    TRACING=foundry  ask the Foundry project for its connected Application Insights
    TRACING=otlp     local OTLP/HTTP viewer (AI Toolkit for VS Code, Aspire Dashboard) — the offline fallback
    TRACING=off
    """
    if settings.tracing == "off":
        return "off"
    if settings.tracing == "otlp":
        from agent_framework.observability import configure_otel_providers

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        configure_otel_providers(service_name=SERVICE_NAME, otlp_endpoint=endpoint, otlp_protocol="http",
                                 enable_sensitive_data=settings.enable_sensitive_data)
        return f"OTLP → {endpoint}"
    connection_string = settings.appinsights_connection_string
    if not connection_string and settings.tracing == "foundry":
        connection_string = _connection_string_from_foundry(settings)
    if not connection_string:
        return "off (set APPLICATIONINSIGHTS_CONNECTION_STRING or TRACING=foundry)"

    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=connection_string, resource=create_resource(service_name=SERVICE_NAME))
    if settings.enable_sensitive_data:
        enable_sensitive_telemetry()  # prompts, tool arguments and results show up in the trace
    return "Application Insights → Foundry"


def _connection_string_from_foundry(settings: Settings) -> str | None:
    """Ask the Foundry project for its connected Application Insights resource."""
    from azure.ai.projects import AIProjectClient

    from account_risk.clients import credential

    try:
        with AIProjectClient(endpoint=settings.foundry_project_endpoint, credential=credential()) as project:
            return project.telemetry.get_application_insights_connection_string()
    except Exception:  # noqa: BLE001 - tracing must never break the demo
        log.exception("Could not get the Application Insights connection string from Foundry")
        return None


def trace_id(span: Span) -> str | None:
    """The trace id to look up in Foundry / Application Insights (None when tracing is off)."""
    return format_trace_id(span.get_span_context().trace_id) if span.is_recording() else None


def observe_tools(agent: str) -> Callable[[FunctionInvocationContext, Callable[[], Awaitable[None]]], Awaitable[None]]:
    """Function middleware: one span per tool call named `<agent>.<tool>`, plus a line on the console."""

    @function_middleware
    async def _observe(context: FunctionInvocationContext, call_next: Callable[[], Awaitable[None]]) -> None:
        tool = context.function.name
        arguments = _as_dict(context.arguments)
        with tracer.start_as_current_span(f"{agent}.{tool}") as span:
            span.set_attribute("account_risk.agent", agent)
            span.set_attribute("account_risk.source", ui.SOURCES.get(tool, "tool"))
            span.set_attribute("gen_ai.tool.name", tool)
            ui.tool_call(agent, tool, arguments)
            await call_next()
            ui.tool_result(agent, tool, context.result)

    return _observe


def _as_dict(arguments: Any) -> dict[str, Any]:
    if hasattr(arguments, "model_dump"):
        return arguments.model_dump()
    return dict(arguments) if isinstance(arguments, Mapping) else {"value": arguments}
