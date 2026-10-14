"""Climate entity per heating area (target is stored permanently, no schedules)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_MAX_TARGET, CONF_MIN_TARGET
from .coordinator import AiHeatingConfigEntry, HeatingCoordinator
from .entity import AreaEntity

PARALLEL_UPDATES = 0

# Home Assistant 2026.11 renames the temperature properties to native_*.
_NATIVE = hasattr(ClimateEntity, "native_current_temperature")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AiHeatingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    for area in coordinator.areas.values():
        if area.has_circuit:
            async_add_entities(
                [AreaClimate(coordinator, area.area_id)], config_subentry_id=area.area_id
            )


class AreaClimate(AreaEntity, ClimateEntity):
    """Thermostat of one area."""

    _attr_name = None
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_target_temperature_step = 0.1

    if _NATIVE:
        _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

        @property
        def native_current_temperature(self) -> float | None:
            return self.area.temp

        @property
        def native_target_temperature(self) -> float | None:
            return self.area.target

    else:
        _attr_temperature_unit = UnitOfTemperature.CELSIUS

        @property
        def current_temperature(self) -> float | None:
            return self.area.temp

        @property
        def target_temperature(self) -> float | None:
            return self.area.target

    def __init__(self, coordinator: HeatingCoordinator, area_id: str) -> None:
        super().__init__(coordinator, area_id, "area")
        self._attr_unique_id = f"{area_id}_climate"
        cfg = coordinator.areas[area_id].cfg
        self._attr_min_temp = float(cfg.get(CONF_MIN_TARGET, 16.0))
        self._attr_max_temp = float(cfg.get(CONF_MAX_TARGET, 24.0))

    @property
    def current_humidity(self) -> float | None:
        return self.area.humidity

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if self.area.hvac_on else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        area = self.area
        if area.switch_on:
            return HVACAction.HEATING
        return HVACAction.IDLE if area.hvac_on else HVACAction.OFF

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        area = self.area
        decision = area.decision
        return {
            "status": area.status,
            "effective_target": area.effective_target,
            "heating_day": self.coordinator.heating_day,
            "predicted_temperature": decision.predicted_temp if decision else None,
            "expected_peak": decision.expected_peak if decision else None,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set_target(self.area_id, float(temperature))
        if (mode := kwargs.get("hvac_mode")) is not None:
            await self.async_set_hvac_mode(mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_set_hvac(self.area_id, hvac_mode == HVACMode.HEAT)

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_hvac(self.area_id, True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_hvac(self.area_id, False)
