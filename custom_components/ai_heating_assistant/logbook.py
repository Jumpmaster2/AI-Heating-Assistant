"""Describe logbook events of AI Heating Assistant."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LazyEventPartialState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, EVENT_LOGBOOK, NAME


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None
    ],
) -> None:
    """Describe logbook events."""

    @callback
    def describe(event: LazyEventPartialState) -> dict[str, Any]:
        data = event.data
        result = {
            LOGBOOK_ENTRY_NAME: data.get("name", NAME),
            LOGBOOK_ENTRY_MESSAGE: data.get("message", ""),
        }
        if entity_id := data.get(ATTR_ENTITY_ID):
            result[LOGBOOK_ENTRY_ENTITY_ID] = entity_id
        return result

    async_describe_event(DOMAIN, EVENT_LOGBOOK, describe)
