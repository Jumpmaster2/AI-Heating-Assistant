"""WebSocket API for the panel: read the configuration, change options, areas and the API key."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import cache
from types import MappingProxyType
from typing import Any

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import EntitySelector, Selector, TimeSelector

from .config_flow import (
    START_KEYS,
    ai_schema,
    area_schema,
    check_api_key,
    decision_schema_expert,
    general_schema,
    keep_start_values,
    learned_fields,
    other_areas,
    rules_schema,
    running_coordinator,
    vacation_schema,
    validate_area,
    ventilation_schema,
    with_price_suggestions,
)
from .const import (
    AREA_DEFAULTS,
    CONF_AI_MODEL,
    CONF_AREA_NAME,
    CONF_CHECK_INTERVAL,
    CONF_CHECK_MAX_INTERVAL,
    CONF_DRAFT_GROUPS,
    CONF_LIMITS,
    CONF_OUTDOOR_TEMP,
    CONF_PROMPTS,
    CONF_SEASON_END,
    CONF_SEASON_START,
    CONF_TEMP_SENSOR,
    CONF_WEATHER,
    DEFAULTS,
    DOMAIN,
    LEARNED_THETA,
    MODEL_PRICE_SUGGESTIONS,
    SUBENTRY_AREA,
)
from .logic.ai_schema import PARAMS, default_limits
from .logic.draft import LEGACY_MODE, LEGACY_WINDOWS, draft_groups
from .logic.physics import parse_day_month
from .logic.prompts import PromptError, clean_prompts, prompt_defaults
from .sensor import AREA_SENSORS

DATA_WS = f"{DOMAIN}_ws_registered"

# entity keys of the integration (unique id suffix) for the panel
ENTITY_KEYS = {
    "heating_day": "binary_sensor",
    "decision_phase": "sensor",
    "ai_last_check": "sensor",
    "ai_next_check": "sensor",
    "ai_cost_month": "sensor",
    "heat_today": "sensor",
    "ai_enabled": "switch",
    "heating_day_override": "select",
}
AREA_ENTITY_KEYS = {
    "climate": "climate",
    "status": "sensor",
    "ventilation": "sensor",
    "ventilation_recommended": "binary_sensor",
    "learning_progress": "sensor",
    "heat_rate": "sensor",
    "cool_rate": "sensor",
    "dead_time": "sensor",
    "overshoot": "sensor",
    "recovery_time": "sensor",
    "outdoor_influence": "sensor",
    "sun_influence": "sensor",
}
REQUIRED_OPTIONS: tuple[str, ...] = ()


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    if hass.data.get(DATA_WS):
        return
    hass.data[DATA_WS] = True
    websocket_api.async_register_command(hass, ws_config)
    websocket_api.async_register_command(hass, ws_save_options)
    websocket_api.async_register_command(hass, ws_save_api_key)
    websocket_api.async_register_command(hass, ws_save_area)
    websocket_api.async_register_command(hass, ws_delete_area)
    websocket_api.async_register_command(hass, ws_save_theta)
    websocket_api.async_register_command(hass, ws_learned)


def _entry(hass: HomeAssistant) -> ConfigEntry | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _fields(schema: vol.Schema) -> dict[str, Selector]:
    """Selectors of a form by key, sections flattened."""
    fields: dict[str, Selector] = {}
    for marker, value in schema.schema.items():
        if isinstance(value, section):
            fields.update(_fields(value.schema))
        else:
            fields[str(marker)] = value
    return fields


@cache
def option_fields() -> dict[str, Selector]:
    """The selectors of the options dialog: one source for types and ranges."""
    values: dict[str, Any] = dict(DEFAULTS)
    fields: dict[str, Selector] = {}
    for schema in (
        general_schema(values, season_text=True),
        vacation_schema(values),
        rules_schema(values),
        ventilation_schema(values),
        ai_schema(values),
        decision_schema_expert(values),
    ):
        fields.update(_fields(schema))
    return fields


@cache
def area_fields() -> dict[str, Selector]:
    return _fields(area_schema({}))


def _spec(selector: Selector) -> dict[str, Any]:
    kind, config = next(iter(selector.serialize()["selector"].items()))
    return {"selector": kind, **dict(config)}


def _coerce(selector: Selector, value: Any, default: Any) -> Any:
    """Validate a value from the panel with the selector of the dialog (None = cleared)."""
    if isinstance(value, str):
        value = value.strip()
    if value is None or value == "":
        return None
    if isinstance(selector, EntitySelector) and selector.config.get("multiple"):
        if not isinstance(value, list):
            raise vol.Invalid("list expected")
        value = [str(v).strip() for v in value if str(v).strip()]
        return selector(value) if value else []
    if isinstance(selector, TimeSelector) and isinstance(value, str) and value.count(":") == 1:
        value = f"{value}:00"
    result = selector(value)
    if (
        isinstance(default, int)
        and not isinstance(default, bool)
        and isinstance(result, float)
        and result.is_integer()
    ):
        return int(result)
    return result


class PanelError(Exception):
    """Error key for the panel, optionally with the field it belongs to."""

    def __init__(self, code: str, field: str | None = None) -> None:
        super().__init__(f"{code}:{field}" if field else code)


def _limits(value: Any, current: Any) -> dict[str, dict[str, float]]:
    limits = default_limits()
    for key, item in (current or {}).items():
        if key in limits and isinstance(item, dict):
            limits[key].update(item)
    if not isinstance(value, dict):
        raise PanelError("invalid_value", CONF_LIMITS)
    for key, item in value.items():
        if key not in PARAMS or not isinstance(item, dict):
            raise PanelError("invalid_value", CONF_LIMITS)
        try:
            new = {k: float(item.get(k, limits[key][k])) for k in ("min", "max", "step")}
        except (TypeError, ValueError) as err:
            raise PanelError("invalid_value", key) from err
        if new["min"] > new["max"]:
            raise PanelError("min_above_max", key)
        if new["step"] < 0:
            raise PanelError("invalid_value", key)
        limits[key] = new
    return limits


def apply_options(current: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """New options from the changed values of one card; raises PanelError."""
    fields = option_fields()
    updates: dict[str, Any] = {}
    removed: set[str] = set()
    for key, value in changes.items():
        if key == CONF_LIMITS:
            updates[key] = _limits(value, current.get(CONF_LIMITS))
            continue
        if key == CONF_PROMPTS:
            try:
                updates[key] = clean_prompts(value)
            except PromptError as err:
                raise PanelError(str(err), CONF_PROMPTS) from err
            continue
        if key not in fields:
            raise PanelError("unknown_option", key)
        try:
            coerced = _coerce(fields[key], value, DEFAULTS.get(key))
        except (vol.Invalid, TypeError, ValueError) as err:
            raise PanelError("invalid_value", key) from err
        if coerced is not None:
            updates[key] = coerced
        elif key in REQUIRED_OPTIONS:
            raise PanelError("required", key)
        elif key in DEFAULTS:
            updates[key] = DEFAULTS[key]
        else:
            removed.add(key)
    updates = with_price_suggestions({**DEFAULTS, **current}, updates)
    options = {k: v for k, v in current.items() if k not in removed}
    options.update(updates)
    merged = {**DEFAULTS, **options}
    if not merged.get(CONF_OUTDOOR_TEMP) and not merged.get(CONF_WEATHER):
        raise PanelError("outdoor_required", CONF_OUTDOOR_TEMP)
    for key in (CONF_SEASON_START, CONF_SEASON_END):
        try:
            parse_day_month(str(merged[key]))
        except ValueError as err:
            raise PanelError("invalid_day_month", key) from err
    if float(merged[CONF_CHECK_MAX_INTERVAL]) < float(merged[CONF_CHECK_INTERVAL]):
        raise PanelError("max_below_base", CONF_CHECK_MAX_INTERVAL)
    return options


def area_data(
    title: str, data: dict[str, Any], others: Sequence[ConfigSubentry] = ()
) -> dict[str, Any]:
    """Validated data of a heating area; raises PanelError. ``others`` are the other
    areas of the entry (names and switches must differ)."""
    fields = area_fields()
    title = title.strip()
    values: dict[str, Any] = {}
    for key, value in data.items():
        # like the dialog: only the fields of the form are kept
        if key == CONF_AREA_NAME or key not in fields:
            continue
        try:
            coerced = _coerce(fields[key], value, AREA_DEFAULTS.get(key))
        except (vol.Invalid, TypeError, ValueError) as err:
            raise PanelError("invalid_value", key) from err
        if coerced is not None:
            values[key] = coerced
    values = {**AREA_DEFAULTS, CONF_AREA_NAME: title, **values}
    if not values.get(CONF_TEMP_SENSOR):
        raise PanelError("required", CONF_TEMP_SENSOR)
    errors = validate_area(values, others)
    if error := errors.get(CONF_AREA_NAME):
        raise PanelError(error)
    if error := errors.get("base"):
        raise PanelError(error)
    return values


def _learned(coordinator: Any, values: Any) -> dict[str, float]:
    """Learned values from the panel, validated with the fields of the dialog."""
    if not isinstance(values, dict):
        raise PanelError("invalid_value", LEARNED_THETA)
    ranges = coordinator.learned_ranges()
    for key in values:
        if key not in ranges:
            raise PanelError("unknown_option", key)
    fields = learned_fields(dict.fromkeys(values, 0.0), ranges)
    result = {}
    for marker, selector in fields.items():
        key = str(marker)
        try:
            result[key] = float(selector(values[key]))
        except (vol.Invalid, TypeError, ValueError) as err:
            raise PanelError("invalid_value", key) from err
    return result


def _area_values(data: Mapping[str, Any]) -> dict[str, Any]:
    """Area data for the editor; combinations of version 1.1.0 as the new fields."""
    values = {k: v for k, v in data.items() if k not in (LEGACY_WINDOWS, LEGACY_MODE)}
    groups = draft_groups(dict(data))
    for i, key in enumerate(CONF_DRAFT_GROUPS):
        values[key] = groups[i] if i < len(groups) else []
    return values


def config_payload(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    registry = er.async_get(hass)
    coordinator = running_coordinator(entry)
    entities: dict[str, str] = {}
    for key, domain in ENTITY_KEYS.items():
        if entity_id := registry.async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{key}"):
            entities[key] = entity_id
    areas = []
    for sub_id, sub in entry.subentries.items():
        if sub.subentry_type != SUBENTRY_AREA:
            continue
        area_entities = {
            key: entity_id
            for key, domain in AREA_ENTITY_KEYS.items()
            if (entity_id := registry.async_get_entity_id(domain, DOMAIN, f"{sub_id}_{key}"))
        }
        areas.append(
            {
                "id": sub_id,
                "title": sub.title,
                "data": _area_values(sub.data),
                "entities": area_entities,
                # values in effect instead of the start values (empty while not running)
                "learned": coordinator.learned_values(sub_id) if coordinator else {},
            }
        )
    options = {**DEFAULTS, **entry.options}
    options[CONF_LIMITS] = _limits({}, entry.options.get(CONF_LIMITS))
    options[CONF_PROMPTS] = entry.options.get(CONF_PROMPTS) or {}
    learned_specs: dict[str, Any] = {}
    if coordinator is not None:
        keys = dict.fromkeys((LEARNED_THETA, *START_KEYS), 0.0)
        learned_specs = {
            str(k): _spec(sel)
            for k, sel in learned_fields(keys, coordinator.learned_ranges()).items()
        }
    return {
        "entry_id": entry.entry_id,
        "options": options,
        "has_api_key": bool(entry.data.get(CONF_API_KEY)),
        "areas": areas,
        "entities": entities,
        "option_specs": {key: _spec(sel) for key, sel in option_fields().items()},
        "area_specs": {key: _spec(sel) for key, sel in area_fields().items()},
        "area_defaults": dict(AREA_DEFAULTS),
        "theta": round(coordinator.theta, 2) if coordinator else None,
        "learned_specs": learned_specs,
        "limit_params": [{"key": p.key, "unit": p.unit} for p in PARAMS.values()],
        "model_prices": {k: list(v) for k, v in MODEL_PRICE_SUGGESTIONS.items()},
        "prompt_defaults": prompt_defaults(),
    }


def _error(connection: websocket_api.ActiveConnection, msg_id: int, err: Exception) -> None:
    connection.send_error(msg_id, "invalid", str(err))


# learned rates of the areas, shown in the panel (their sensors are off by default)
LEARNED_STATS = (
    "heat_rate",
    "cool_rate",
    "overshoot",
    "dead_time",
    "recovery_time",
    "outdoor_influence",
    "sun_influence",
)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/learned"})
@websocket_api.require_admin
@callback
def ws_learned(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    entry = _entry(hass)
    coordinator = running_coordinator(entry) if entry else None
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "AI Heating Assistant is not running")
        return
    descriptions = {d.key: d for d in AREA_SENSORS if d.key in LEARNED_STATS}
    result = {
        area.area_id: {
            key: {"value": d.value_fn(area), "unit": d.native_unit_of_measurement}
            for key, d in descriptions.items()
        }
        for area in coordinator.areas.values()
        if area.has_circuit
    }
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/config"})
@websocket_api.require_admin
@callback
def ws_config(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    entry = _entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_found", "AI Heating Assistant is not set up")
        return
    connection.send_result(msg["id"], config_payload(hass, entry))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/save_options", vol.Required("options"): dict}
)
@websocket_api.require_admin
@callback
def ws_save_options(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    entry = _entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_found", "AI Heating Assistant is not set up")
        return
    try:
        options = apply_options(dict(entry.options), msg["options"])
    except PanelError as err:
        _error(connection, msg["id"], err)
        return
    hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"], config_payload(hass, entry))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save_api_key",
        vol.Optional("api_key", default=""): str,
        vol.Optional("remove", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save_api_key(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Check and store a new API key, or remove it (the key is never sent to the panel)."""
    entry = _entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_found", "AI Heating Assistant is not set up")
        return
    api_key = "" if msg["remove"] else msg["api_key"].strip()
    if not api_key and not msg["remove"]:
        connection.send_error(msg["id"], "invalid", "api_key_required")
        return
    if api_key:
        model = str(entry.options.get(CONF_AI_MODEL, DEFAULTS[CONF_AI_MODEL]))
        if error := await check_api_key(hass, api_key, model):
            connection.send_error(msg["id"], "invalid", error)
            return
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_API_KEY: api_key})
    # a reauth flow started for the old key has nothing left to do
    for flow in list(entry.async_get_active_flows(hass, {SOURCE_REAUTH})):
        hass.config_entries.flow.async_abort(flow["flow_id"])
    connection.send_result(msg["id"], config_payload(hass, entry))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save_area",
        vol.Optional("subentry_id"): str,
        vol.Required("title"): str,
        vol.Required("data"): dict,
        vol.Optional("learned"): dict,
    }
)
@websocket_api.require_admin
@callback
def ws_save_area(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    entry = _entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_found", "AI Heating Assistant is not set up")
        return
    sub_id = msg.get("subentry_id")
    subentry = entry.subentries.get(sub_id) if sub_id else None
    if sub_id and (subentry is None or subentry.subentry_type != SUBENTRY_AREA):
        connection.send_error(msg["id"], "not_found", "area not found")
        return
    coordinator = running_coordinator(entry)
    try:
        data = area_data(msg["title"], msg["data"], other_areas(entry, sub_id))
        learned = (
            _learned(coordinator, msg["learned"])
            if subentry is not None and coordinator is not None and "learned" in msg
            else {}
        )
    except PanelError as err:
        _error(connection, msg["id"], err)
        return
    title = data[CONF_AREA_NAME]
    if subentry is not None:
        # the start values were set when the area was created and stay as they are
        data = {k: v for k, v in data.items() if k not in START_KEYS}
        data.update(keep_start_values(subentry.data))
        if learned:
            coordinator.set_learned(subentry.subentry_id, learned)
        hass.config_entries.async_update_subentry(entry, subentry, data=data, title=title)
    else:
        subentry = ConfigSubentry(
            data=MappingProxyType(data), subentry_type=SUBENTRY_AREA, title=title, unique_id=None
        )
        hass.config_entries.async_add_subentry(entry, subentry)
        sub_id = subentry.subentry_id
    connection.send_result(
        msg["id"], {"subentry_id": sub_id, "config": config_payload(hass, entry)}
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/save_theta", vol.Required("theta"): vol.Any(int, float, str)}
)
@websocket_api.require_admin
@callback
def ws_save_theta(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Change the learned theta (its start value is only set up once)."""
    entry = _entry(hass)
    coordinator = running_coordinator(entry) if entry else None
    if entry is None or coordinator is None:
        connection.send_error(msg["id"], "not_found", "AI Heating Assistant is not running")
        return
    try:
        theta = _learned(coordinator, {LEARNED_THETA: msg["theta"]})[LEARNED_THETA]
    except PanelError as err:
        _error(connection, msg["id"], err)
        return
    coordinator.set_theta(theta)
    connection.send_result(msg["id"], config_payload(hass, entry))


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/delete_area", vol.Required("subentry_id"): str}
)
@websocket_api.require_admin
@callback
def ws_delete_area(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    entry = _entry(hass)
    subentry = entry.subentries.get(msg["subentry_id"]) if entry else None
    if entry is None or subentry is None or subentry.subentry_type != SUBENTRY_AREA:
        connection.send_error(msg["id"], "not_found", "area not found")
        return
    hass.config_entries.async_remove_subentry(entry, msg["subentry_id"])
    connection.send_result(msg["id"], config_payload(hass, entry))
