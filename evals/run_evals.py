"""Demo 3 · Evaluate the Account Risk Agent, then compare two models for the Data Analyst.

    uv run python evals/run_evals.py              # 15 questions + Foundry evaluators + model comparison
    uv run python evals/run_evals.py --quick      # 6 questions (stage)
    uv run python evals/run_evals.py --local-only # no Foundry evaluators (offline fallback)

1. Run the agent over evals/dataset.jsonl (a fresh session per question).
2. Local checks: expected facts in the answer, expected tools called.
3. Foundry evaluators (groundedness, task adherence, tool-call accuracy, intent resolution);
   results land in the Foundry portal (the link is printed).
4. Same data questions on DATA_ANALYST_MODEL and DATA_ANALYST_MODEL_ALT: quality vs latency vs cost.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_framework import Agent, AgentResponse, EvalItem, FunctionTool, Message
from agent_framework.foundry import FoundryEvals

from account_risk import console as ui
from account_risk.agents import create_data_analyst, create_risk_agent
from account_risk.app import friendly_error, setup_logging
from account_risk.clients import chat_client
from account_risk.config import ROOT, Settings, get_settings
from account_risk.telemetry import setup_telemetry, tracer

HERE = Path(__file__).parent
# Two Foundry evaluation runs. Groundedness runs without tool definitions: with agent-framework-foundry 1.15
# the service rejects tool_definitions that the groundedness data mapping does not use (EvalValidationFailed).
FOUNDRY_SUITES = {
    "Agent behaviour": ([FoundryEvals.TASK_ADHERENCE, FoundryEvals.TOOL_CALL_ACCURACY, FoundryEvals.INTENT_RESOLUTION], True),
    "Groundedness": ([FoundryEvals.GROUNDEDNESS], False),
}


@dataclass
class Run:
    case: dict[str, Any]
    response: AgentResponse | None
    seconds: float
    tools: list[FunctionTool] = field(default_factory=list)
    error: str | None = None

    @property
    def called(self) -> set[str]:
        if not self.response:
            return set()
        return {c.name for m in self.response.messages for c in m.contents if c.type == "function_call" and c.name}

    @property
    def facts(self) -> float:
        """Share of expected facts found in the answer (each fact is a list of accepted spellings)."""
        text = (self.response.text if self.response else "").lower()
        groups = self.case["expected_facts"]
        return sum(any(option.lower() in text for option in group) for group in groups) / len(groups)

    @property
    def tools_ok(self) -> bool:
        return set(self.case["expected_tools"]) <= self.called

    def usage(self, key: str) -> int:
        return ((self.response.usage_details or {}).get(key) or 0) if self.response else 0


# ============================================================================ run the agent


async def run_cases(cases: list[dict[str, Any]], make_agent: Callable[[], Agent], timeout: int,
                    workers: int = 4) -> list[Run]:
    """Each worker owns one agent (and its MCP connections); questions are spread over the workers."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    for case in cases:
        queue.put_nowait(case)
    runs: list[Run] = []

    async def worker() -> None:
        async with make_agent() as agent:
            tools = [f for mcp in agent.mcp_tools for f in mcp.functions]
            while not queue.empty():
                case = queue.get_nowait()
                start = time.perf_counter()
                try:
                    response = await asyncio.wait_for(agent.run(case["query"], session=agent.create_session()), timeout)
                    runs.append(Run(case, response, time.perf_counter() - start, tools))
                except Exception as e:  # noqa: BLE001 - one bad question must not stop the eval
                    runs.append(Run(case, None, time.perf_counter() - start, tools, error=friendly_error(e)[0]))
                ui.info(f"   {'✓' if runs[-1].response else '✘'} {case['id']} · {case['query'][:70]}")

    await asyncio.gather(*(worker() for _ in range(min(workers, len(cases)))))
    return sorted(runs, key=lambda r: r.case["id"])


def show_local_results(runs: list[Run]) -> None:
    rows = [[r.case["id"], r.case["category"], f"{r.facts:.0%}", "✔" if r.tools_ok else "✘", f"{r.seconds:.1f}s",
             r.error or ", ".join(sorted(r.called))] for r in runs]
    ui.table("Local checks", ["ID", "Category", "Facts", "Tools", "Latency", "Tools called / error"], rows)
    ok = [r for r in runs if r.response]
    ui.success(f"Facts found: {sum(r.facts for r in ok) / max(len(ok), 1):.0%} · "
               f"expected tools used: {sum(r.tools_ok for r in ok)}/{len(ok)} · errors: {len(runs) - len(ok)}")


# ============================================================================ Foundry evaluators


def _tool_results(response: AgentResponse) -> str:
    """What the tools returned: the context the answer must be grounded in."""
    return "\n".join(str(c.result) for m in response.messages for c in m.contents if c.type == "function_result")


async def foundry_evaluation(settings: Settings, runs: list[Run]) -> None:
    judge = chat_client(settings, settings.models.eval_judge)

    async def run_suite(name: str, evaluators: list[str], with_tools: bool) -> Any:
        items = [
            EvalItem(conversation=[Message("user", [r.case["query"]]), *r.response.messages],
                     tools=(r.tools or None) if with_tools else None, context=_tool_results(r.response) or None)
            for r in runs if r.response
        ]
        evals = FoundryEvals(client=judge, evaluators=evaluators, timeout=240, poll_interval=3)
        return await evals.evaluate(items, eval_name=f"Douro Cellars · Account Risk Agent · {name}")

    with ui.working("risk_agent", "Foundry is scoring the answers…"):
        results = await asyncio.gather(*(run_suite(name, ev, tools) for name, (ev, tools) in FOUNDRY_SUITES.items()))

    rows = []
    for result in results:
        for evaluator, counts in sorted(result.per_evaluator.items()):
            rows.append([evaluator, str(counts.get("passed", 0)), str(counts.get("failed", 0)),
                         str(counts.get("errored", 0))])
    ui.table("Foundry evaluators", ["Evaluator", "Passed", "Failed", "Errored"], rows)
    for name, result in zip(FOUNDRY_SUITES, results, strict=True):
        if result.error:
            ui.warn(f"{name}: {result.status} · {result.error}")
        if result.report_url:
            ui.success(f"{name} · Foundry portal: {result.report_url}")
        elif not result.error:
            ui.warn(f"{name}: {result.status} (no portal link yet; check Foundry → Evaluations)")


# ============================================================================ model comparison


def _prices() -> dict[str, list[float]]:
    return json.loads((HERE / "model_prices.json").read_text())


async def compare_models(settings: Settings, cases: list[dict[str, Any]]) -> list[list[str]]:
    models = [settings.models.data_analyst, settings.models.data_analyst_alt]
    data_cases = [c for c in cases if c["data_only"]]
    prices = _prices()
    rows = []
    for model in models:
        if not model:
            continue
        runs = await run_cases(data_cases, lambda m=model: create_data_analyst(settings, model=m), settings.run_timeout_seconds)
        ok = [r for r in runs if r.response] or runs
        tokens_in = sum(r.usage("input_token_count") for r in ok) / len(ok)
        tokens_out = sum(r.usage("output_token_count") for r in ok) / len(ok)
        price = prices.get(model)
        cost = f"${(tokens_in * price[0] + tokens_out * price[1]) / 1_000_000 * 1000:.2f}" if price else "add price"
        rows.append([model, f"{sum(r.facts for r in ok) / len(ok):.0%}", f"{sum(r.seconds for r in ok) / len(ok):.1f}s",
                     f"{tokens_in:,.0f} / {tokens_out:,.0f}", cost, str(len(runs) - len(ok))])
    return rows


# ============================================================================ main


async def main(args: argparse.Namespace) -> None:
    settings = get_settings()
    tracing = setup_telemetry(settings)
    cases = [json.loads(line) for line in (HERE / "dataset.jsonl").read_text().splitlines() if line.strip()]
    if args.quick:
        cases = [c for c in cases if c["id"] in {"q01", "q02", "q04", "q05", "q09", "q12"}]

    ui.banner("Demo 3 · Evals & model comparison",
              f"mode: {settings.demo_mode} · {len(cases)} questions · judge: {settings.models.eval_judge} · tracing: {tracing}")
    with tracer.start_as_current_span("account_risk.evals"):
        ui.step(1, f"Run the Account Risk Agent on {len(cases)} test questions")
        runs = await run_cases(cases, lambda: create_risk_agent(settings), settings.run_timeout_seconds)
        show_local_results(runs)

        ui.step(2, "Foundry evaluators + model comparison (in parallel)")
        use_foundry = not args.local_only and settings.model_provider == "foundry"
        evaluation, comparison = await asyncio.gather(
            foundry_evaluation(settings, runs) if use_foundry else _nothing(),
            compare_models(settings, cases) if not args.no_compare else _nothing(),
            return_exceptions=True,
        )

    if isinstance(evaluation, BaseException):
        logging.getLogger("account_risk").error("Foundry evaluation failed", exc_info=evaluation)
        ui.warn(f"Lost contact with the Foundry evaluation ({friendly_error(evaluation)[0]}). It keeps running in "
                "Foundry: open Evaluations → 'Douro Cellars · Account Risk Agent'.")
    if isinstance(comparison, BaseException):
        logging.getLogger("account_risk").error("Model comparison failed", exc_info=comparison)
        ui.warn(f"Model comparison failed: {friendly_error(comparison)[0]}")
    elif comparison:
        ui.table("Data Analyst · quality vs latency vs cost",
                 ["Model", "Facts", "Latency", "Tokens in/out", "Cost / 1k questions", "Errors"], comparison)
    _save(runs)


async def _nothing() -> None:
    return None


def _save(runs: list[Run]) -> None:
    out = ROOT / "evals" / "results"
    out.mkdir(exist_ok=True)
    path = out / f"run-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps([{"id": r.case["id"], "query": r.case["query"], "answer": r.response.text if r.response else None,
                                 "facts": r.facts, "tools_ok": r.tools_ok, "seconds": round(r.seconds, 2),
                                 "error": r.error} for r in runs], indent=2, ensure_ascii=False))
    ui.info(f"Answers saved to {path.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="6 questions instead of 15")
    parser.add_argument("--local-only", action="store_true", help="skip the Foundry evaluators")
    parser.add_argument("--no-compare", action="store_true", help="skip the model comparison")
    parsed = parser.parse_args()
    setup_logging(verbose=False)
    ui.configure(verbose=False, pause=False, show_tools=False)
    try:
        asyncio.run(main(parsed))
    except KeyboardInterrupt:
        ui.info("Stopped.")
    except Exception as e:  # noqa: BLE001
        logging.getLogger("account_risk").exception("Evals failed")
        message, hint = friendly_error(e)
        ui.error(message, hint)
        sys.exit(1)
