"""Stage-friendly console output: big, clear labels for agents and tools. Details only with --verbose."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

console = Console(highlight=False)
_settings = {"verbose": False, "pause": True, "show_tools": True}
# The web UI registers a callback per request; a ContextVar keeps parallel requests apart.
_sink: ContextVar[Any | None] = ContextVar("account_risk_sink", default=None)


def set_sink(callback: Any | None) -> None:
    """Send tool-call events of the current request to `callback(event: dict)` as well (used by the web UI)."""
    _sink.set(callback)

AGENTS = {
    "risk_agent": ("🤖", "Risk Agent", "cyan"),
    "orchestrator": ("🧭", "Orchestrator", "magenta"),
    "data_analyst": ("📊", "Data Analyst", "blue"),
    "work_context": ("💬", "Work Context", "green"),
    "action": ("📝", "Action", "yellow"),
}
SOURCES = {
    "list_ontology_entity_types": "Fabric IQ", "search_ontology": "Fabric IQ",
    "retrieve": "Work IQ", "ask": "Work IQ", "fetch": "Work IQ",
    "send_email": "Outbox", "create_follow_up_task": "Tasks",
}


def configure(*, verbose: bool, pause: bool, show_tools: bool = True) -> None:
    _settings.update(verbose=verbose, pause=pause, show_tools=show_tools)


def is_verbose() -> bool:
    return _settings["verbose"]


def label(agent: str) -> str:
    icon, name, color = AGENTS.get(agent, ("•", agent, "white"))
    return f"[bold {color}]{icon} {name}[/]"


# ---------------------------------------------------------------- structure


def banner(title: str, subtitle: str) -> None:
    console.print(Panel(f"[bold]{title}[/]\n[dim]{subtitle}[/]", border_style="bright_white", padding=(1, 2)))


def step(number: int, text: str) -> None:
    console.print()
    console.rule(f"[bold]Step {number} · {text}[/]", align="left", style="bright_black")


def pause(message: str = "Press Enter to continue") -> None:
    if _settings["pause"]:
        _input(f"[dim]{message}[/]")


def info(text: str) -> None:
    console.print(f"[dim]{text}[/]")


def success(text: str) -> None:
    console.print(f"[bold green]✔ {text}[/]", soft_wrap=True)  # soft_wrap keeps long portal links clickable


def warn(text: str) -> None:
    console.print(f"[bold yellow]⚠ {text}[/]")


def error(text: str, hint: str | None = None) -> None:
    body = f"[bold red]{text}[/]" + (f"\n\n{hint}" if hint else "")
    console.print(Panel(body, title="Something went wrong", border_style="red"))


@contextmanager
def working(agent: str, text: str = "is working…") -> Iterator[None]:
    with console.status(f"{label(agent)} [dim]{text}[/]", spinner="dots"):
        yield


def ask(prompt: str) -> str:
    return _input(f"\n[bold]{prompt}[/]").strip()


def _input(prompt: str) -> str:
    try:
        return Prompt.ask(prompt, default="", show_default=False)
    except EOFError:  # no keyboard attached (rehearsal scripts, CI)
        return ""


# ---------------------------------------------------------------- agents and tools


def source_of(tool: str, server: str | None = None) -> str:
    """Which source a tool belongs to: by tool name (mocks) or by MCP server label (Foundry tools)."""
    label = (server or "").lower()
    if "workiq" in label or "work_iq" in label:
        return "Work IQ"
    if "fabric" in label:
        return "Fabric IQ"
    return SOURCES.get(tool, server or "tool")


def tool_call(agent: str, tool: str, arguments: Any, hosted: bool = False, server: str | None = None) -> None:
    source = source_of(tool, server)
    if callback := _sink.get():
        callback({"type": "tool_call", "agent": agent, "tool": tool, "source": source,
                  "args": _short_args(arguments), "hosted": hosted})
    if not _settings["show_tools"]:
        return
    args = _short_args(arguments)
    where = " [dim](in Foundry)[/]" if hosted else ""
    console.print(f"   🔧 {label(agent)} → [bold]{source}[/] · [bold]{tool}[/]{where} [dim]{args}[/]")


def tool_result(agent: str, tool: str, result: Any) -> None:
    if not is_verbose():
        return
    text = _to_text(result)
    console.print(f"      [dim]↳ {tool}: {text[:300]}{'…' if len(text) > 300 else ''}[/]")


def agent_message(agent: str, markdown: str, title: str | None = None) -> None:
    icon, name, color = AGENTS.get(agent, ("•", agent, "white"))
    console.print(Panel(Markdown(markdown), title=f"{icon} {title or name}", title_align="left",
                        border_style=color, padding=(0, 1)))


def approval(agent: str, tool: str, arguments: Mapping[str, Any]) -> bool:
    """Show what the agent wants to do and ask the account manager to approve or reject it."""
    table = Table.grid(padding=(0, 2))
    for key, value in arguments.items():
        table.add_row(f"[bold]{key}[/]", str(value))
    console.print(Panel(table, title=f"✋ Approval needed · {label(agent)} wants to call [bold]{tool}[/]",
                        title_align="left", border_style="red", padding=(1, 2)))
    try:
        approved = Confirm.ask("[bold]Approve?[/]", default=False)
    except EOFError:
        approved = False
    console.print("[bold green]   ✔ Approved[/]" if approved else "[bold red]   ✘ Rejected — nothing was sent[/]")
    return approved


def code(path: str, title: str) -> None:
    console.print(Panel(Syntax.from_path(path, line_numbers=True, theme="ansi_dark", word_wrap=True),
                        title=title, title_align="left", border_style="bright_black"))


def table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    t = Table(title=title, title_justify="left", header_style="bold", show_lines=False)
    for column in columns:
        t.add_column(column)
    for row in rows:
        t.add_row(*row)
    console.print(t)


# ---------------------------------------------------------------- helpers


def _short_args(arguments: Any) -> str:
    if arguments is None:
        return ""
    if hasattr(arguments, "model_dump"):
        arguments = arguments.model_dump()
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return arguments[:120]
    if isinstance(arguments, Mapping):
        parts = [f"{k}={_clip(v)}" for k, v in arguments.items() if v not in (None, "", [])]
        return " ".join(parts)
    return _clip(arguments)


def _clip(value: Any, limit: int = 90) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = text.replace("\n", " ")
    return repr(text[:limit] + "…") if len(text) > limit else repr(text)


def _to_text(result: Any) -> str:
    if isinstance(result, list):
        return " ".join(_to_text(r) for r in result)
    text = getattr(result, "text", None)
    return text if isinstance(text, str) else str(result)
