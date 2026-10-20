"""Base entities."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TEMP_SENSOR, DOMAIN, NAME
from .coordinator import Area, HeatingCoordinator


def global_device_info(entry_id: str) -> DeviceInfo:
    """Device of the integration as a whole."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=NAME,
        manufacturer=NAME,
        model="Controller",
        entry_type=DeviceEntryType.SERVICE,
    )


def sensor_area_name(hass: HomeAssistant, entity_id: str | None) -> str | None:
    """Name of the Home Assistant area of a sensor (its own or its device's)."""
    entry = er.async_get(hass).async_get(entity_id) if entity_id else None
    if entry is None:
        return None
    area_id = entry.area_id
    if area_id is None and entry.device_id:
        device = dr.async_get(hass).async_get(entry.device_id)
        area_id = device.area_id if device else None
    area = ar.async_get(hass).async_get_area(area_id) if area_id else None
    return area.name if area else None


class GlobalEntity(CoordinatorEntity[HeatingCoordinator]):
    """Entity of the integration as a whole."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HeatingCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = global_device_info(entry_id)


class AreaEntity(CoordinatorEntity[HeatingCoordinator]):
    """Entity belonging to one heating area."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HeatingCoordinator, area_id: str, key: str) -> None:
        super().__init__(coordinator)
        self.area_id = area_id
        area = coordinator.areas[area_id]
        self._attr_translation_key = key
        self._attr_unique_id = f"{area_id}_{key}"
        device_info = DeviceInfo(
            identifiers={(DOMAIN, area_id)},
            name=area.name,
            manufacturer=NAME,
            model="Heating area" if area.has_circuit else "Ventilation area",
        )
        # Reference the main device by its id; the identifier based
        # ``via_device`` is deprecated and fails when HA itself re-adds the
        # entity (e.g. after renaming its entity id).
        if coordinator.global_device_id:
            device_info["via_device_id"] = coordinator.global_device_id
        # only used when the device is created: a later choice of the user stays
        if suggested := sensor_area_name(coordinator.hass, area.cfg.get(CONF_TEMP_SENSOR)):
            device_info["suggested_area"] = suggested
        self._attr_device_info = device_info

    @property
    def area(self) -> Area:
        return self.coordinator.areas[self.area_id]
