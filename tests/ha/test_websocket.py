"""WebSocket API of the panel."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.ai_heating_assistant.ai_client import AiAuthError
from custom_components.ai_heating_assistant.const import DOMAIN

from .conftest import AREA_DATA, make_entry


async def _setup(hass: HomeAssistant, **kwargs):
    entry = make_entry(**kwargs)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _send(client, **msg):
    await client.send_json_auto_id(msg)
    return await client.receive_json()


async def test_config_payload(hass: HomeAssistant, base_states, hass_ws_client) -> None:
    await _setup(hass, api_key="secret-key")
    client = await hass_ws_client(hass)

    msg = await _send(client, type=f"{DOMAIN}/config")
    assert msg["success"], msg
    cfg = msg["result"]
    assert cfg["has_api_key"] is True
    assert "secret-key" not in str(cfg)
    assert cfg["options"]["frost_temperature"] == 7.0
    assert cfg["options"]["limits"]["theta"]["max"] > cfg["options"]["limits"]["theta"]["min"]
    assert cfg["entities"]["heating_day"] == "binary_sensor.ai_heating_assistant_heating_day"
    assert cfg["entities"]["ai_enabled"].startswith("switch.")
    living = next(a for a in cfg["areas"] if a["title"] == "Living room")
    storage = next(a for a in cfg["areas"] if a["title"] == "Storage room")
    assert living["entities"]["climate"].startswith("climate.")
    assert "climate" not in storage["entities"]
    assert living["entities"]["heat_rate"] == "sensor.living_room_heat_up_rate"
    assert living["entities"]["learning_progress"].startswith("sensor.")
    assert "learning_progress" not in storage["entities"]
    assert storage["entities"]["ventilation"].startswith("sensor.")
    spec = cfg["option_specs"]["frost_temperature"]
    assert (spec["selector"], spec["min"], spec["max"]) == ("number", 0, 15)
    assert cfg["option_specs"]["vacation_entities"]["multiple"] is True
    assert cfg["area_specs"]["temperature_sensor"]["domain"] == ["sensor"]


async def test_save_options(hass: HomeAssistant, base_states, hass_ws_client) -> None:
    entry = await _setup(hass)
    client = await hass_ws_client(hass)

    msg = await _send(
        client,
        type=f"{DOMAIN}/save_options",
        options={"frost_temperature": "8.5", "preheat_reserve": 45.0, "weather": "weather.home"},
    )
    assert msg["success"], msg
    assert entry.options["frost_temperature"] == 8.5
    assert entry.options["preheat_reserve"] == 45
    assert isinstance(entry.options["preheat_reserve"], int)
    assert entry.options["weather"] == "weather.home"

    # a cleared optional entity is removed, a cleared value falls back to the default
    msg = await _send(
        client,
        type=f"{DOMAIN}/save_options",
        options={"weather": "", "outdoor_humidity": None, "frost_temperature": None},
    )
    assert msg["success"], msg
    assert "weather" not in entry.options
    assert "outdoor_humidity" not in entry.options
    assert entry.options["frost_temperature"] == 7.0

    for options, error in (
        ({"outdoor_temperature": ""}, "required:outdoor_temperature"),
        ({"frost_temperature": 99}, "invalid_value:frost_temperature"),
        ({"weather": "sensor.not_weather"}, "invalid_value:weather"),
        ({"season_start": "31.02."}, "invalid_day_month:season_start"),
        ({"check_interval": 10, "check_max_interval": 5}, "max_below_base:check_max_interval"),
        ({"not_an_option": 1}, "unknown_option:not_an_option"),
        ({"limits": {"theta": {"min": 20, "max": 10}}}, "min_above_max:theta"),
    ):
        msg = await _send(client, type=f"{DOMAIN}/save_options", options=options)
        assert not msg["success"], options
        assert msg["error"]["message"] == error
    assert entry.options["frost_temperature"] == 7.0


async def test_save_options_model_prices_and_limits(
    hass: HomeAssistant, base_states, hass_ws_client
) -> None:
    entry = await _setup(hass)
    client = await hass_ws_client(hass)

    # prices still at the old model's suggestion follow the new model
    msg = await _send(client, type=f"{DOMAIN}/save_options", options={"model": "claude-sonnet-5-5"})
    assert msg["success"], msg
    assert entry.options["price_input"] == 2.0
    assert msg["result"]["options"]["price_output"] == 10.0

    msg = await _send(
        client,
        type=f"{DOMAIN}/save_options",
        options={"limits": {"theta": {"min": 10, "max": 18, "step": 0.5}}},
    )
    assert msg["success"], msg
    assert entry.options["limits"]["theta"] == {"min": 10.0, "max": 18.0, "step": 0.5}
    assert "puffer" in entry.options["limits"]


async def test_save_api_key(hass: HomeAssistant, base_states, hass_ws_client) -> None:
    entry = await _setup(hass)
    client = await hass_ws_client(hass)
    target = "custom_components.ai_heating_assistant.config_flow.ClaudeClient.validate"

    with patch(target, side_effect=AiAuthError("authentication failed")):
        msg = await _send(client, type=f"{DOMAIN}/save_api_key", api_key="wrong")
    assert not msg["success"]
    assert msg["error"]["message"] == "invalid_auth"
    assert entry.data["api_key"] == ""

    msg = await _send(client, type=f"{DOMAIN}/save_api_key", api_key=" ")
    assert msg["error"]["message"] == "api_key_required"

    with patch(target):
        msg = await _send(client, type=f"{DOMAIN}/save_api_key", api_key=" good-key ")
        await hass.async_block_till_done(wait_background_tasks=True)
    assert msg["success"], msg
    assert msg["result"]["has_api_key"] is True
    assert entry.data["api_key"] == "good-key"
    assert entry.runtime_data.ai_configured

    msg = await _send(client, type=f"{DOMAIN}/save_api_key", remove=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert msg["success"]
    assert entry.data["api_key"] == ""
    assert not entry.runtime_data.ai_configured


async def test_areas(hass: HomeAssistant, base_states, hass_ws_client) -> None:
    entry = await _setup(hass, areas=[AREA_DATA])
    client = await hass_ws_client(hass)

    msg = await _send(
        client,
        type=f"{DOMAIN}/save_area",
        title=" Bath ",
        data={
            "temperature_sensor": "sensor.storage_temperature",
            "humidity_sensor": "sensor.storage_humidity",
            "window_sensors": [],
            "heater_switch": "",
            "ventilation_rh_threshold": "65",
            "old_key": 1,
        },
    )
    assert msg["success"], msg
    sub_id = msg["result"]["subentry_id"]
    sub = entry.subentries[sub_id]
    assert sub.title == "Bath"
    assert sub.data["name"] == "Bath"
    assert sub.data["ventilation_rh_threshold"] == 65.0
    assert sub.data["dead_time"] == 30
    assert "heater_switch" not in sub.data
    assert "old_key" not in sub.data

    msg = await _send(
        client,
        type=f"{DOMAIN}/save_area",
        subentry_id=sub_id,
        title="Bathroom",
        data={**sub.data, "default_target": 22.5},
    )
    assert msg["success"], msg
    assert entry.subentries[sub_id].title == "Bathroom"
    assert entry.subentries[sub_id].data["default_target"] == 22.5

    for title, data, error in (
        ("", {"temperature_sensor": "sensor.x"}, "name_required"),
        ("X", {}, "required:temperature_sensor"),
        (
            "X",
            {"temperature_sensor": "sensor.x", "min_target": 22, "max_target": 20},
            "min_above_max",
        ),
        (
            "X",
            {"temperature_sensor": "sensor.x", "reference_temperature": "sensor.y"},
            "reference_incomplete",
        ),
        ("X", {"temperature_sensor": "binary_sensor.x"}, "invalid_value:temperature_sensor"),
    ):
        msg = await _send(client, type=f"{DOMAIN}/save_area", title=title, data=data)
        assert not msg["success"], data
        assert msg["error"]["message"] == error

    msg = await _send(client, type=f"{DOMAIN}/delete_area", subentry_id=sub_id)
    assert msg["success"]
    assert sub_id not in entry.subentries
    msg = await _send(client, type=f"{DOMAIN}/delete_area", subentry_id=sub_id)
    assert not msg["success"]


async def test_area_change_reloads(hass: HomeAssistant, base_states, hass_ws_client) -> None:
    entry = await _setup(hass, areas=[AREA_DATA])
    client = await hass_ws_client(hass)
    sub_id = next(iter(entry.subentries))
    msg = await _send(
        client,
        type=f"{DOMAIN}/save_area",
        subentry_id=sub_id,
        title="Lounge",
        data={**entry.subentries[sub_id].data, "dead_time": 45},
    )
    assert msg["success"], msg
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.runtime_data.areas[sub_id].name == "Lounge"
    msg = await _send(client, type=f"{DOMAIN}/config")
    assert msg["result"]["areas"][0]["entities"]["climate"].startswith("climate.")
