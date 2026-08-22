"""The single LLM integration boundary for the whole platform.

Everything the platform sends to a language model goes through `complete()`.
Phase 6's summary rewrite and Phase 7's assistant call the same function with
different timeouts, so there is exactly one place that knows a provider exists.

**Provider: Groq**, using its OpenAI-compatible `/chat/completions` endpoint over
`httpx` — already a dependency, so this file adds none. Any other
OpenAI-compatible provider drops in by changing `GROQ_BASE_URL` and `GROQ_MODEL`.

Two properties matter more than anything else here:

1. **`complete()` never raises.** No key, disabled, timeout, connection refused,
   500, malformed body, empty completion — every one of them returns `None`, so
   every caller has exactly one fallback path rather than an except-list that
   drifts out of date.
2. **Nothing about the prompt or the completion is ever logged.** A prompt in
   this application contains a named person's blood pressure. Logs get the
   failure reason and the elapsed milliseconds, and nothing else.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Final

import httpx

from ..config import settings

logger = logging.getLogger("doordoctor.llm")

# A re-wording task. Creativity is the failure mode, not the goal.
DEFAULT_TEMPERATURE: Final = 0.2

# Timeouts are per-caller because the two callers have genuinely different
# budgets: a summary rewrite blocks a dashboard paint, an assistant reply is a
# thing the user is watching a spinner for.
SUMMARY_TIMEOUT: Final = 2.0
ASSISTANT_TIMEOUT: Final = 8.0


def available() -> bool:
    """Whether a call is worth attempting at all."""
    return settings.llm_configured


def complete(
    *,
    system: str,
    user: str,
    timeout: float,
    max_tokens: int = 400,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str | None:
    """One completion, or `None` if anything at all goes wrong.

    `None` is not an error condition — it is the ordinary case on a laptop with
    no API key, which is the configuration the demo runs in.
    """
    if not available():
        return None

    url = f"{settings.groq_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.groq_model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key.strip()}",
        "Content-Type": "application/json",
    }

    started = time.monotonic()
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    except httpx.TimeoutException:
        logger.info("LLM call timed out after %.0fms", (time.monotonic() - started) * 1000)
        return None
    except httpx.HTTPError as exc:
        # Only the exception *type* is logged. Its message can carry the URL and,
        # with some providers, an echo of the request.
        logger.info("LLM call failed: %s", type(exc).__name__)
        return None

    if response.status_code != 200:
        logger.info("LLM call returned HTTP %d", response.status_code)
        return None

    try:
        body = response.json()
        text = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        logger.info("LLM call returned a body this client could not read")
        return None

    if not isinstance(text, str) or not text.strip():
        return None

    logger.info("LLM call succeeded in %.0fms", (time.monotonic() - started) * 1000)
    return text.strip()
