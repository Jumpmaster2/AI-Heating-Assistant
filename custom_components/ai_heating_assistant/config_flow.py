"""Config flow, options flow and the subentry flow for heating areas."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .ai_client import AiAuthError, AiError, ClaudeClient
from .const import (
    AREA_DEFAULTS,
    CONF_AI_CHECK_DAYS,
    CONF_AI_EFFORT,
    CONF_AI_MODEL,
    CONF_AREA_NAME,
    CONF_BUDGET,
    CONF_CHECK_INTERVAL,
    CONF_CHECK_MAX_INTERVAL,
    CONF_DEAD_TIME,
    CONF_DEFAULT_TARGET,
    CONF_EMERGENCY_DELTA,
    CONF_EMERGENCY_DURATION,
    CONF_EMERGENCY_ENABLED,
    CONF_EMERGENCY_QUIET,
    CONF_FALLBACK_ERRORS,
    CONF_FROST_TEMP,
    CONF_HEAT_METER,
    CONF_HUMIDITY_SENSOR,
    CONF_LIMITS,
    CONF_MAX_OUTPUT_TOKENS,
    CONF_MAX_TARGET,
    CONF_MIN_OFF,
    CONF_MIN_ON,
    CONF_MIN_TARGET,
    CONF_NIGHT_END,
    CONF_NIGHT_START,
    CONF_NIGHTLY_TIME,
    CONF_OUTDOOR_HUMIDITY,
    CONF_OUTDOOR_TEMP,
    CONF_PHASE_MAX_ERRORS,
    CONF_PREHEAT_RESERVE,
    CONF_PRICE_CACHE_READ,
    CONF_PRICE_CACHE_WRITE,
    CONF_PRICE_INPUT,
    CONF_PRICE_OUTPUT,
    CONF_PUFFER,
    CONF_PUFFER_DOWN,
    CONF_PUFFER_UP,
    CONF_PV_FORECAST,
    CONF_PV_POWER,
    CONF_RECOVERY,
    CONF_REF_HUMIDITY,
    CONF_REF_TEMP,
    CONF_RETURN_ENTITY,
    CONF_RULE_AGREEMENT,
    CONF_RULE_DAYS,
    CONF_SEASON_END,
    CONF_SEASON_START,
    CONF_SHARED_AGREEMENT,
    CONF_SHARED_DAYS,
    CONF_SWITCH,
    CONF_TEMP_SENSOR,
    CONF_THETA_DOWN,
    CONF_THETA_START,
    CONF_THETA_UP,
    CONF_TOO_COLD_MARGIN,
    CONF_TOO_COLD_MINUTES,
    CONF_VACATION_ENTITIES,
    CONF_VACATION_TEMP,
    CONF_VENT_BLOCK,
    CONF_VENT_COOL_MARGIN,
    CONF_VENT_COOL_MIN_TEMP,
    CONF_VENT_MAX_EXCESS,
    CONF_VENT_MIN_AH,
    CONF_VENT_MIN_COOLING,
    CONF_VENT_RH,
    CONF_WEATHER,
    CONF_WINDOW_DELAY,
    CONF_WINDOWS,
    DEFAULTS,
    DOMAIN,
    EFFORT_OPTIONS,
    LEARNED_THETA,
    MODEL_OPTIONS,
    MODEL_PRICE_SUGGESTIONS,
    NAME,
    SECTION_HEATING,
    SECTION_LEARNED,
    SECTION_SENSORS,
    SECTION_START,
    SECTION_VENTILATION,
    SUBENTRY_AREA,
)
from .logic.ai_schema import PARAMS, default_limits
from .logic.physics import parse_day_month

PRICE_KEYS = (CONF_PRICE_INPUT, CONF_PRICE_OUTPUT, CONF_PRICE_CACHE_WRITE, CONF_PRICE_CACHE_READ)


def _number(
    minimum: float, maximum: float, step: float | str, unit: str | None = None
) -> NumberSelector:
    config = NumberSelectorConfig(min=minimum, max=maximum, step=step, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(config)


def _entity(domains: list[str] | None = None, multiple: bool = False) -> EntitySelector:
    config = EntitySelectorConfig(multiple=multiple)
    if domains:
        config["domain"] = domains
    return EntitySelector(config)


def _opt_entity(key: str, values: dict[str, Any]) -> vol.Optional:
    """Optional entity field that can be cleared again."""
    return vol.Optional(key, description={"suggested_value": values.get(key)})


def _req(key: str, values: dict[str, Any]) -> vol.Required:
    return vol.Required(key, default=values.get(key, DEFAULTS.get(key, AREA_DEFAULTS.get(key))))


# ---------------------------------------------------------------- global schemas


def _general_schema(v: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_OUTDOOR_TEMP, default=v.get(CONF_OUTDOOR_TEMP)): _entity(["sensor"]),
            _opt_entity(CONF_OUTDOOR_HUMIDITY, v): _entity(["sensor"]),
            _opt_entity(CONF_WEATHER, v): _entity(["weather"]),
            _opt_entity(CONF_PV_POWER, v): _entity(["sensor"]),
            _opt_entity(CONF_PV_FORECAST, v): _entity(["sensor"]),
            _opt_entity(CONF_HEAT_METER, v): _entity(["sensor"]),
            _req(CONF_SEASON_START, v): TextSelector(),
            _req(CONF_SEASON_END, v): TextSelector(),
            _req(CONF_FROST_TEMP, v): _number(0, 15, 0.5, "°C"),
        }
    )


def _vacation_schema(v: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_VACATION_ENTITIES, default=v.get(CONF_VACATION_ENTITIES, [])
            ): _entity(
                ["input_boolean", "binary_sensor", "switch", "calendar", "schedule"], multiple=True
            ),
            _req(CONF_VACATION_TEMP, v): _number(5, 25, 0.5, "°C"),
            _opt_entity(CONF_RETURN_ENTITY, v): _entity(["input_datetime", "sensor", "datetime"]),
            _req(CONF_PREHEAT_RESERVE, v): _number(0, 720, 5, "min"),
        }
    )


def _rules_schema(v: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _req(CONF_EMERGENCY_ENABLED, v): BooleanSelector(),
            _req(CONF_EMERGENCY_DELTA, v): _number(0.2, 5, 0.1, "K"),
            _req(CONF_EMERGENCY_DURATION, v): _number(5, 240, 5, "min"),
            _req(CONF_EMERGENCY_QUIET, v): _number(0, 240, 5, "min"),
        }
    )


def _ventilation_schema(v: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _req(CONF_VENT_MIN_AH, v): _number(0.1, 5, 0.1, "g/m³"),
            _req(CONF_VENT_MAX_EXCESS, v): _number(0, 15, 0.5, "K"),
            _req(CONF_VENT_MIN_COOLING, v): _number(0, 10, 0.5, "K"),
            _req(CONF_VENT_COOL_MARGIN, v): _number(0, 5, 0.1, "K"),
            _req(CONF_VENT_COOL_MIN_TEMP, v): _number(0, 35, 0.5, "°C"),
            _req(CONF_NIGHT_START, v): _number(0, 23, 1, "h"),
            _req(CONF_NIGHT_END, v): _number(0, 23, 1, "h"),
        }
    )


def _ai_basic_fields(v: dict[str, Any]) -> dict[Any, Any]:
    return {
        _req(CONF_AI_MODEL, v): SelectSelector(
            SelectSelectorConfig(
                options=MODEL_OPTIONS, custom_value=True, mode=SelectSelectorMode.DROPDOWN
            )
        ),
        _req(CONF_NIGHTLY_TIME, v): TimeSelector(),
        _req(CONF_BUDGET, v): _number(0, 100, 0.5, "€"),
    }


def _ai_schema(v: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            **_ai_basic_fields(v),
            _req(CONF_AI_EFFORT, v): SelectSelector(
                SelectSelectorConfig(
                    options=EFFORT_OPTIONS,
                    translation_key="effort",
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            _req(CONF_CHECK_INTERVAL, v): _number(0.5, 48, 0.5, "h"),
            _req(CONF_CHECK_MAX_INTERVAL, v): _number(1, 336, 1, "h"),
            _req(CONF_PRICE_INPUT, v): _number(0, 100, 0.001, "€/MTok"),
            _req(CONF_PRICE_OUTPUT, v): _number(0, 500, 0.001, "€/MTok"),
            _req(CONF_PRICE_CACHE_WRITE, v): _number(0, 100, 0.001, "€/MTok"),
            _req(CONF_PRICE_CACHE_READ, v): _number(0, 100, 0.001, "€/MTok"),
            _req(CONF_MAX_OUTPUT_TOKENS, v): _number(500, 32000, 100),
        }
    )


def _limits_schema(v: dict[str, Any]) -> vol.Schema:
    limits = default_limits()
    for key, value in (v.get(CONF_LIMITS) or {}).items():
        if key in limits:
            limits[key].update(value)
    fields: dict[Any, Any] = {}
    for key, spec in PARAMS.items():
        width = max(abs(spec.min), abs(spec.max)) * 2 + 10
        fields[vol.Required(key)] = section(
            vol.Schema(
                {
                    vol.Required("min", default=limits[key]["min"]): _number(
                        -width, width, 0.01, spec.unit or None
                    ),
                    vol.Required("max", default=limits[key]["max"]): _number(
                        -width, width, 0.01, spec.unit or None
                    ),
                    vol.Required("step", default=limits[key]["step"]): _number(
                        0, width, 0.01, spec.unit or None
                    ),
                }
            ),
            {"collapsed": True},
        )
    return vol.Schema(fields)


def _decision_schema(v: dict[str, Any]) -> vol.Schema:
    """Start value of the heating day rule: set once at setup, learned afterwards."""
    return vol.Schema({_req(CONF_THETA_START, v): _number(5, 25, 0.5, "°C")})


def _coordinator(entry: ConfigEntry) -> Any:
    """The running coordinator of the entry, or None (learned values need it)."""
    if entry.state is not ConfigEntryState.LOADED:
        return None
    return getattr(entry, "runtime_data", None)


def _learned_fields(values: dict[str, float], ranges: dict[str, tuple[float, float]]) -> dict:
    """Fields for learned values that replace the start values once set up."""
    units = {LEARNED_THETA: "°C", CONF_PUFFER: "K"}
    # learned values are not on a step grid
    return {
        vol.Required(key, default=value): _number(*ranges[key], "any", units.get(key, "min"))
        for key, value in values.items()
    }


def _advanced_schema(v: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            _req(CONF_TOO_COLD_MARGIN, v): _number(0, 3, 0.1, "K"),
            _req(CONF_TOO_COLD_MINUTES, v): _number(0, 600, 5, "min"),
            _req(CONF_THETA_UP, v): _number(0, 5, 0.1, "K"),
            _req(CONF_THETA_DOWN, v): _number(0, 5, 0.1, "K"),
            _req(CONF_PUFFER_UP, v): _number(0, 2, 0.05, "K"),
            _req(CONF_PUFFER_DOWN, v): _number(0, 2, 0.05, "K"),
            _req(CONF_SHARED_DAYS, v): _number(1, 120, 1, "d"),
            _req(CONF_SHARED_AGREEMENT, v): _number(0, 100, 1, "%"),
            _req(CONF_RULE_DAYS, v): _number(1, 180, 1, "d"),
            _req(CONF_RULE_AGREEMENT, v): _number(0, 100, 1, "%"),
            _req(CONF_PHASE_MAX_ERRORS, v): _number(0, 30, 1),
            _req(CONF_FALLBACK_ERRORS, v): _number(1, 7, 1),
            _req(CONF_AI_CHECK_DAYS, v): _number(1, 60, 1, "d"),
        }
    )


def _validate_general(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for key in (CONF_SEASON_START, CONF_SEASON_END):
        try:
            parse_day_month(str(user_input.get(key, "")))
        except ValueError:
            errors[key] = "invalid_day_month"
    return errors


def _validate_limits(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    limits: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for key in PARAMS:
        value = user_input.get(key) or {}
        low, high, step = (
            float(value.get("min", 0)),
            float(value.get("max", 0)),
            float(value.get("step", 0)),
        )
        if low > high:
            errors[key] = "min_above_max"
        limits[key] = {"min": low, "max": high, "step": step}
    return limits, errors


async def _check_api_key(hass: Any, api_key: str, model: str) -> str | None:
    """Return an error key or None."""
    try:
        client = await ClaudeClient.create(hass, api_key, model, "auto")
        await client.validate()
    except AiAuthError:
        return "invalid_auth"
    except AiError:
        return "cannot_connect"
    return None


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """Drop cleared optional values."""
    return {k: v for k, v in data.items() if v not in (None, "")}


def _with_price_suggestions(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """When the model changes and prices still match the old model's suggestion, suggest new ones."""
    old_model, new_model = old.get(CONF_AI_MODEL, DEFAULTS[CONF_AI_MODEL]), new.get(CONF_AI_MODEL)
    if new_model == old_model or new_model not in MODEL_PRICE_SUGGESTIONS:
        return new
    old_prices = MODEL_PRICE_SUGGESTIONS.get(str(old_model))
    current = tuple(float(new.get(k, old.get(k, DEFAULTS[k]))) for k in PRICE_KEYS)
    if old_prices is None or tuple(old_prices) == current:
        return {**new, **dict(zip(PRICE_KEYS, MODEL_PRICE_SUGGESTIONS[new_model], strict=True))}
    return new


# ---------------------------------------------------------------- config flow


class AiHeatingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup: global sensors, vacation, AI."""

    VERSION = 1
    MINOR_VERSION = 2  # 2: relay minute options removed, learning steps down doubled

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AiHeatingOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_AREA: AreaSubentryFlow}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_general(user_input)
            if not errors:
                self._options.update(_clean(user_input))
                return await self.async_step_vacation()
        return self.async_show_form(
            step_id="user", data_schema=_general_schema(user_input or {}), errors=errors
        )

    async def async_step_vacation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(_clean(user_input))
            return await self.async_step_decision()
        return self.async_show_form(step_id="vacation", data_schema=_vacation_schema({}))

    async def async_step_decision(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_ai()
        return self.async_show_form(step_id="decision", data_schema=_decision_schema({}))

    async def async_step_ai(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input.pop(CONF_API_KEY, "") or "").strip()
            options = {**DEFAULTS, **self._options, **user_input}
            options = _with_price_suggestions({CONF_AI_MODEL: DEFAULTS[CONF_AI_MODEL]}, options)
            if api_key:
                error = await _check_api_key(self.hass, api_key, str(options[CONF_AI_MODEL]))
                if error:
                    errors["base"] = error
            if not errors:
                options[CONF_LIMITS] = default_limits()
                return self.async_create_entry(
                    title=NAME, data={CONF_API_KEY: api_key}, options=options
                )
        schema = vol.Schema(
            {
                vol.Optional(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                **_ai_basic_fields(user_input or {}),
            }
        )
        return self.async_show_form(step_id="ai", data_schema=schema, errors=errors)

    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Directly continue with the first heating area."""
        entry = result.get("result")
        if entry is None:
            return result
        sub = await self.hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_AREA), context={"source": SOURCE_USER}
        )
        result["next_flow"] = (FlowType.CONFIG_SUBENTRIES_FLOW, sub["flow_id"])
        return result

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change or remove the API key."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input.get(CONF_API_KEY, "") or "").strip()
            if api_key:
                model = str(entry.options.get(CONF_AI_MODEL, DEFAULTS[CONF_AI_MODEL]))
                if error := await _check_api_key(self.hass, api_key, model):
                    errors["base"] = error
            if not errors:
                return self.async_update_and_abort(entry, data_updates={CONF_API_KEY: api_key})
        schema = vol.Schema(
            {
                vol.Optional(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                )
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)


# ---------------------------------------------------------------- options flow


class AiHeatingOptionsFlow(OptionsFlow):
    """All global settings, grouped in a menu."""

    @property
    def _values(self) -> dict[str, Any]:
        return {**DEFAULTS, **self.config_entry.options}

    def _save(self, updates: dict[str, Any], remove: tuple[str, ...] = ()) -> ConfigFlowResult:
        options = {**self.config_entry.options}
        for key in remove:
            options.pop(key, None)
        options.update(updates)
        return self.async_create_entry(data=options)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "vacation",
                "rules",
                "ventilation",
                "ai",
                "ai_limits",
                "advanced",
            ],
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_general(user_input)
            if not errors:
                return self._save(
                    _clean(user_input),
                    remove=(
                        CONF_OUTDOOR_HUMIDITY,
                        CONF_WEATHER,
                        CONF_PV_POWER,
                        CONF_PV_FORECAST,
                        CONF_HEAT_METER,
                    ),
                )
        return self.async_show_form(
            step_id="general",
            data_schema=_general_schema(user_input or self._values),
            errors=errors,
        )

    async def async_step_vacation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(_clean(user_input), remove=(CONF_RETURN_ENTITY,))
        return self.async_show_form(step_id="vacation", data_schema=_vacation_schema(self._values))

    async def async_step_rules(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        return self.async_show_form(step_id="rules", data_schema=_rules_schema(self._values))

    async def async_step_ventilation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        return self.async_show_form(
            step_id="ventilation", data_schema=_ventilation_schema(self._values)
        )

    async def async_step_ai(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if float(user_input[CONF_CHECK_MAX_INTERVAL]) < float(user_input[CONF_CHECK_INTERVAL]):
                errors[CONF_CHECK_MAX_INTERVAL] = "max_below_base"
            else:
                return self._save(_with_price_suggestions(self._values, user_input))
        return self.async_show_form(
            step_id="ai", data_schema=_ai_schema(user_input or self._values), errors=errors
        )

    async def async_step_ai_limits(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            limits, errors = _validate_limits(user_input)
            if not errors:
                return self._save({CONF_LIMITS: limits})
        return self.async_show_form(
            step_id="ai_limits", data_schema=_limits_schema(self._values), errors=errors
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        coordinator = _coordinator(self.config_entry)
        if user_input is not None:
            theta = user_input.pop(LEARNED_THETA, None)
            if coordinator is not None and theta is not None:
                coordinator.set_theta(theta)
            return self._save(user_input)
        schema = _advanced_schema(self._values)
        if coordinator is not None:
            # The start value is set once at setup; afterwards the learned value is edited.
            learned = _learned_fields(
                {LEARNED_THETA: round(coordinator.theta, 2)}, coordinator.learned_ranges()
            )
            schema = vol.Schema({**learned, **schema.schema})
        return self.async_show_form(step_id="advanced", data_schema=schema)


# ---------------------------------------------------------------- heating area subentry


def _area_schema(
    v: dict[str, Any],
    learned: dict[str, float] | None = None,
    ranges: dict[str, tuple[float, float]] | None = None,
) -> vol.Schema:
    """Form of a heating area. Start values only when it is created: an existing area
    shows the learned values instead (``learned``, omitted when unknown)."""

    def req(key: str) -> vol.Required:
        return vol.Required(key, default=v.get(key, AREA_DEFAULTS.get(key)))

    return vol.Schema(
        {
            vol.Required(CONF_AREA_NAME, default=v.get(CONF_AREA_NAME, "")): TextSelector(),
            vol.Required(SECTION_SENSORS): section(
                vol.Schema(
                    {
                        vol.Required(CONF_TEMP_SENSOR, default=v.get(CONF_TEMP_SENSOR)): _entity(
                            ["sensor"]
                        ),
                        _opt_entity(CONF_HUMIDITY_SENSOR, v): _entity(["sensor"]),
                        vol.Optional(CONF_WINDOWS, default=v.get(CONF_WINDOWS, [])): _entity(
                            ["binary_sensor", "input_boolean"], multiple=True
                        ),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required(SECTION_HEATING): section(
                vol.Schema(
                    {
                        _opt_entity(CONF_SWITCH, v): _entity(["switch", "input_boolean"]),
                        req(CONF_DEFAULT_TARGET): _number(5, 30, 0.1, "°C"),
                        req(CONF_MIN_TARGET): _number(5, 30, 0.5, "°C"),
                        req(CONF_MAX_TARGET): _number(5, 30, 0.5, "°C"),
                        req(CONF_MIN_ON): _number(0, 120, 1, "min"),
                        req(CONF_MIN_OFF): _number(0, 120, 1, "min"),
                    }
                ),
                {"collapsed": False},
            ),
            **(_start_section(v) if learned is None else _learned_section(learned, ranges)),
            vol.Required(SECTION_VENTILATION): section(
                vol.Schema(
                    {
                        req(CONF_VENT_RH): _number(30, 95, 1, "%"),
                        _opt_entity(CONF_REF_TEMP, v): _entity(["sensor"]),
                        _opt_entity(CONF_REF_HUMIDITY, v): _entity(["sensor"]),
                        _opt_entity(CONF_VENT_BLOCK, v): _entity(),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def _start_section(v: dict[str, Any]) -> dict[Any, Any]:
    def req(key: str) -> vol.Required:
        return vol.Required(key, default=v.get(key, AREA_DEFAULTS.get(key)))

    return {
        vol.Required(SECTION_START): section(
            vol.Schema(
                {
                    req(CONF_WINDOW_DELAY): _number(0, 60, 1, "min"),
                    req(CONF_RECOVERY): _number(0, 240, 5, "min"),
                    req(CONF_DEAD_TIME): _number(5, 240, 5, "min"),
                    req(CONF_PUFFER): _number(0, 2, 0.1, "K"),
                }
            ),
            {"collapsed": True},
        )
    }


def _learned_section(
    learned: dict[str, float], ranges: dict[str, tuple[float, float]] | None
) -> dict[Any, Any]:
    if not learned or ranges is None:
        return {}
    return {
        vol.Required(SECTION_LEARNED): section(
            vol.Schema(_learned_fields(learned, ranges)), {"collapsed": True}
        )
    }


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {CONF_AREA_NAME: str(user_input.get(CONF_AREA_NAME, "")).strip()}
    for key in (SECTION_SENSORS, SECTION_HEATING, SECTION_START, SECTION_VENTILATION):
        flat.update(user_input.get(key) or {})
    return _clean(flat)


START_KEYS = (CONF_WINDOW_DELAY, CONF_RECOVERY, CONF_DEAD_TIME, CONF_PUFFER)


def keep_start_values(data: Any) -> dict[str, Any]:
    """Start values of an existing area: not changed after it was created."""
    return {k: data[k] for k in START_KEYS if k in data}


def _used_switches(entry: ConfigEntry, exclude: str | None = None) -> set[str]:
    """Heating circuit switches of the areas of an entry, except one area."""
    return {
        sub.data[CONF_SWITCH]
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_AREA
        and sub.subentry_id != exclude
        and sub.data.get(CONF_SWITCH)
    }


def _validate_area(data: dict[str, Any], used_switches: set[str] | None = None) -> dict[str, str]:
    """Errors of an area form; the first problem found is the one reported."""
    errors: dict[str, str] = {}
    if not data.get(CONF_AREA_NAME):
        errors[CONF_AREA_NAME] = "name_required"
    if data.get(CONF_SWITCH) and data[CONF_SWITCH] in (used_switches or set()):
        # two areas switching one circuit would work against each other
        errors.setdefault("base", "switch_in_use")
    low, high = float(data.get(CONF_MIN_TARGET, 16)), float(data.get(CONF_MAX_TARGET, 24))
    if low >= high:
        errors.setdefault("base", "min_above_max")
    elif not low <= float(data.get(CONF_DEFAULT_TARGET, 21)) <= high:
        errors.setdefault("base", "target_out_of_range")
    if bool(data.get(CONF_REF_TEMP)) != bool(data.get(CONF_REF_HUMIDITY)):
        errors.setdefault("base", "reference_incomplete")
    return errors


class AreaSubentryFlow(ConfigSubentryFlow):
    """Add or change one heating area."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        values: dict[str, Any] = {}
        if user_input is not None:
            values = _flatten(user_input)
            errors = _validate_area(values, _used_switches(self._get_entry()))
            if not errors:
                return self.async_create_entry(title=values[CONF_AREA_NAME], data=values)
        return self.async_show_form(step_id="user", data_schema=_area_schema(values), errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        coordinator = _coordinator(entry)
        learned: dict[str, float] = {}
        ranges = None
        if coordinator is not None:
            learned = coordinator.learned_values(subentry.subentry_id)
            ranges = coordinator.learned_ranges()
        errors: dict[str, str] = {}
        values = {CONF_AREA_NAME: subentry.title, **subentry.data}
        if user_input is not None:
            edited = user_input.pop(SECTION_LEARNED, None) or {}
            # the start values were set when the area was created and stay as they are
            values = {**_flatten(user_input), **keep_start_values(subentry.data)}
            errors = _validate_area(values, _used_switches(entry, subentry.subentry_id))
            if not errors:
                if coordinator is not None and edited:
                    coordinator.set_learned(subentry.subentry_id, edited)
                return self.async_update_and_abort(
                    entry, subentry, title=values[CONF_AREA_NAME], data=values
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_area_schema(values, learned, ranges),
            errors=errors,
        )
