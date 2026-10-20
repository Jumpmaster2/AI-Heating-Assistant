"""What happens to the circuits when the integration stops controlling them."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.ai_heating_assistant.const import EVENT_LOGBOOK
from custom_components.ai_heating_assistant.coordinator import HeatingCoordinator

from .conftest import IN_SEASON, make_entry

CIRCUIT = "input_boolean.heating_circuit_1"


async def _setup_heating(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Set up and run until the circuit of the living room heats (19 °C, target 21 °C)."""
    freezer.move_to(IN_SEASON)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    for _ in range(11):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(CIRCUIT).state == "on"
    return entry


async def test_disabling_switches_the_circuits_off(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup_heating(hass, freezer)
    assert await hass.config_entries.async_set_disabled_by(entry.entry_id, ConfigEntryDisabler.USER)
    await hass.async_block_till_done()
    assert hass.states.get(CIRCUIT).state == "off"


async def test_removing_switches_the_circuits_off(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup_heating(hass, freezer)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(CIRCUIT).state == "off"


async def test_reload_keeps_the_circuits_running(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup_heating(hass, freezer)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(CIRCUIT).state == "on"


async def test_circuit_of_a_deleted_area_is_switched_off(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup_heating(hass, freezer)
    events = async_capture_events(hass, EVENT_LOGBOOK)
    living = next(s for s in entry.subentries.values() if s.title == "Living room")
    hass.config_entries.async_remove_subentry(entry, living.subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(CIRCUIT).state == "off"
    assert any(CIRCUIT in e.data["message"] for e in events)


async def test_unload_saves_and_shuts_down_once(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup_heating(hass, freezer)
    store = entry.runtime_data.store
    with patch.object(store, "async_save", wraps=store.async_save) as save:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    assert save.call_count == 1


async def test_failed_first_refresh_leaves_no_listeners(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    """A setup retry must not leave a second control loop behind (audit F-08)."""
    freezer.move_to(IN_SEASON)
    started: list[HeatingCoordinator] = []

    async def fail(self: HeatingCoordinator) -> int:
        started.append(self)
        raise UpdateFailed("sensor platform not ready")

    entry = make_entry()
    entry.add_to_hass(hass)
    with patch.object(HeatingCoordinator, "_async_update_data", fail):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    failed = started[0]
    assert failed._unsubs == [] and failed._unsub_check is None


async def test_released_circuit_not_reachable_is_tried_again(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    """A dropped switch that cannot be switched off now is not forgotten."""
    entry = await _setup_heating(hass, freezer)
    living = next(s for s in entry.subentries.values() if s.title == "Living room")
    hass.states.async_set(CIRCUIT, "unavailable")
    hass.config_entries.async_remove_subentry(entry, living.subentry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data._data_to_save()["release"] == [CIRCUIT]

    hass.states.async_set(CIRCUIT, "on")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(CIRCUIT).state == "off"
    assert entry.runtime_data._data_to_save()["release"] == []


async def test_entities_no_longer_provided_are_removed(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    """Removing the heat meter leaves no "unavailable" heat sensor behind (F-15)."""
    from homeassistant.helpers import entity_registry as er

    freezer.move_to(IN_SEASON)
    hass.states.async_set("sensor.heat_meter", "12.5", {"unit_of_measurement": "MWh"})
    entry = make_entry(heat_meter="sensor.heat_meter")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    registry = er.async_get(hass)
    heat = "sensor.ai_heating_assistant_heat_today"
    assert registry.async_get(heat) is not None
    # a diagnostic entity disabled by the user stays in the registry
    registry.async_update_entity(
        "sensor.living_room_dead_time", disabled_by=er.RegistryEntryDisabler.USER
    )

    options = {k: v for k, v in entry.options.items() if k != "heat_meter"}
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get(heat) is None
    assert registry.async_get("sensor.living_room_dead_time") is not None
    assert registry.async_get("climate.living_room") is not None


async def test_circuit_entities_of_an_area_without_circuit_are_removed(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    from homeassistant.helpers import entity_registry as er

    entry = await _setup_heating(hass, freezer)
    registry = er.async_get(hass)
    living = next(s for s in entry.subentries.values() if s.title == "Living room")
    data = {k: v for k, v in living.data.items() if k != "heater_switch"}
    hass.config_entries.async_update_subentry(entry, living, data=data)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get("climate.living_room") is None
    assert registry.async_get("sensor.living_room_dead_time") is None
    # the ventilation advice of the area stays
    assert registry.async_get("sensor.living_room_ventilation_recommendation") is not None


async def test_entity_that_failed_to_load_keeps_its_registry_entry(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    """A platform error must not delete entities the configuration still provides."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.ai_heating_assistant import climate

    entry = await _setup_heating(hass, freezer)
    registry = er.async_get(hass)
    registry.async_update_entity("climate.living_room", name="My floor")

    async def broken(*args, **kwargs) -> None:
        raise RuntimeError("platform bug")

    with patch.object(climate, "async_setup_entry", broken):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert registry.async_get("climate.living_room").name == "My floor"


async def test_area_device_is_placed_in_the_area_of_its_sensor(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    from custom_components.ai_heating_assistant.const import DOMAIN

    from .conftest import AREA_DATA

    freezer.move_to(IN_SEASON)
    lounge = ar.async_get(hass).async_create("Lounge")
    sensor = er.async_get(hass).async_get_or_create("sensor", "test", "lounge_temp")
    er.async_get(hass).async_update_entity(sensor.entity_id, area_id=lounge.id)
    hass.states.async_set(sensor.entity_id, "19.0", {"unit_of_measurement": "°C"})
    entry = make_entry(areas=[{**AREA_DATA, "temperature_sensor": sensor.entity_id}])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    area_id = next(iter(entry.subentries))
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, area_id), entry.entry_id)
    assert device is not None and device.area_id == lounge.id


async def test_disabling_removes_the_panel(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    import custom_components.ai_heating_assistant as integration

    entry = await _setup_heating(hass, freezer)

    with patch.object(integration, "async_unregister_panel") as unregister:
        assert await hass.config_entries.async_set_disabled_by(
            entry.entry_id, ConfigEntryDisabler.USER
        )
        await hass.async_block_till_done()
    unregister.assert_called_once()
