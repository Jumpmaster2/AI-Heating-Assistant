"""Config flow, options flow and subentry flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER, FlowType
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ai_heating_assistant.ai_client import AiAuthError
from custom_components.ai_heating_assistant.const import DOMAIN, SUBENTRY_AREA

from .conftest import make_entry

GENERAL = {
    "outdoor_temperature": "sensor.outdoor_temperature",
    "season_start": "01.10.",
    "season_end": "31.03.",
    "frost_temperature": 7.0,
}
VACATION = {"vacation_entities": [], "vacation_temperature": 18.0, "preheat_reserve": 30}
AI = {"model": "claude-sonnet-5-5", "nightly_time": "03:00:00", "monthly_budget": 5.0}


async def test_full_user_flow_without_ai(hass: HomeAssistant, base_states) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**GENERAL, "season_start": "1.13."}
    )
    assert result["errors"] == {"season_start": "invalid_day_month"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], GENERAL)
    assert result["step_id"] == "vacation"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], VACATION)
    assert result["step_id"] == "ai"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], AI)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data == {"api_key": ""}
    assert entry.options["model"] == "claude-sonnet-5-5"
    # prices follow the chosen model
    assert entry.options["price_input"] == 2.0
    assert entry.options["season_start"] == "01.10."
    # the flow continues with the first heating area
    assert result["next_flow"][0] == FlowType.CONFIG_SUBENTRIES_FLOW


async def test_api_key_is_validated(hass: HomeAssistant, base_states) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], GENERAL)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], VACATION)
    with patch(
        "custom_components.ai_heating_assistant.config_flow.ClaudeClient.validate",
        side_effect=AiAuthError("authentication failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**AI, "api_key": "wrong"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with (
        patch("custom_components.ai_heating_assistant.config_flow.ClaudeClient.validate"),
        patch(
            "custom_components.ai_heating_assistant.ai_client.ClaudeClient.structured",
            return_value=(
                {"heating_day": True, "confidence": 50, "reason": "", "critical_area": ""},
                {"input_tokens": 10, "output_tokens": 10},
            ),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**AI, "api_key": "good-key"}
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data["api_key"] == "good-key"


async def test_subentry_flow_adds_area(hass: HomeAssistant, base_states) -> None:
    entry = make_entry(areas=[])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_AREA), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    user_input = {
        "name": "Living room",
        "sensors": {
            "temperature_sensor": "sensor.living_room_temperature",
            "humidity_sensor": "sensor.living_room_humidity",
            "window_sensors": ["binary_sensor.living_room_window"],
        },
        "heating": {
            "heater_switch": "input_boolean.heating_circuit_1",
            "default_target": 21.0,
            "min_target": 16.0,
            "max_target": 24.0,
            "min_on_time": 10,
            "min_off_time": 10,
        },
        "start_values": {"window_delay": 5, "recovery_time": 30, "dead_time": 30, "puffer": 0.7},
        "ventilation": {"ventilation_rh_threshold": 60},
    }
    bad = {**user_input, "heating": {**user_input["heating"], "min_target": 25.0}}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], bad)
    assert result["errors"] == {"base": "min_above_max"}

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Living room"
    assert subentry.data["heater_switch"] == "input_boolean.heating_circuit_1"
    # entry was reloaded and the thermostat exists
    assert hass.states.get("climate.living_room") is not None


async def test_options_menu_and_ai_step(hass: HomeAssistant, base_states) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "ai"}
    )
    assert result["step_id"] == "ai"
    values = {
        "model": "claude-haiku-5-5",
        "effort": "low",
        "nightly_time": "02:30:00",
        "monthly_budget": 3.0,
        "check_interval": 6.0,
        "check_max_interval": 2.0,
        "price_input": 4.0,
        "price_output": 20.0,
        "price_cache_write": 5.0,
        "price_cache_read": 0.2,
        "max_output_tokens": 3000,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], values)
    assert result["errors"] == {"check_max_interval": "max_below_base"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**values, "check_max_interval": 24.0}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["model"] == "claude-haiku-5-5"
    assert entry.options["price_output"] == 0.5  # switched to the haiku suggestion
    assert entry.options["nightly_time"] == "02:30:00"


async def test_options_limits(hass: HomeAssistant, base_states) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "ai_limits"}
    )
    limits = dict(entry.options["limits"])
    limits["hysteresis_on"] = {"min": 0.5, "max": 0.1, "step": 0.1}
    result = await hass.config_entries.options.async_configure(result["flow_id"], limits)
    assert result["errors"] == {"hysteresis_on": "min_above_max"}
    limits["hysteresis_on"] = {"min": 0.1, "max": 0.4, "step": 0.05}
    result = await hass.config_entries.options.async_configure(result["flow_id"], limits)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.options["limits"]["hysteresis_on"] == {"min": 0.1, "max": 0.4, "step": 0.05}


async def test_reconfigure_api_key(hass: HomeAssistant, base_states) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await entry.start_reconfigure_flow(hass)
    with patch("custom_components.ai_heating_assistant.config_flow.ClaudeClient.validate"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": "new-key"}
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["api_key"] == "new-key"


async def test_options_ventilation_cooling_margin(hass: HomeAssistant, base_states) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "ventilation"}
    )
    assert result["step_id"] == "ventilation"
    values = {
        "ventilation_min_ah_advantage": 0.8,
        "ventilation_max_reference_excess": 4.0,
        "ventilation_min_cooling_advantage": 1.0,
        "ventilation_cooling_margin": 1.5,
        "ventilation_cooling_min_temp": 23.5,
        "night_start_hour": 20,
        "night_end_hour": 8,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], values)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["ventilation_cooling_margin"] == 1.5
    assert entry.options["ventilation_cooling_min_temp"] == 23.5


async def test_reconfigure_target_of_area_without_circuit(hass: HomeAssistant, base_states) -> None:
    """Areas without a heating circuit take the target from their configuration."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    sub = next(s for s in entry.subentries.values() if s.title == "Storage room")
    assert entry.runtime_data.areas[sub.subentry_id].target == 21.0

    result = await entry.start_subentry_reconfigure_flow(hass, sub.subentry_id)
    user_input = {
        "name": "Storage room",
        "sensors": {
            "temperature_sensor": "sensor.storage_temperature",
            "humidity_sensor": "sensor.storage_humidity",
            "window_sensors": [],
        },
        "heating": {
            "default_target": 18.0,
            "min_target": 16.0,
            "max_target": 24.0,
            "min_on_time": 10,
            "min_off_time": 10,
        },
        "start_values": {"window_delay": 5, "recovery_time": 30, "dead_time": 30, "puffer": 0.7},
        "ventilation": {"ventilation_rh_threshold": 65},
    }
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert result["reason"] == "reconfigure_successful"
    assert entry.runtime_data.areas[sub.subentry_id].target == 18.0
