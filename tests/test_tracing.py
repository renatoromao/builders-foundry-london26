"""Spans need meaningful names: `<agent>.<tool>` next to the framework's invoke_agent / execute_tool spans."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from account_risk.runner import run_workflow
from account_risk.workflow import build_workflow

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)


async def test_workflow_trace_has_business_named_tool_spans(settings, scripted_models, approve):
    approve(True)
    async with build_workflow(settings).running() as app:
        await run_workflow(app.workflow, "Prepare my QBR with Zava Lisboa", timeout=60)
    names = {span.name for span in exporter.get_finished_spans()}
    assert {"data_analyst.search_ontology", "work_context.retrieve", "action.send_email"} <= names
    assert any(name.startswith("invoke_agent") for name in names)
    assert any(name.startswith("workflow") for name in names)
