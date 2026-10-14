"""AI Heating Assistant: local learning heating control with periodic AI review."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PUFFER_DOWN, CONF_THETA_DOWN, DOMAIN, PLATFORMS, STORAGE_VERSION
from .coordinator import AiHeatingConfigEntry, HeatingCoordinator
from .entity import global_device_info
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services once."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: AiHeatingConfigEntry) -> bool:
    """Bring the options of an older entry up to date."""
    if entry.version > 1:
        return False
    if entry.minor_version < 2:
        # The evaluation no longer uses relay minutes, and the learning steps down became
        # as large as the steps up (only values still at the old default are changed).
        options = {**entry.options}
        for key in ("relay_need_minutes", "relay_no_need_minutes"):
            options.pop(key, None)
        for key, old, new in ((CONF_THETA_DOWN, 0.5, 1.0), (CONF_PUFFER_DOWN, 0.1, 0.2)):
            if options.get(key) == old:
                options[key] = new
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AiHeatingConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    coordinator = HeatingCoordinator(hass, entry)
    # Create the main device first so area devices can point to it by id.
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **global_device_info(entry.entry_id)
    )
    coordinator.global_device_id = device.id
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: AiHeatingConfigEntry) -> None:
    """Options or areas changed: reload."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AiHeatingConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: AiHeatingConfigEntry) -> None:
    """Delete stored learning data when the integration is removed."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
