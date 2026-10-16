import pytest

from account_risk import console as ui
from account_risk.config import get_settings

TEST_ENV = {
    "DEMO_MODE": "mock",
    "MODEL_PROVIDER": "foundry",
    "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/test",
    "FOUNDRY_MODEL": "test-model",
    "ORCHESTRATOR_MODEL": "test-model",
    "DATA_ANALYST_MODEL": "test-model",
    "DATA_ANALYST_MODEL_ALT": "test-model-alt",
    "WORK_CONTEXT_MODEL": "test-model",
    "ACTION_MODEL": "test-model",
    "DEMO_TODAY": "2026-10-19",
    "TRACING": "off",
}


@pytest.fixture(autouse=True)
def test_env(monkeypatch, tmp_path):
    """Deterministic settings (ignores the presenter's .env) and a throw-away outbox."""
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    from account_risk.tools import actions

    monkeypatch.setattr(actions, "STATE_DIR", tmp_path)
    monkeypatch.setattr(actions, "OUTBOX", tmp_path / "outbox.jsonl")
    ui.configure(verbose=False, pause=False)
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def scripted_models(monkeypatch):
    """Replace the LLM in every agent with the scripted client from tests/fakes.py."""
    from account_risk.agents import action, data_analyst, orchestrator, risk_agent, work_context
    from tests.fakes import ScriptedChatClient, scripted_chat_client

    ScriptedChatClient.seen.clear()
    for module in (action, data_analyst, orchestrator, risk_agent, work_context):
        monkeypatch.setattr(module, "chat_client", scripted_chat_client)
    return ScriptedChatClient


@pytest.fixture
def tool_calls(monkeypatch):
    """Record every (agent, tool) pair that the console would show."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(ui, "tool_call", lambda agent, tool, *_a, **_k: calls.append((agent, tool)))
    return calls


@pytest.fixture
def approve(monkeypatch):
    """Answer every approval prompt automatically: approve(True) or approve(False)."""
    decisions: list[tuple[str, bool]] = []

    def _set(answer: bool) -> list[tuple[str, bool]]:
        def _approval(agent, tool, arguments):
            decisions.append((tool, answer))
            return answer

        monkeypatch.setattr(ui, "approval", _approval)
        return decisions

    return _set
