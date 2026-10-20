"""Thin wrapper around the official Anthropic SDK.

The API key is only handed to the SDK client. It is never logged and never
part of an error message produced here.
"""

from __future__ import annotations

import json
from functools import partial
from typing import Any

import anthropic
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import FALLBACK_BETA, FALLBACK_MODELS, LOGGER

REQUEST_TIMEOUT = 120.0  # s at least for one answer
MAX_REQUEST_TIMEOUT = 600.0
OUTPUT_TOKENS_PER_S = 30  # slow end of the output speed, thinking included


def request_timeout(max_tokens: int) -> float:
    """Seconds to wait for an answer of up to max_tokens tokens."""
    return min(MAX_REQUEST_TIMEOUT, max(REQUEST_TIMEOUT, max_tokens / OUTPUT_TOKENS_PER_S))


class AiError(Exception):
    """A failed AI call. ``usage`` holds token counts if tokens were consumed."""

    def __init__(self, message: str, usage: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.usage = usage or {}


class AiAuthError(AiError):
    """The API key was rejected."""


def _usage(message: Any) -> dict[str, Any]:
    usage = getattr(message, "usage", None)
    if usage is None:
        return {}
    try:
        return usage.model_dump(exclude_none=True)
    except AttributeError:
        return {}


class ClaudeClient:
    """Structured JSON calls to Claude."""

    def __init__(
        self, client: anthropic.AsyncAnthropic, model: str, effort: str, *, owned: bool = False
    ) -> None:
        self._client = client
        self._owned = owned  # own HTTP client (not the shared one of Home Assistant)
        self.model = model
        self.effort = effort
        self.served_model: str | None = None  # model that answered the last request

    @classmethod
    async def create(
        cls, hass: HomeAssistant, api_key: str, model: str, effort: str
    ) -> ClaudeClient:
        """Create the SDK client outside the event loop (it loads certificates).

        The manifest asks for at least the SDK version of Home Assistant's own
        Anthropic integration (hassfest forbids pinning a core dependency), which
        accepts the shared httpx client. Should a newer version reject it (SDK 1.x
        requires httpx2), the SDK creates its own client, which ``close`` releases.
        """
        try:
            client = await hass.async_add_executor_job(
                partial(
                    anthropic.AsyncAnthropic,
                    api_key=api_key,
                    http_client=get_async_client(hass),
                    max_retries=2,
                )
            )
        except TypeError:
            client = await hass.async_add_executor_job(
                partial(anthropic.AsyncAnthropic, api_key=api_key, max_retries=2)
            )
            return cls(client, model, effort, owned=True)
        return cls(client, model, effort)

    async def close(self) -> None:
        """Release an own HTTP client; the shared one stays open for others."""
        if self._owned:
            await self._client.close()

    async def validate(self) -> None:
        """Check the API key with a free request."""
        try:
            await self._client.models.list(limit=1, timeout=30)
        except anthropic.AuthenticationError as err:
            raise AiAuthError("authentication failed") from err
        except anthropic.APIConnectionError as err:
            raise AiError("cannot connect") from err
        except anthropic.APIStatusError as err:
            raise AiError(f"API error {err.status_code}") from err

    async def structured(
        self, system: str, user: str, schema: dict[str, Any], max_tokens: int
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Send one request and return (parsed JSON, usage)."""
        output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": schema}}
        if self.effort and self.effort != "auto":
            output_config["effort"] = self.effort
        extra_headers: dict[str, str] = {}
        extra_body: dict[str, Any] = {}
        self.served_model = None
        if self.model in FALLBACK_MODELS:
            extra_headers["anthropic-beta"] = FALLBACK_BETA
            extra_body["fallbacks"] = "default"
        try:
            message = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config=output_config,  # type: ignore[arg-type]
                extra_headers=extra_headers or None,
                extra_body=extra_body or None,
                # A long answer (up to max_tokens) must be able to arrive.
                timeout=request_timeout(max_tokens),
            )
        except anthropic.AuthenticationError as err:
            raise AiAuthError("authentication failed") from err
        except anthropic.RateLimitError as err:
            raise AiError("rate limited") from err
        except anthropic.APIConnectionError as err:
            raise AiError("cannot connect or timeout") from err
        except anthropic.APIStatusError as err:
            raise AiError(f"API error {err.status_code}") from err

        usage = _usage(message)
        served = getattr(message, "model", None)
        self.served_model = served if isinstance(served, str) else None
        stop = getattr(message, "stop_reason", None)
        if stop == "refusal":
            raise AiError("request refused by the model", usage)
        if stop == "max_tokens":
            raise AiError("answer truncated (max tokens)", usage)
        text = next((b.text for b in message.content if getattr(b, "type", None) == "text"), None)
        if not text:
            raise AiError("empty answer", usage)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            raise AiError("answer is not valid JSON", usage) from err
        LOGGER.debug("AI answer (%s): %s", self.model, data)
        return data, usage
