"""Switch to turn the AI on or off globally."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AiHeatingConfigEntry, HeatingCoordinator
from .entity import GlobalEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AiHeatingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([AiEnabledSwitch(entry.runtime_data)])


class AiEnabledSwitch(GlobalEntity, SwitchEntity):
    """Without AI the local control runs alone with the learned values."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: HeatingCoordinator) -> None:
        super().__init__(coordinator, "ai_enabled")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.ai_configured

    @property
    def is_on(self) -> bool:
        return self.coordinator.ai_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_ai_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_ai_enabled(False)
