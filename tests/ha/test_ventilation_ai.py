"""AI check of the ventilation thresholds and the learned humidity profile."""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.ai_heating_assistant.const import DOMAIN, EVENT_LOGBOOK
from custom_components.ai_heating_assistant.logic.ai_schema import VENT_PARAMS

from .conftest import make_entry
from .test_control import STRUCTURED, USAGE, _advance, _setup

SUMMER = "2026-07-15 10:00:00+02:00"


def _answer(*adjustments: dict) -> tuple[dict, dict]:
    return {"adjustments": list(adjustments), "summary": "Fine.", "confidence": 60}, USAGE


async def test_ventilation_check_runs_all_year_and_backs_off(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(SUMMER)
    change = {"area": "a2", "parameter": "rh_threshold", "value": 72, "reason": "Cellar."}
    with patch(STRUCTURED, side_effect=[_answer(change), _answer()]) as mock:
        await _setup(hass, make_entry(api_key="test-key"))
        coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
        assert not coordinator.season_active
        # first check after the base interval, the statistics need a while
        first = dt_util.parse_datetime(coordinator.vent_state["next_check"])
        assert first - dt_util.utcnow() == timedelta(hours=6)
        events = async_capture_events(hass, EVENT_LOGBOOK)
        await _advance(hass, freezer, 30)
        await coordinator.async_run_vent_check("manual")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock.call_count == 1
        system, user = mock.call_args.args[0], mock.call_args.args[1]
        payload = json.loads(user)
        assert mock.call_args.args[2]["properties"]["adjustments"]["items"]["properties"][
            "parameter"
        ]["enum"] == sorted(VENT_PARAMS)
        assert "rh_threshold" in system
        assert not payload["heating_period"]
        storage = next(a for a in payload["areas"] if a["id"] == "a2")
        assert storage["params"]["rh_threshold"] == 65.0
        assert storage["stats"]["humid_min"] == pytest.approx(30, abs=1)  # 70 % >= 65 %
        assert storage["stats"]["rh_mean"] == 70.0
        assert storage["profile"]["season"] == "summer"
        assert storage["profile"]["floor_14d"] is None  # no day completed yet
        area = next(a for a in coordinator.areas.values() if a.prompt_id == "a2")
        assert area.vent_params.rh_threshold == 68.0  # one step of 3 %
        assert any(
            "Feuchte-Schwelle" in e.data["message"] or "humidity threshold" in e.data["message"]
            for e in events
        )
        # a room humid for long keeps the interval at its base
        assert coordinator.vent_state["stable"] == 0
        assert area.vent_check["minutes"] == 0
        assert (
            hass.states.get("sensor.storage_room_ventilation_recommendation").attributes[
                "humidity_threshold"
            ]
            == 68.0
        )

        # dry again and nothing to change: the interval grows
        hass.states.async_set("sensor.storage_humidity", "50", {"unit_of_measurement": "%"})
        await _advance(hass, freezer, 30)
        await coordinator.async_run_vent_check("manual")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock.call_count == 2
        history = json.loads(mock.call_args.args[1])["history"]
    assert history[0]["changes"] == ["a2 rh_threshold 65>68"]
    assert coordinator.vent_state["stable"] == 1
    later = dt_util.parse_datetime(coordinator.vent_state["next_check"])
    assert later - dt_util.utcnow() == timedelta(hours=12)
    last = hass.states.get("sensor.ai_heating_assistant_last_ai_ventilation_check")
    assert last is not None and last.attributes["summary"] == "Fine."
    stored = coordinator._data_to_save()["areas"][area.area_id]
    assert stored["vent_params"]["rh_threshold"] == 68.0
    assert stored["humidity"]["day"]["n"] > 0


async def test_ventilation_check_off_without_ai_or_option(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(SUMMER)
    await _setup(hass, make_entry(api_key="test-key", ventilation_ai_enabled=False))
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    assert not coordinator.vent_ai_active
    assert coordinator.vent_state["next_check"] is None
    with patch(STRUCTURED) as mock:
        await coordinator.async_run_vent_check("manual")
    mock.assert_not_called()


async def test_ventilation_switching_ai_off_and_on(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(SUMMER)
    await _setup(hass, make_entry(api_key="test-key"))
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    await coordinator.async_set_ai_enabled(False)
    assert coordinator.vent_state["next_check"] is None
    await coordinator.async_set_ai_enabled(True)
    soon = dt_util.parse_datetime(coordinator.vent_state["next_check"])
    assert soon - dt_util.utcnow() == timedelta(minutes=5)


async def test_ventilation_parameters_reset_export_and_import(
    hass: HomeAssistant, base_states, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(SUMMER)
    await _setup(hass, make_entry(api_key="test-key"))
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    area = next(a for a in coordinator.areas.values() if a.prompt_id == "a2")
    area.vent_params.rh_threshold = 74.0
    exported = coordinator.export_parameters([area.area_id])
    assert exported["areas"]["Storage room"]["vent_params"]["rh_threshold"] == 74.0
    assert "humidity" in exported["areas"]["Storage room"]

    coordinator.reset_learned([area.area_id], include_parameters=True)
    assert area.vent_params.rh_threshold == 65.0  # configured start value
    assert area.humidity_profile.day.n == 0

    exported["areas"]["Storage room"]["vent_params"]["rh_threshold"] = 99
    coordinator.import_parameters(exported, [area.area_id])
    assert area.vent_params.rh_threshold == 95.0  # clamped to the limit
