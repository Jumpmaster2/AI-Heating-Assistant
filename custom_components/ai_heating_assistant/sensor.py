"""Sensors: status, learned values, ventilation, AI state and costs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_HEAT_METER
from .coordinator import AiHeatingConfigEntry, Area, HeatingCoordinator
from .entity import AreaEntity, GlobalEntity
from .logic.controller import AreaStatus
from .logic.heating_day import Phase
from .logic.ventilation import VentilationState

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AreaSensorDescription(SensorEntityDescription):
    """Area sensor with a value function."""

    value_fn: Callable[[Area], Any]
    attrs_fn: Callable[[Area], dict[str, Any]] | None = None
    circuit_only: bool = True


def _learner(area: Area) -> Any:
    return area.learner


AREA_SENSORS: tuple[AreaSensorDescription, ...] = (
    AreaSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[s.value for s in AreaStatus],
        value_fn=lambda a: a.status,
    ),
    AreaSensorDescription(
        key="heat_rate",
        native_unit_of_measurement="K/h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda a: round(a.learned_values.heat_rate_kph, 3),
        attrs_fn=lambda a: {
            "heat_effect_kph": round(a.learner.model.a, 4),
            "samples": a.learner.model.n_heat,
        },
    ),
    AreaSensorDescription(
        key="cool_rate",
        native_unit_of_measurement="K/h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda a: round(a.learned_values.cool_rate_kph, 4),
        attrs_fn=lambda a: {"samples": a.learner.model.n_cool},
    ),
    AreaSensorDescription(
        key="overshoot",
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda a: round(a.learner.overshoot.value, 3),
        attrs_fn=lambda a: {
            "per_hour_heating": round(a.learner.overshoot_rate.value, 3),
            "events": a.learner.overshoot.count,
        },
    ),
    AreaSensorDescription(
        key="dead_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda a: round(a.learner.dead_time.value / 60, 1),
        attrs_fn=lambda a: {"events": a.learner.dead_time.count},
    ),
    AreaSensorDescription(
        key="recovery_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda a: round(a.learner.recovery.value / 60, 1),
        attrs_fn=lambda a: {
            "events": a.learner.recovery.count,
            "bias_min": a.params.recovery_bias_min,
        },
    ),
    AreaSensorDescription(
        key="outdoor_influence",
        native_unit_of_measurement="1/h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda a: round(a.learner.model.k, 5),
    ),
    AreaSensorDescription(
        key="sun_influence",
        native_unit_of_measurement="K/h/kW",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda a: round(a.learner.model.s, 4),
    ),
    AreaSensorDescription(
        key="learning_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda a: a.learner.confidence(),
        attrs_fn=lambda a: {"parameters": a.params.as_dict()},
    ),
    AreaSensorDescription(
        key="ventilation",
        device_class=SensorDeviceClass.ENUM,
        options=[s.value for s in VentilationState],
        circuit_only=False,
        value_fn=lambda a: a.ventilation.state if a.ventilation else VentilationState.UNKNOWN,
        attrs_fn=lambda a: (
            {
                "absolute_humidity_inside": a.ventilation.ah_inside,
                "absolute_humidity_reference": a.ventilation.ah_reference,
                "delta_absolute_humidity": a.ventilation.delta_ah,
                "delta_temperature": a.ventilation.delta_t,
                "humidity_high": a.ventilation.rh_high,
                "drying_useful": a.ventilation.drying_useful,
                "cooling_useful": a.ventilation.cooling_useful,
                "humidity_after_exchange": a.ventilation.rh_after_exchange,
            }
            if a.ventilation
            else {}
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AiHeatingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            HeatingDayPhaseSensor(coordinator),
            AiTimestampSensor(coordinator, "ai_last_check", "last_check"),
            AiTimestampSensor(coordinator, "ai_next_check", "next_check"),
            AiCostSensor(coordinator),
        ]
    )
    if coordinator.opt(CONF_HEAT_METER):
        async_add_entities([HeatTodaySensor(coordinator)])
    for area in coordinator.areas.values():
        async_add_entities(
            [
                AreaSensor(coordinator, area.area_id, description)
                for description in AREA_SENSORS
                if area.has_circuit or not description.circuit_only
            ],
            config_subentry_id=area.area_id,
        )


class AreaSensor(AreaEntity, SensorEntity):
    """Sensor of one area."""

    entity_description: AreaSensorDescription

    def __init__(
        self, coordinator: HeatingCoordinator, area_id: str, description: AreaSensorDescription
    ) -> None:
        super().__init__(coordinator, area_id, description.key)
        self.entity_description = description
        if description.key not in ("status", "ventilation"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.area)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.area)


class HeatingDayPhaseSensor(GlobalEntity, SensorEntity):
    """Who currently leads the heating day decision."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [p.value for p in Phase]

    def __init__(self, coordinator: HeatingCoordinator) -> None:
        super().__init__(coordinator, "decision_phase")

    @property
    def native_value(self) -> str:
        return self.coordinator.phase

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        history = self.coordinator.day_state.get("history", [])
        return {
            "theta": self.coordinator.theta,
            "evaluated_days": len(history),
            "last_days": history[-7:],
        }


class AiTimestampSensor(GlobalEntity, SensorEntity):
    """Last or next AI check."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: HeatingCoordinator, key: str, state_key: str) -> None:
        super().__init__(coordinator, key)
        self._state_key = state_key

    @property
    def native_value(self) -> datetime | None:
        return dt_util.parse_datetime(str(self.coordinator.ai_state.get(self._state_key) or ""))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._state_key != "last_check":
            return {"stable_checks": self.coordinator.ai_state.get("stable", 0)}
        ai = self.coordinator.ai_state
        return {
            "summary": ai.get("last_summary"),
            "confidence": ai.get("last_confidence"),
            "rejected": ai.get("last_rejected"),
            "last_error": ai.get("last_error"),
            "last_error_at": ai.get("last_error_at"),
        }


class AiCostSensor(GlobalEntity, SensorEntity):
    """AI costs of the current month."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: HeatingCoordinator) -> None:
        super().__init__(coordinator, "ai_cost_month")

    @property
    def native_value(self) -> float:
        budget = self.coordinator.budget
        budget.roll(dt_util.now().strftime("%Y-%m"))
        return round(budget.spent, 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        budget = self.coordinator.budget
        return {
            "month": budget.month,
            "calls": budget.calls,
            "input_tokens": budget.input_tokens,
            "output_tokens": budget.output_tokens,
            "budget": float(self.coordinator.opt("monthly_budget")),
            "budget_reached": budget.blocked,
        }


class HeatTodaySensor(GlobalEntity, SensorEntity):
    """Heat measured by the heat meter today (between meter readings), more in attributes.

    No state class: the meter itself already feeds the long-term statistics.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: HeatingCoordinator) -> None:
        super().__init__(coordinator, "heat_today")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.meter.kwh_since("today")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meter = self.coordinator.meter
        last = meter.last
        return {
            "yesterday": meter.closed.get("yesterday"),
            "month": meter.kwh_since("month"),
            "last_month": meter.closed.get("last_month"),
            "meter_reading_at": dt_util.utc_from_timestamp(last.ts).isoformat() if last else None,
        }
