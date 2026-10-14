"""Manual override of today's heating day decision."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AiHeatingConfigEntry, HeatingCoordinator
from .entity import GlobalEntity
from .logic.heating_day import Override

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AiHeatingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HeatingDayOverride(entry.runtime_data)])


class HeatingDayOverride(GlobalEntity, SelectEntity):
    """Automatic, heat today or no heating today (reset with the next decision day)."""

    _attr_options = [o.value for o in Override]

    def __init__(self, coordinator: HeatingCoordinator) -> None:
        super().__init__(coordinator, "heating_day_override")

    @property
    def current_option(self) -> str:
        return str(self.coordinator.day_state.get("override", Override.AUTO))

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_override(option)
