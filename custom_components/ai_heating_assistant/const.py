"""Constants for AI Heating Assistant."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

from .logic.draft import DRAFT_GROUP_KEYS

DOMAIN: Final = "ai_heating_assistant"
NAME: Final = "AI Heating Assistant"
LOGGER = logging.getLogger(__package__)

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

SUBENTRY_AREA: Final = "heating_area"
STORAGE_VERSION: Final = 1
EVENT_LOGBOOK: Final = f"{DOMAIN}_logbook"
TICK_SECONDS: Final = 60

# ---------- global options ----------
CONF_OUTDOOR_TEMP = "outdoor_temperature"
CONF_OUTDOOR_HUMIDITY = "outdoor_humidity"
CONF_WEATHER = "weather"
CONF_PV_POWER = "pv_power"
CONF_PV_FORECAST = "pv_forecast"
CONF_HEAT_METER = "heat_meter"
CONF_SEASON_START = "season_start"
CONF_SEASON_END = "season_end"
CONF_FROST_TEMP = "frost_temperature"
CONF_FORECAST_TRUST = "forecast_trust"
CONF_FORCE_ON_BELOW = "force_on_below"

CONF_VACATION_ENTITIES = "vacation_entities"
CONF_VACATION_TEMP = "vacation_temperature"
CONF_RETURN_ENTITY = "return_entity"
CONF_PREHEAT_RESERVE = "preheat_reserve"

CONF_EMERGENCY_ENABLED = "emergency_enabled"
CONF_EMERGENCY_DELTA = "emergency_delta"
CONF_EMERGENCY_DURATION = "emergency_duration"
CONF_EMERGENCY_QUIET = "emergency_window_quiet"

CONF_VENT_MIN_AH = "ventilation_min_ah_advantage"
CONF_VENT_MAX_EXCESS = "ventilation_max_reference_excess"
CONF_VENT_MIN_COOLING = "ventilation_min_cooling_advantage"
CONF_VENT_COOL_MARGIN = "ventilation_cooling_margin"
CONF_VENT_COOL_MIN_TEMP = "ventilation_cooling_min_temp"
CONF_VENT_ENERGY = "ventilation_energy_rh_per_k"
# The thresholds above and the humidity threshold of an area are start values: the
# ventilation check of the AI adjusts them per area.
CONF_VENT_AI = "ventilation_ai_enabled"
CONF_VENT_CHECK_INTERVAL = "ventilation_check_interval"
CONF_VENT_CHECK_MAX_INTERVAL = "ventilation_check_max_interval"
CONF_NIGHT_START = "night_start_hour"
CONF_NIGHT_END = "night_end_hour"

CONF_AI_MODEL = "model"
CONF_AI_EFFORT = "effort"
CONF_NIGHTLY_TIME = "nightly_time"
CONF_CHECK_INTERVAL = "check_interval"
CONF_CHECK_MAX_INTERVAL = "check_max_interval"
CONF_BUDGET = "monthly_budget"
CONF_PRICE_INPUT = "price_input"
CONF_PRICE_OUTPUT = "price_output"
CONF_PRICE_CACHE_WRITE = "price_cache_write"
CONF_PRICE_CACHE_READ = "price_cache_read"
CONF_MAX_OUTPUT_TOKENS = "max_output_tokens"
CONF_LIMITS = "limits"
CONF_PROMPTS = "prompt_blocks"

CONF_THETA_START = "theta_start"
CONF_TOO_COLD_MARGIN = "too_cold_margin"
CONF_TOO_COLD_MINUTES = "too_cold_minutes"
CONF_THETA_UP = "theta_step_up"
CONF_THETA_DOWN = "theta_step_down"
CONF_PUFFER_UP = "puffer_step_up"
CONF_PUFFER_DOWN = "puffer_step_down"
CONF_SHARED_DAYS = "phase_shared_min_days"
CONF_SHARED_AGREEMENT = "phase_shared_min_agreement"
CONF_RULE_DAYS = "phase_rule_min_days"
CONF_RULE_AGREEMENT = "phase_rule_min_agreement"
CONF_PHASE_MAX_ERRORS = "phase_max_rule_errors"
CONF_FALLBACK_ERRORS = "phase_fallback_errors_7d"
CONF_AI_CHECK_DAYS = "phase_ai_check_every_days"

# ---------- area (subentry) ----------
CONF_AREA_NAME = "name"
CONF_SWITCH = "heater_switch"
CONF_HEATING_TYPE = "heating_type"
HEATING_TYPES: Final = ("underfloor", "radiator", "other")
CONF_TEMP_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_WINDOWS = "window_sensors"
# combinations of windows in other rooms whose draft cools this area too
CONF_DRAFT_GROUPS: Final = DRAFT_GROUP_KEYS
CONF_DEFAULT_TARGET = "default_target"
CONF_MIN_TARGET = "min_target"
CONF_MAX_TARGET = "max_target"
CONF_MIN_ON = "min_on_time"
CONF_MIN_OFF = "min_off_time"
CONF_WINDOW_DELAY = "window_delay"
CONF_RECOVERY = "recovery_time"
CONF_DEAD_TIME = "dead_time"
CONF_PUFFER = "puffer"
CONF_VENT_RH = "ventilation_rh_threshold"
CONF_REF_TEMP = "reference_temperature"
CONF_REF_HUMIDITY = "reference_humidity"
CONF_VENT_BLOCK = "ventilation_block_entity"

SECTION_HEATING = "heating"
SECTION_SENSORS = "sensors"
SECTION_VENTILATION = "ventilation"
SECTION_DRAFT = "draft"
SECTION_START = "start_values"
SECTION_LEARNED = "learned_values"
LEARNED_THETA = "theta"

# ---------- AI ----------
EFFORT_OPTIONS: Final = ["auto", "low", "medium", "high"]
MODEL_OPTIONS: Final = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
# Suggested list prices (per million tokens). Only defaults for the UI fields;
# the values in the options are what counts.
MODEL_PRICE_SUGGESTIONS: Final = {
    "claude-opus-5-5": (4.0, 20.0, 5.0, 0.2),
    "claude-sonnet-5-5": (2.0, 10.0, 2.5, 0.2),
    "claude-haiku-5-5": (0.1, 0.5, 0.125, 0.01),
}
FALLBACK_MODELS: Final = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_BETA: Final = "server-side-fallback-2026-07-01"

DEFAULT_MODEL: Final = "claude-opus-5-5"
# Heating period suggested south of the equator (the defaults below are northern).
SOUTHERN_SEASON: Final = {"season_start": "01.05.", "season_end": "30.09."}

DEFAULTS: Final[dict[str, object]] = {
    CONF_SEASON_START: "01.10.",
    CONF_SEASON_END: "31.03.",
    CONF_FROST_TEMP: 7.0,
    CONF_FORECAST_TRUST: 70,
    CONF_FORCE_ON_BELOW: 1.0,
    CONF_VACATION_ENTITIES: [],
    CONF_VACATION_TEMP: 18.0,
    CONF_PREHEAT_RESERVE: 30,
    CONF_EMERGENCY_ENABLED: True,
    CONF_EMERGENCY_DELTA: 1.0,
    CONF_EMERGENCY_DURATION: 45,
    CONF_EMERGENCY_QUIET: 30,
    CONF_VENT_MIN_AH: 0.8,
    CONF_VENT_MAX_EXCESS: 4.0,
    CONF_VENT_MIN_COOLING: 1.0,
    CONF_VENT_COOL_MARGIN: 1.0,
    CONF_VENT_COOL_MIN_TEMP: 0.0,
    CONF_VENT_ENERGY: 0.25,
    CONF_VENT_AI: True,
    CONF_VENT_CHECK_INTERVAL: 6.0,
    CONF_VENT_CHECK_MAX_INTERVAL: 72.0,
    CONF_NIGHT_START: "20:00:00",
    CONF_NIGHT_END: "08:00:00",
    CONF_AI_MODEL: DEFAULT_MODEL,
    CONF_AI_EFFORT: "low",
    CONF_NIGHTLY_TIME: "03:00:00",
    CONF_CHECK_INTERVAL: 4.0,
    CONF_CHECK_MAX_INTERVAL: 48.0,
    CONF_BUDGET: 5.0,
    CONF_PRICE_INPUT: 4.0,
    CONF_PRICE_OUTPUT: 20.0,
    CONF_PRICE_CACHE_WRITE: 5.0,
    CONF_PRICE_CACHE_READ: 0.2,
    CONF_MAX_OUTPUT_TOKENS: 16000,
    CONF_THETA_START: 16.0,
    CONF_TOO_COLD_MARGIN: 0.5,
    CONF_TOO_COLD_MINUTES: 15,
    CONF_THETA_UP: 1.0,
    CONF_THETA_DOWN: 1.0,
    CONF_PUFFER_UP: 0.2,
    CONF_PUFFER_DOWN: 0.2,
    CONF_SHARED_DAYS: 14,
    CONF_SHARED_AGREEMENT: 80,
    CONF_RULE_DAYS: 21,
    CONF_RULE_AGREEMENT: 90,
    CONF_PHASE_MAX_ERRORS: 1,
    CONF_FALLBACK_ERRORS: 2,
    CONF_AI_CHECK_DAYS: 7,
}

AREA_DEFAULTS: Final[dict[str, object]] = {
    CONF_WINDOWS: [],
    **{key: [] for key in DRAFT_GROUP_KEYS},
    CONF_DEFAULT_TARGET: 21.0,
    CONF_MIN_TARGET: 16.0,
    CONF_MAX_TARGET: 24.0,
    CONF_MIN_ON: 10,
    CONF_MIN_OFF: 10,
    CONF_HEATING_TYPE: "underfloor",
    CONF_WINDOW_DELAY: 5,
    CONF_RECOVERY: 30,
    CONF_DEAD_TIME: 30,
    CONF_PUFFER: 0.7,
    CONF_VENT_RH: 60.0,
}
