"""The SDK client: shared HTTP client of Home Assistant, or an own one closed again."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import anthropic
from homeassistant.core import HomeAssistant

from custom_components.ai_heating_assistant.ai_client import AiError, ClaudeClient

from .conftest import IN_SEASON, make_entry


async def test_shared_http_client_is_used_and_left_open(hass: HomeAssistant) -> None:
    client = await ClaudeClient.create(hass, "sk-test", "claude-opus-5-5", "auto")
    with patch.object(client._client, "close", AsyncMock()) as close:
        await client.close()
    close.assert_not_called()


async def test_own_http_client_is_closed_on_unload(
    hass: HomeAssistant, base_states, freezer
) -> None:
    """An SDK that rejects the shared client (as SDK 1.x does) gets its own; the
    unload closes it, otherwise every reload would leave connections open."""
    real = anthropic.AsyncAnthropic
    created: list[anthropic.AsyncAnthropic] = []

    def sdk(**kwargs):
        if "http_client" in kwargs:
            raise TypeError("http_client must be an httpx2 client")
        created.append(client := real(**kwargs))
        return client

    freezer.move_to(IN_SEASON)
    entry = make_entry(api_key="sk-test")
    entry.add_to_hass(hass)
    with (
        patch("anthropic.AsyncAnthropic", side_effect=sdk),
        patch.object(ClaudeClient, "structured", side_effect=AiError("offline")),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert len(created) == 1 and not created[0].is_closed()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert created[0].is_closed()
