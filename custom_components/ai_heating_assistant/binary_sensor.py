"""Binary sensors: heating day and ventilation recommendation."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AiHeatingConfigEntry, HeatingCoordinator
from .entity import AreaEntity, GlobalEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AiHeatingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([HeatingDaySensor(coordinator)])
    for area in coordinator.areas.values():
        async_add_entities(
            [VentilationRecommended(coordinator, area.area_id)], config_subentry_id=area.area_id
        )


class HeatingDaySensor(GlobalEntity, BinarySensorEntity):
    """Is today a heating day?"""

    def __init__(self, coordinator: HeatingCoordinator) -> None:
        super().__init__(coordinator, "heating_day")

    @property
    def is_on(self) -> bool:
        return self.coordinator.heating_day

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        current = self.coordinator.current_day or {}
        return {
            "date": current.get("date"),
            "decided_at": current.get("decided_at"),
            "next_decision": self.coordinator.next_nightly.isoformat(),
            "source": current.get("source"),
            "phase": current.get("phase"),
            "confidence": current.get("confidence"),
            "reason": current.get("reason"),
            "critical_area": current.get("critical_area"),
            "rule": current.get("rule"),
            "override": self.coordinator.day_state.get("override", "auto"),
            "season_active": self.coordinator.season_active,
            "vacation": self.coordinator.vacation,
        }


class VentilationRecommended(AreaEntity, BinarySensorEntity):
    """On when opening the window is recommended."""

    def __init__(self, coordinator: HeatingCoordinator, area_id: str) -> None:
        super().__init__(coordinator, area_id, "ventilation_recommended")

    @property
    def is_on(self) -> bool | None:
        vent = self.area.ventilation
        return None if vent is None else vent.recommended
