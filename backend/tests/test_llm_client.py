"""The LLM boundary (Phases 6 and 7).

`complete()` has one contract that everything downstream depends on: it returns
`str | None` and it never raises. Every test here is a way of trying to make it
raise.
"""

import httpx
import pytest

from app.services import llm_client, summary_service


@pytest.fixture
def configured(monkeypatch):
    """Pretend a key is present without ever reaching a network."""
    monkeypatch.setattr(llm_client.settings, "groq_api_key", "test-key", raising=False)
    monkeypatch.setattr(llm_client.settings, "assistant_enabled", True, raising=False)
    return llm_client.settings


def _call() -> str | None:
    return llm_client.complete(system="s", user="u", timeout=2.0)


# --------------------------------------------------------------------------
# The no-key path is the demo path, not an edge case
# --------------------------------------------------------------------------


def test_unavailable_without_a_key():
    assert llm_client.available() is False
    assert _call() is None


def test_unavailable_when_the_assistant_is_switched_off(monkeypatch, configured):
    monkeypatch.setattr(llm_client.settings, "assistant_enabled", False, raising=False)
    assert llm_client.available() is False
    assert _call() is None


def test_no_request_is_made_without_a_key(monkeypatch):
    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("a request was attempted with no API key configured")

    monkeypatch.setattr(llm_client.httpx, "post", explode)
    assert _call() is None


# --------------------------------------------------------------------------
# Every failure mode returns None rather than raising
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    [
        httpx.TimeoutException("timed out"),
        httpx.ConnectError("refused"),
        httpx.ReadError("dropped"),
    ],
)
def test_transport_failures_return_none(monkeypatch, configured, failure):
    monkeypatch.setattr(llm_client.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(failure))
    assert _call() is None


@pytest.mark.parametrize("status_code", [400, 401, 429, 500, 503])
def test_error_statuses_return_none(monkeypatch, configured, status_code):
    monkeypatch.setattr(
        llm_client.httpx,
        "post",
        lambda *a, **k: httpx.Response(status_code, json={"error": "no"}),
    )
    assert _call() is None


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": None}}]},
        {"choices": "not a list"},
    ],
)
def test_malformed_bodies_return_none(monkeypatch, configured, body):
    monkeypatch.setattr(llm_client.httpx, "post", lambda *a, **k: httpx.Response(200, json=body))
    assert _call() is None


def test_non_json_body_returns_none(monkeypatch, configured):
    monkeypatch.setattr(
        llm_client.httpx, "post", lambda *a, **k: httpx.Response(200, text="<html>nope</html>")
    )
    assert _call() is None


def test_a_good_completion_comes_back_trimmed(monkeypatch, configured):
    monkeypatch.setattr(
        llm_client.httpx,
        "post",
        lambda *a, **k: httpx.Response(200, json={"choices": [{"message": {"content": "  hello  "}}]}),
    )
    assert _call() == "hello"


def test_the_request_carries_the_configured_model_and_key(monkeypatch, configured):
    seen: dict = {}

    def capture(url, **kwargs):
        seen["url"] = url
        seen["json"] = kwargs["json"]
        seen["headers"] = kwargs["headers"]
        seen["timeout"] = kwargs["timeout"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm_client.httpx, "post", capture)
    llm_client.complete(system="S", user="U", timeout=3.5, max_tokens=42)

    assert seen["url"].endswith("/chat/completions")
    assert seen["json"]["model"] == llm_client.settings.groq_model
    assert seen["json"]["max_tokens"] == 42
    assert seen["json"]["messages"] == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
    ]
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert seen["timeout"] == 3.5


def test_the_two_timeouts_are_the_agreed_budgets():
    # Recorded in STATE.md as part of the provider contract: 2s for the summary
    # rewrite, 8s for the assistant.
    assert llm_client.SUMMARY_TIMEOUT == 2.0
    assert llm_client.ASSISTANT_TIMEOUT == 8.0


def test_the_prompt_is_never_logged(monkeypatch, configured, caplog):
    """A prompt here contains a named person's readings."""
    secret = "Lakshmi blood pressure 148 over 92"
    monkeypatch.setattr(
        llm_client.httpx, "post", lambda *a, **k: httpx.Response(500, json={"error": "x"})
    )
    with caplog.at_level("DEBUG"):
        llm_client.complete(system=summary_service.SYSTEM_PROMPT, user=secret, timeout=2.0)

    assert secret not in caplog.text
    assert "Lakshmi" not in caplog.text
