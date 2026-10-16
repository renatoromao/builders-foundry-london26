"""Entry point: `uv run account-risk <command>`. No raw stack traces on stage — details go to logs/demo.log."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import warnings

from account_risk import console as ui
from account_risk.config import LOG_DIR, ConfigError, Settings, get_settings

log = logging.getLogger("account_risk")


def main() -> None:
    args = _parse_args()
    setup_logging(args.verbose)
    ui.configure(verbose=args.verbose, pause=not args.no_pause)
    try:
        settings = get_settings()
        if args.command == "web":
            from account_risk.web import serve as serve_web

            serve_web(port=args.port)
            return
        if args.command == "devui":
            from account_risk.devui import serve

            serve(settings, port=args.port)
            return
        asyncio.run(_run(args, settings))
    except KeyboardInterrupt:
        ui.info("\nStopped.")
    except ConfigError as e:
        ui.error(str(e), "Edit .env (see .env.example) and run scripts/preflight.py.")
        sys.exit(2)
    except BaseException as e:  # noqa: BLE001 - last line of defence on stage
        log.exception("Demo failed")
        message, hint = friendly_error(e)
        ui.error(message, f"{hint}\n[dim]Full details: logs/demo.log[/]")
        sys.exit(1)


async def _run(args: argparse.Namespace, settings: Settings) -> None:
    from account_risk import demos
    from account_risk.telemetry import setup_telemetry

    tracing = setup_telemetry(settings)
    if args.command == "demo1":
        await demos.demo1(settings, tracing, args.question)
    elif args.command == "demo2":
        await demos.demo2(settings, tracing, args.request)
    elif args.command == "graph":
        from agent_framework import WorkflowViz

        from account_risk.workflow import build_workflow

        mermaid = WorkflowViz(build_workflow(settings).workflow).to_mermaid()
        ui.console.print(mermaid)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="account-risk", description="Douro Cellars Account Risk Agent demos")
    parser.add_argument("--verbose", action="store_true", help="show tool results and framework logs")
    parser.add_argument("--no-pause", action="store_true", help="don't wait for Enter between steps")
    sub = parser.add_subparsers(dest="command", required=True)
    d1 = sub.add_parser("demo1", help="Demo 1 · Fabric IQ + Work IQ Agent")
    d1.add_argument("--question", help="override the first question")
    d2 = sub.add_parser("demo2", help="Demo 2 · Multi-Agent + Human Approval")
    d2.add_argument("--request", help="override the request")
    sub.add_parser("graph", help="print the workflow as a Mermaid diagram")
    web = sub.add_parser("web", help="open the stage UI in the browser (all three demos)")
    web.add_argument("--port", type=int, default=8000)
    dev = sub.add_parser("devui", help="open the agent and the workflow in Agent Framework DevUI")
    dev.add_argument("--port", type=int, default=8090)
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(LOG_DIR / "demo.log", encoding="utf-8")]
    if verbose:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True)
    logging.captureWarnings(True)
    if not verbose:
        warnings.filterwarnings("ignore")


def friendly_error(error: BaseException) -> tuple[str, str]:
    """Turn an exception into one sentence the audience can read, plus what to do next."""
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    name, text = type(error).__name__, str(error).split("\n")[0][:200]
    lowered = f"{name} {text}".lower()
    if "403" in lowered or "access denied" in lowered or "forbidden" in lowered:
        where = "Work IQ" if "workiq" in lowered else "a tool"
        return f"Access denied by {where} (403).", "Check the connection's permissions/consent, or set WORK_IQ_MODE=mock."
    if "unsupported parameter" in lowered:
        return f"The model rejected a parameter: {text}", "Check the *_MODEL names; reasoning models take no temperature."
    if isinstance(error, TimeoutError):
        return "The agent took too long to answer.", "Run the step again, or set RUN_TIMEOUT_SECONDS higher."
    if "credential" in lowered or "authentication" in lowered or "az login" in lowered:
        return "Azure sign-in failed.", "Run `az login` (right tenant) and try again."
    if "deploymentnotfound" in lowered or "notfound" in lowered or "404" in lowered:
        return f"Not found: {text}", "Check the *_MODEL deployment names and FOUNDRY_PROJECT_ENDPOINT in .env."
    if "ratelimit" in lowered or "429" in lowered:
        return "The model is rate limited.", "Wait 10 seconds and try again, or switch to the backup model."
    if "connect" in lowered or "network" in lowered or "dns" in lowered:
        return "Cannot reach the model endpoint.", "Check the network, or switch to the offline fallback (README)."
    return f"{name}: {text}", "Re-run the step; if it fails again use the fallback in the README."


if __name__ == "__main__":
    main()
