"""A scripted chat client so the agents and the workflow can be tested without a model or network.

Real MCP servers and real Agent Framework plumbing; only the LLM is replaced by a few rules:
call the useful tools once per turn, then summarise the tool results as the answer.
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncIterable, Mapping, Sequence
from typing import Any, ClassVar

from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
    ResponseStream,
)

_ids = itertools.count(1)

SCRIPTED_CALLS: dict[str, list[tuple[str, dict[str, Any]]]] = {
    "search_ontology": [("search_ontology", {"question": "late shipments, top SKU stock and order trend for key accounts"})],
    "retrieve": [("retrieve", {"query": "Zava Lisboa escalation"})],
    "send_email": [
        ("send_email", {"to": "sofia.almeida@zava-lisboa.example", "subject": "Recovery plan", "body": "Dear Sofia, ..."}),
        ("create_follow_up_task", {"title": "Book express freight", "owner": "Ana Ribeiro", "due_date": "2026-10-19"}),
    ],
}


class _ScriptedClient(BaseChatClient[Any]):
    OTEL_PROVIDER_NAME: ClassVar[str] = "scripted"

    def _inner_get_response(self, *, messages: Sequence[Message], stream: bool = False,
                            options: Mapping[str, Any], **kwargs: Any) -> Any:
        response = ChatResponse(messages=[self._reply(messages, options)], model="scripted",
                                response_id=f"resp-{next(_ids)}")
        if not stream:
            async def _done() -> ChatResponse:
                return response
            return _done()

        async def _stream() -> AsyncIterable[ChatResponseUpdate]:
            yield ChatResponseUpdate(contents=list(response.messages[0].contents), role="assistant",
                                     response_id=response.response_id, model="scripted")

        return ResponseStream(_stream(), finalizer=lambda _updates: response)

    def _reply(self, messages: Sequence[Message], options: Mapping[str, Any]) -> Message:
        tool_names = {getattr(t, "name", None) for t in options.get("tools") or []}
        last_question = max((i for i, m in enumerate(messages) if m.role == "user" and m.text), default=0)
        turn = messages[last_question:]  # only look at the current turn, not the remembered history
        already_called = any(c.type == "function_call" for m in turn for c in m.contents)
        results = [str(c.result) for m in turn for c in m.contents if c.type == "function_result"]
        rejected = any(c.type == "function_approval_response" and not c.approved for m in turn for c in m.contents)

        ScriptedChatClient.seen.append([m.text for m in messages])
        if not already_called and tool_names & SCRIPTED_CALLS.keys():
            contents: list[Content] = [Content.from_text("## Risk score\n80 — High\n")] if "send_email" in tool_names else []
            for trigger, calls in SCRIPTED_CALLS.items():
                if trigger in tool_names:
                    contents += [Content.from_function_call(call_id=f"call-{next(_ids)}", name=name, arguments=args)
                                 for name, args in calls]
            return Message("assistant", contents)
        if rejected:
            return Message("assistant", ["Not sent — tell me what to change."])
        if results:
            return Message("assistant", ["Findings: " + " | ".join(r[:400] for r in results)])
        return Message("assistant", ["1. Data Analyst: check Zava Lisboa. 2. Work Context: check emails. 3. Action: brief."])


class ScriptedChatClient(FunctionInvocationLayer[Any], ChatMiddlewareLayer[Any], _ScriptedClient):
    """Scripted client with the same layers as the real clients (tool calling, approvals, middleware)."""

    seen: ClassVar[list[list[str]]] = []  # the message texts of every model call, for memory assertions


def scripted_chat_client(_settings: Any, _model: str) -> ScriptedChatClient:
    return ScriptedChatClient()

