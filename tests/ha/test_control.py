"""Control loop, AI calls, services and diagnostics with a test instance."""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.ai_heating_assistant.const import DOMAIN, EVENT_LOGBOOK, STORAGE_VERSION
from custom_components.ai_heating_assistant.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import IN_SEASON, make_entry

STRUCTURED = "custom_components.ai_heating_assistant.ai_client.ClaudeClient.structured"
USAGE = {"input_tokens": 1500, "output_tokens": 500}


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float) -> None:
    """Advance time minute by minute so every controller tick runs."""
    for _ in range(int(minutes)):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)


async def test_heats_respects_min_times_and_window(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    entry = make_entry()
    await _setup(hass, entry)

    climate = hass.states.get("climate.living_room")
    assert climate is not None
    assert climate.attributes["temperature"] == 21.0
    assert hass.states.get("binary_sensor.ai_heating_assistant_heating_day").state == "on"
    # switch was just created: minimum off time first
    assert hass.states.get("input_boolean.heating_circuit_1").state == "off"

    await _advance(hass, freezer, 11)
    assert hass.states.get("input_boolean.heating_circuit_1").state == "on"
    assert hass.states.get("climate.living_room").attributes["hvac_action"] == "heating"
    assert hass.states.get("sensor.living_room_status").state == "heating"

    # window open: pause after the delay, switch off after the minimum on time
    hass.states.async_set("binary_sensor.living_room_window", "on")
    await _advance(hass, freezer, 1)
    hass.states.async_set("sensor.living_room_temperature", "18.0")
    await _advance(hass, freezer, 5)
    assert hass.states.get("sensor.living_room_status").state == "window_open"
    await _advance(hass, freezer, 5)
    assert hass.states.get("input_boolean.heating_circuit_1").state == "off"

    # closed again: recovery
    hass.states.async_set("binary_sensor.living_room_window", "off")
    await _advance(hass, freezer, 1)
    assert hass.states.get("sensor.living_room_status").state == "recovery"


async def test_external_switching_is_logged(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    hass.states.async_set("sensor.living_room_temperature", "22.5")
    await _setup(hass, make_entry())
    events = async_capture_events(hass, EVENT_LOGBOOK)
    await hass.services.async_call(
        "input_boolean", "turn_on", {"entity_id": "input_boolean.heating_circuit_1"}, blocking=True
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert any("external" in e.data["message"] or "außen" in e.data["message"] for e in events)


async def test_set_target_and_off(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    await _setup(hass, make_entry())
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.living_room", "temperature": 22.5},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("climate.living_room").attributes["temperature"] == 22.5
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.living_room", "hvac_mode": "off"},
        blocking=True,
    )
    await _advance(hass, freezer, 1)
    assert hass.states.get("sensor.living_room_status").state == "off"


async def test_out_of_season_frost_only(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-07-01 10:00:00+02:00")
    await _setup(hass, make_entry())
    await _advance(hass, freezer, 11)
    assert hass.states.get("sensor.living_room_status").state == "out_of_season"
    assert hass.states.get("input_boolean.heating_circuit_1").state == "off"
    hass.states.async_set("sensor.living_room_temperature", "5.0")
    await _advance(hass, freezer, 1)
    assert hass.states.get("sensor.living_room_status").state == "frost_protection"
    assert hass.states.get("input_boolean.heating_circuit_1").state == "on"


async def test_nightly_run_out_of_season(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-07-01 02:58:00+02:00")
    await _setup(hass, make_entry())
    day = hass.states.get("binary_sensor.ai_heating_assistant_heating_day")
    assert day.attributes["decided_at"] is None
    assert day.attributes["next_decision"] == "2026-07-01T01:00:00+00:00"
    await _advance(hass, freezer, 3)
    day = hass.states.get("binary_sensor.ai_heating_assistant_heating_day")
    assert day.state == "off"
    assert day.attributes["source"] == "season"
    assert day.attributes["decided_at"] == "2026-07-01T01:00:00+00:00"
    assert day.attributes["next_decision"] == "2026-07-02T01:00:00+00:00"


async def test_ventilation_only_area(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    await _setup(hass, make_entry())
    assert hass.states.get("climate.storage_room") is None
    state = hass.states.get("sensor.storage_room_ventilation_recommendation")
    assert state is not None and state.state == "ventilate_now"
    assert hass.states.get("binary_sensor.storage_room_ventilation_recommended").state == "on"


async def test_nightly_ai_says_no(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    answer = (
        {"heating_day": False, "confidence": 80, "reason": "Mild.", "critical_area": "a1"},
        USAGE,
    )
    with patch(STRUCTURED, return_value=answer) as mock:
        await _setup(hass, make_entry(api_key="test-key"))
        assert mock.call_count == 1
        system, user = mock.call_args.args[0], mock.call_args.args[1]
        assert "underfloor" in system and "test-key" not in user
    state = hass.states.get("binary_sensor.ai_heating_assistant_heating_day")
    assert state.state == "off"
    assert state.attributes["source"] == "ai"
    assert state.attributes["critical_area"] == "Living room"
    # decided at setup, next nightly run at 03:00 local time
    assert state.attributes["decided_at"] == "2026-11-16T09:00:00+00:00"
    assert state.attributes["next_decision"] == "2026-11-17T02:00:00+00:00"
    await _advance(hass, freezer, 11)
    assert hass.states.get("sensor.living_room_status").state == "no_heating_day"
    assert hass.states.get("input_boolean.heating_circuit_1").state == "off"
    cost = hass.states.get("sensor.ai_heating_assistant_ai_costs_this_month")
    assert float(cost.state) == pytest.approx((1500 * 4 + 500 * 20) / 1e6, abs=1e-4)


async def test_periodic_check_adjusts_within_limits(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    nightly = (
        {"heating_day": True, "confidence": 90, "reason": "Cold.", "critical_area": ""},
        USAGE,
    )
    check = (
        {
            "adjustments": [
                {
                    "area": "a1",
                    "parameter": "hysteresis_on",
                    "value": 0.6,
                    "reason": "Too cold in the morning.",
                },
                {"area": "a1", "parameter": "bogus", "value": 1, "reason": "x"},
            ],
            "summary": "One change.",
            "confidence": 70,
        },
        USAGE,
    )
    with patch(STRUCTURED, side_effect=[nightly, check]) as mock:
        await _setup(hass, make_entry(api_key="test-key"))
        events = async_capture_events(hass, EVENT_LOGBOOK)
        coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
        await coordinator.async_run_ai_check("manual")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock.call_count == 2
    area = next(iter(coordinator.areas.values()))
    assert area.params.hysteresis_on == pytest.approx(0.3)  # 0.2 + max step 0.1
    assert any("hysteresis_on" in e.data["message"] for e in events)
    assert coordinator.ai_state["last_rejected"]
    assert coordinator.ai_state["next_check"] is not None


async def test_overheating_is_counted_and_shown_to_the_ai(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    nightly = (
        {"heating_day": True, "confidence": 90, "reason": "Cold.", "critical_area": ""},
        USAGE,
    )
    change = {"area": "a1", "parameter": "overshoot_factor", "value": 1.1, "reason": "Peak."}
    first = ({"adjustments": [change], "summary": "", "confidence": 60}, USAGE)
    second = ({"adjustments": [], "summary": "", "confidence": 60}, USAGE)
    with patch(STRUCTURED, side_effect=[nightly, first, second]) as mock:
        await _setup(hass, make_entry(api_key="test-key"))
        coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
        area = next(a for a in coordinator.areas.values() if a.has_circuit)
        ts = dt_util.utcnow().timestamp()
        area.check = {}
        area.temp, area.switch_on, area.window_open = 21.5, False, False
        # warm without recent heating (sun only): not wasted
        area.off_at = None
        coordinator._count(area, 60, 21.0, ts)
        assert area.check.get("over_kh", 0.0) == 0.0
        # one hour after switch-off: 0.3 K beyond the tolerance for one hour
        area.off_at = ts - 3600
        coordinator._count(area, 60, 21.0, ts)
        assert area.check["over_kh"] == pytest.approx(0.3)
        assert area.day.over_kh == pytest.approx(0.3)
        assert area.check["deg_h"] == pytest.approx(2 * 16.0)  # outdoor 5 °C, target 21 °C

        await coordinator.async_run_ai_check("manual")
        await hass.async_block_till_done(wait_background_tasks=True)
        stats = json.loads(mock.call_args.args[1])["areas"][0]["stats"]
        assert stats["over_kh"] == pytest.approx(0.3)
        # overheating keeps the interval at its base value
        assert coordinator.ai_state["stable"] == 0

        await coordinator.async_run_ai_check("manual")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock.call_count == 3
        history = json.loads(mock.call_args.args[1])["history"]
    assert history[0]["changes"] == ["a1 overshoot_factor 1>1.1"]
    assert history[0]["areas"]["a1"]["over_kh"] == pytest.approx(0.3)
    assert len(coordinator.ai_state["check_history"]) == 2

    coordinator.reset_learned([area.area_id], include_parameters=False)
    assert all("a1" not in h["areas"] for h in coordinator.ai_state["check_history"])


async def test_heat_meter_feeds_check_and_dashboard(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    hass.states.async_set("sensor.heat_meter", "12.500", {"unit_of_measurement": "MWh"})
    nightly = (
        {"heating_day": True, "confidence": 90, "reason": "Cold.", "critical_area": ""},
        USAGE,
    )
    check = ({"adjustments": [], "summary": "", "confidence": 60}, USAGE)
    with patch(STRUCTURED, side_effect=[nightly, check]) as mock:
        await _setup(hass, make_entry(api_key="test-key", heat_meter="sensor.heat_meter"))
        coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
        await _advance(hass, freezer, 120)
        hass.states.async_set("sensor.heat_meter", "12.520", {"unit_of_measurement": "MWh"})
        await _advance(hass, freezer, 1)
        await coordinator.async_run_ai_check("manual")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock.call_count == 2
        payload = json.loads(mock.call_args.args[1])
    heat = payload["heat"]
    assert heat["kwh"] == pytest.approx(20.0)
    assert heat["hours"] == pytest.approx(2.0, abs=0.1)
    # demand: target 21 °C, outdoor 5 °C for about two hours
    assert heat["kwh_per_kh"] == pytest.approx(20 / 32, rel=0.05)
    assert coordinator.ai_state["check_history"][-1]["kwh_per_kh"] == heat["kwh_per_kh"]
    today = hass.states.get("sensor.ai_heating_assistant_heat_today")
    assert float(today.state) == pytest.approx(20.0)
    assert today.attributes["month"] == pytest.approx(20.0)


async def test_no_heat_sensor_without_meter(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    await _setup(hass, make_entry())
    assert hass.states.get("sensor.ai_heating_assistant_heat_today") is None


async def test_heat_meter_reading_after_midnight_counts_for_the_new_day(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    hass.states.async_set("sensor.heat_meter", "12.500", {"unit_of_measurement": "MWh"})
    await _setup(hass, make_entry(heat_meter="sensor.heat_meter"))
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    def reading(at: str, value: str) -> None:
        freezer.move_to(at)
        hass.states.async_set("sensor.heat_meter", value, {"unit_of_measurement": "MWh"})
        coordinator._update_meter(dt_util.utcnow().timestamp(), 0.0)

    reading("2026-11-16 23:55:00+01:00", "12.510")
    reading("2026-11-17 00:01:00+01:00", "12.513")
    assert coordinator.meter.closed["yesterday"] == pytest.approx(10.0)
    assert coordinator.meter.kwh_since("today") == pytest.approx(3.0)


async def test_heat_meter_removed_starts_again(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    hass.states.async_set("sensor.heat_meter", "12.500", {"unit_of_measurement": "MWh"})
    await _setup(hass, make_entry(heat_meter="sensor.heat_meter"))
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    assert coordinator.meter.last is not None
    opt = coordinator.opt
    with patch.object(
        coordinator, "opt", side_effect=lambda key: None if key == "heat_meter" else opt(key)
    ):
        coordinator._update_meter(dt_util.utcnow().timestamp(), 1.0)
    assert coordinator.meter.last is None
    assert coordinator.meter.entity == ""


async def test_budget_blocks_calls(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    with patch(STRUCTURED) as mock:
        await _setup(hass, make_entry(api_key="test-key", monthly_budget=0.0))
        assert mock.call_count == 0
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    assert coordinator.budget.blocked
    # the rule decided instead
    assert coordinator.current_day["source"] == "rule_fallback"


async def test_ai_error_keeps_control_running(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    from custom_components.ai_heating_assistant.ai_client import AiError

    freezer.move_to(IN_SEASON)
    with patch(STRUCTURED, side_effect=AiError("cannot connect or timeout")):
        await _setup(hass, make_entry(api_key="test-key"))
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    assert coordinator.current_day["source"] == "rule_fallback"
    assert "cannot connect" in coordinator.ai_state["last_error"]
    await _advance(hass, freezer, 11)
    assert hass.states.get("input_boolean.heating_circuit_1").state == "on"


async def test_services_export_import_reset(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    await _setup(hass, make_entry())
    exported = await hass.services.async_call(
        DOMAIN, "export_parameters", {}, blocking=True, return_response=True
    )
    assert "Living room" in exported["areas"]
    data = exported["areas"]["Living room"]
    data["learned"]["dead_time_min"] = 75
    data["params"]["hysteresis_on"] = 5.0  # clamped to the limit
    result = await hass.services.async_call(
        DOMAIN, "import_parameters", {"data": exported}, blocking=True, return_response=True
    )
    assert result == {"imported": ["Living room", "Storage room"]}
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    area = next(iter(coordinator.areas.values()))
    assert area.learner.dead_time.value == 75 * 60
    assert area.params.hysteresis_on == 0.6

    await hass.services.async_call(
        DOMAIN,
        "reset_learned",
        {"entity_id": "climate.living_room", "include_parameters": True},
        blocking=True,
    )
    area = next(iter(coordinator.areas.values()))
    assert area.learner.dead_time.value == 30 * 60
    assert area.params.hysteresis_on == 0.2


async def test_diagnostics_redacts_key(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    with patch(
        STRUCTURED,
        return_value=(
            {"heating_day": True, "confidence": 50, "reason": "", "critical_area": ""},
            USAGE,
        ),
    ):
        entry = make_entry(api_key="secret-key")
        await _setup(hass, entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert "secret-key" not in str(diagnostics)
    assert diagnostics["entry"]["data"]["api_key"] == "**REDACTED**"


async def test_unload_and_storage(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    entry = make_entry()
    await _setup(hass, entry)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.living_room", "temperature": 20.0},
        blocking=True,
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("climate.living_room").attributes["temperature"] == 20.0


async def test_entity_id_rename_keeps_entity(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    """Renaming an entity id re-adds the entity from HA core (regression for via_device)."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    await _setup(hass, make_entry())
    er.async_get(hass).async_update_entity(
        "climate.living_room", new_entity_id="climate.living_room_heating"
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("climate.living_room_heating") is not None
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    devices = dr.async_get(hass)
    area_id = next(iter(entry.subentries))
    area_device = devices.async_get_device_by_identifier((DOMAIN, area_id), entry.entry_id)
    main_device = devices.async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert area_device is not None and main_device is not None
    assert area_device.via_device_id == main_device.id


async def test_vacation_return_in_past_is_ignored_and_preheat_before_return(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    from datetime import datetime

    def set_return(value: str) -> None:
        stamp = datetime.fromisoformat(value + "+01:00").timestamp()
        hass.states.async_set(
            "input_datetime.vacation_end",
            value,
            {"has_date": True, "has_time": True, "timestamp": stamp},
        )

    hass.states.async_set("input_boolean.vacation", "on")
    set_return("2026-04-10 18:00:00")
    entry = make_entry(
        vacation_entities=["input_boolean.vacation"], return_entity="input_datetime.vacation_end"
    )
    await _setup(hass, entry)
    await _advance(hass, freezer, 1)
    # return date long past: vacation temperature applies, no preheating
    assert hass.states.get("climate.living_room").attributes["effective_target"] == 18.0
    # 19 °C is above 18 °C + puffer, so no heating is needed at all
    assert hass.states.get("sensor.living_room_status").state in ("vacation", "no_heating_day")

    # return in 2 hours: preheating to the normal target has to start already
    set_return("2026-11-16 12:00:00")
    await _advance(hass, freezer, 1)
    assert hass.states.get("climate.living_room").attributes["effective_target"] == 21.0
    assert hass.states.get("sensor.living_room_status").state == "preheat"


async def test_pv_forecast_sensor_sets_expected_sun(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(IN_SEASON)
    hass.states.async_set("sensor.pv_power", "0", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.pv_energy_next_hour", "3.0", {"unit_of_measurement": "kWh"})
    await _setup(
        hass, make_entry(pv_power="sensor.pv_power", pv_forecast="sensor.pv_energy_next_hour")
    )
    await _advance(hass, freezer, 1)
    expected = hass.states.get("climate.living_room").attributes["expected_pv_kw"]
    assert expected > 0

    # forecast unavailable: only the current PV power counts
    hass.states.async_set("sensor.pv_energy_next_hour", "unavailable")
    await _advance(hass, freezer, 1)
    assert hass.states.get("climate.living_room").attributes["expected_pv_kw"] == 0


async def test_old_store_applies_unlearned_start_values(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory, hass_storage: dict
) -> None:
    """A store of an older version has no record: the configuration wins where nothing was learned."""
    entry = make_entry()
    entry.add_to_hass(hass)
    sub = next(s for s in entry.subentries.values() if s.title == "Living room")
    key = f"{DOMAIN}.{entry.entry_id}"
    hass_storage[key] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": key,
        "data": {
            "areas": {
                sub.subentry_id: {
                    "learner": {
                        "dead_time": {"value": 5400, "count": 0},
                        "recovery": {"value": 5400, "count": 1},
                    }
                }
            }
        },
    }
    events = async_capture_events(hass, EVENT_LOGBOOK)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    area = entry.runtime_data.areas[sub.subentry_id]
    assert area.learner.dead_time.value == 30 * 60  # configured, nothing learned
    assert area.learner.recovery.value == 5400  # learned once: kept
    assert area.start == {
        "dead_time": 1800.0,
        "recovery": 1800.0,
        "window_delay_min": 5.0,
        "puffer": 0.7,
    }
    assert any("dead time" in e.data["message"] for e in events)
    # the record reaches the store with the delayed save
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    stored = hass_storage[key]["data"]["areas"][sub.subentry_id]
    assert (
        stored["start"]["dead_time"] == 1800.0 and stored["learner"]["dead_time"]["value"] == 1800
    )
