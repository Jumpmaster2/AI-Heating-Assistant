"""AI Heating Assistant: local learning heating control with periodic AI review."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_PUFFER_DOWN,
    CONF_SWITCH,
    CONF_THETA_DOWN,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    STORAGE_VERSION,
    SUBENTRY_AREA,
)
from .coordinator import (
    AiHeatingConfigEntry,
    HeatingCoordinator,
    async_delete_issues,
    async_turn_off_switches,
)
from .entity import global_device_info
from .panel import async_register_panel, async_unregister_panel
from .services import async_setup_services
from .websocket import async_register_websocket

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services and the panel commands once."""
    async_setup_services(hass)
    async_register_websocket(hass)
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
    await async_register_panel(hass, entry.entry_id)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: AiHeatingConfigEntry) -> None:
    """Options or areas changed: reload."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AiHeatingConfigEntry) -> bool:
    """Unload a config entry. The coordinator shuts itself down afterwards (it registers
    its shutdown with the entry)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and entry.disabled_by is not None:
        # Disabled (not a reload): stop the control first, so no tick switches a
        # circuit on again, then nothing controls the circuits any more.
        await entry.runtime_data.async_shutdown()
        await _async_switch_off_circuits(hass, entry, "disabled")
        async_delete_issues(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: AiHeatingConfigEntry) -> None:
    """Switch off the circuits and delete stored learning data and the panel when the
    integration is removed."""
    await _async_switch_off_circuits(hass, entry, "removed")
    async_delete_issues(hass)
    async_unregister_panel(hass)
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


async def _async_switch_off_circuits(
    hass: HomeAssistant, entry: AiHeatingConfigEntry, reason: str
) -> None:
    """Switch off every circuit of the entry that is on (a circuit left on would heat
    without limit once nothing controls it)."""
    switches = [
        sub.data[CONF_SWITCH]
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_AREA and sub.data.get(CONF_SWITCH)
    ]
    for entity_id in await async_turn_off_switches(hass, switches):
        LOGGER.info("Switched off %s: %s was %s", entity_id, entry.title, reason)
