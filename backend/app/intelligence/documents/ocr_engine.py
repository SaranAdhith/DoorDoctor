"""The single OCR boundary. The only file that knows an OCR engine exists.

The same contract as `services/llm_client.py`, for the same reasons:

1. **`extract()` never raises.** No engine configured, server off, timeout,
   500, a body this client can't read, an empty transcription: every one is
   `None`, and the worker has exactly one fallback path — the page becomes
   "needs manual entry".
2. **Nothing about the page or the transcription is ever logged.** A page here
   is a named person's prescription. Logs get the failure reason and the
   elapsed milliseconds.

**Engine: Chandra OCR 2**, served behind any OpenAI-compatible
`/chat/completions` endpoint that accepts an image — `llama.cpp`'s
`llama-server` with a GGUF quantisation on the founder's laptop today, vLLM on a
GPU server later. Moving between them is a `CHANDRA_BASE_URL` change, not code.

Tests never reach a real engine: `OCR_ENGINE=none` under the suite, and the
tests that exercise OCR install `FakeOcrEngine` with `use_engine()`.
"""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from ...config import settings
from ...core.intelligence import OCR_MAX_TOKENS, OCR_PROMPT

logger = logging.getLogger("doordoctor.ocr")


@dataclass(frozen=True)
class OcrResult:
    #: Chandra emits layout-preserving markdown (or HTML for complex tables);
    #: stored as given. Turning it into facts is Stage 2's job, not this one's.
    text: str
    engine: str
    elapsed_ms: int


class OcrEngine(Protocol):
    name: str

    def extract(self, image: bytes, *, content_type: str) -> OcrResult | None:
        """One page image in, its text out — or `None`. Must never raise."""
        ...


class NullEngine:
    """No OCR configured. Every scanned page becomes 'needs manual entry'."""

    name = "none"

    def extract(self, image: bytes, *, content_type: str) -> OcrResult | None:
        return None


class FakeOcrEngine:
    """Deterministic stand-in for tests and offline demos.

    Returns `text` for every page, or `None` when built with `text=None` to act
    out an engine that is down.
    """

    name = "fake-ocr"

    def __init__(self, text: str | None = "FAKE OCR TEXT") -> None:
        self.text = text
        self.calls = 0

    def extract(self, image: bytes, *, content_type: str) -> OcrResult | None:
        self.calls += 1
        if self.text is None:
            return None
        return OcrResult(text=self.text, engine=self.name, elapsed_ms=0)


class ChandraEngine:
    """Chandra OCR 2 behind an OpenAI-compatible vision endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.name = model[:60]

    def _payload(self, image: bytes, content_type: str) -> dict[str, Any]:
        encoded = base64.b64encode(image).decode("ascii")
        return {
            "model": self.model,
            "temperature": 0,
            "max_tokens": OCR_MAX_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                        {"type": "text", "text": OCR_PROMPT},
                    ],
                }
            ],
        }

    def extract(self, image: bytes, *, content_type: str) -> OcrResult | None:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        started = time.monotonic()
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=self._payload(image, content_type),
                headers=headers,
                timeout=self.timeout,
            )
        except httpx.TimeoutException:
            logger.info("OCR call timed out after %.0fms", (time.monotonic() - started) * 1000)
            return None
        except httpx.HTTPError as exc:
            # Only the type: a message can echo the URL or the request.
            logger.info("OCR call failed: %s", type(exc).__name__)
            return None
        except Exception as exc:  # noqa: BLE001 — the contract is "never raises"
            logger.info("OCR call failed unexpectedly: %s", type(exc).__name__)
            return None

        elapsed_ms = int((time.monotonic() - started) * 1000)
        if response.status_code != 200:
            logger.info("OCR call returned HTTP %d", response.status_code)
            return None

        try:
            text = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            logger.info("OCR call returned a body this client could not read")
            return None

        if not isinstance(text, str) or not text.strip():
            logger.info("OCR call returned no text in %dms", elapsed_ms)
            return None

        logger.info("OCR call succeeded in %dms", elapsed_ms)
        return OcrResult(text=text.strip(), engine=self.name, elapsed_ms=elapsed_ms)


# --- selection --------------------------------------------------------------

_override: OcrEngine | None = None


def use_engine(engine: OcrEngine | None) -> None:
    """Install an engine for this process (tests, demos). `None` restores config."""
    global _override
    _override = engine


def get_engine() -> OcrEngine:
    """The engine the configuration asks for. Read per call, so a changed setting
    is obeyed without a restart and a test's override is never cached around."""
    if _override is not None:
        return _override

    kind = settings.ocr_engine.strip().lower()
    if kind in {"chandra_local", "chandra_api"} and settings.chandra_base_url.strip():
        return ChandraEngine(
            base_url=settings.chandra_base_url,
            model=settings.chandra_model,
            api_key=settings.chandra_api_key,
            timeout=settings.ocr_timeout_s,
        )
    if kind not in {"", "none"}:
        logger.info("Unknown or incomplete OCR_ENGINE %r; OCR is off", kind)
    return NullEngine()
