"""The thermostat card as a dashboard resource."""

from __future__ import annotations

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.ai_heating_assistant.panel import CARD_PATH, async_set_card_resource


async def _urls(hass: HomeAssistant) -> list[str]:
    return [item["url"] for item in hass.data[LOVELACE_DATA].resources.async_items()]


async def test_card_resource_is_added_updated_and_removed(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "lovelace", {})
    resources = hass.data[LOVELACE_DATA].resources
    await resources.async_load()
    resources.loaded = True
    await resources.async_create_item({"res_type": "module", "url": "/local/other.js"})

    await async_set_card_resource(hass, f"{CARD_PATH}?v=1")
    assert await _urls(hass) == ["/local/other.js", f"{CARD_PATH}?v=1"]

    # a new version replaces the entry instead of adding a second one
    await async_set_card_resource(hass, f"{CARD_PATH}?v=2")
    assert await _urls(hass) == ["/local/other.js", f"{CARD_PATH}?v=2"]
    assert resources.async_items()[1]["type"] == "module"

    await async_set_card_resource(hass, None)
    assert await _urls(hass) == ["/local/other.js"]


async def test_card_resource_without_lovelace(hass: HomeAssistant) -> None:
    await async_set_card_resource(hass, f"{CARD_PATH}?v=1")  # nothing to do, no error
