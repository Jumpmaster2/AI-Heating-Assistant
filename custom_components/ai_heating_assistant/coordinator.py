"""Central engine: control loop, learning, heating day decision and AI scheduling."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_API_KEY,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .ai_client import AiError, ClaudeClient
from .const import (
    CONF_AI_CHECK_DAYS,
    CONF_AI_EFFORT,
    CONF_AI_MODEL,
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
    CONF_MIN_OFF,
    CONF_MIN_ON,
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
    EVENT_LOGBOOK,
    LOGGER,
    NAME,
    STORAGE_VERSION,
    SUBENTRY_AREA,
    TICK_SECONDS,
)
from .logic import heating_day as hd
from .logic.ai_policy import (
    Budget,
    Prices,
    cost_eur,
    estimate_cost,
    next_interval_hours,
    overheat_issue,
    update_stable_count,
)
from .logic.ai_schema import (
    CHECK_SCHEMA,
    GLOBAL,
    NIGHTLY_SCHEMA,
    PARAMS,
    AnswerError,
    default_limits,
    validate_check,
    validate_nightly,
)
from .logic.controller import (
    AreaRuntime,
    AreaSettings,
    AreaStatus,
    ControlDecision,
    ControlInput,
    ControlParams,
    LearnedValues,
    emergency_limit,
    preheat_start,
    step,
)
from .logic.energy import HeatMeter, to_kwh
from .logic.learning import (
    DEAD_TIME_BOUNDS,
    P_START,
    RECOVERY_BOUNDS,
    AreaLearner,
    Ewma,
    Sample,
)
from .logic.physics import clamp, in_season, parse_day_month
from .logic.prompts import check_messages, nightly_messages, r
from .logic.start_values import LEARNED_BOUNDS, apply_start_values, read_record
from .logic.sun import (
    FORECAST_TRUST,
    Point,
    SunScale,
    clear_sky_index,
    cloud_factor,
    cloud_pct,
    expected_now,
    planning_pv,
    sensor_point,
    solar_elevation,
    weather_points,
)
from .logic.ventilation import VentilationInput, VentilationResult, VentilationSettings, recommend
from .messages import text

SAVE_DELAY = 30
HISTORY_DAYS = 60
EXTERNAL_SWITCH_GRACE = 120  # s within which a switch change counts as our own command
CHECK_COLD_MARGIN = 0.3
OVERHEAT_MARGIN = 0.2  # K above target tolerated before heat counts as wasted
OVERHEAT_AFTER_S = 4 * 3600.0  # s after switch-off in which overheating is due to heating
SUN_OVERHEAT_KW = 0.3  # PV power from which overheating counts as caused by sun as well
CHECK_HISTORY = 6  # earlier checks shown to the AI
SAVE_EVERY_TICKS = 10
WEATHER_PV_REFRESH_S = 1800  # s between hourly forecast requests for the expected sun
VIRTUAL_MIN_COOL_UPDATES = 24  # model updates without heating before the virtual room is trusted
TWILIGHT_INDEX = 0.05  # clear sky index (about 5 degrees elevation) below which PV counts as 0
PV_NEGLIGIBLE_KW = 0.05  # expected PV power below which a missing PV value counts as 0
PV_MISSING_WARN_MIN = 60.0  # daytime minutes without a PV value before a warning
INACTIVE_STATES = {"off", "idle", STATE_UNAVAILABLE, STATE_UNKNOWN, "none", ""}


@dataclass
class Area:
    """Runtime representation of one heating area (config subentry)."""

    area_id: str
    name: str
    prompt_id: str
    cfg: dict[str, Any]
    params: ControlParams
    settings: AreaSettings
    learner: AreaLearner | None
    runtime: AreaRuntime
    target: float
    hvac_on: bool
    day: hd.DayAreaStats
    check: dict[str, float]
    temp: float | None = None
    humidity: float | None = None
    window_open: bool = False
    switch_on: bool = False
    switch_available: bool = False
    last_switch_change: float | None = None
    on_since: float | None = None
    off_at: float | None = None  # last real switch-off seen (not restored after a restart)
    commanded: tuple[bool, float] | None = None
    effective_target: float | None = None
    vacation: bool = False
    preheat: bool = False
    decision: ControlDecision | None = None
    ventilation: VentilationResult | None = None
    status: str = AreaStatus.IDLE
    learned_values: LearnedValues = field(default_factory=LearnedValues)
    start: dict[str, float] = field(default_factory=dict)  # start values last applied

    @property
    def has_circuit(self) -> bool:
        return bool(self.cfg.get(CONF_SWITCH))

    @property
    def airing(self) -> bool:
        rt = self.runtime
        return self.window_open or rt.window_paused or rt.recovery_until is not None


def _start_values(cfg: dict[str, Any]) -> dict[str, float]:
    """Configured start values in the units the learner and the parameters use."""
    return {
        "dead_time": float(cfg.get(CONF_DEAD_TIME, 30)) * 60,
        "recovery": float(cfg.get(CONF_RECOVERY, 30)) * 60,
        "window_delay_min": float(cfg.get(CONF_WINDOW_DELAY, 5)),
        "puffer": float(cfg.get(CONF_PUFFER, 0.7)),
    }


# Divisor and unit for the logbook: seconds are shown as minutes.
_START_UNITS = {
    "dead_time": (60.0, "min"),
    "recovery": (60.0, "min"),
    "window_delay_min": (1.0, "min"),
    "puffer": (1.0, "K"),
}

# Start value of the area configuration -> learned value or parameter that replaces it.
LEARNED_NAMES = {
    CONF_WINDOW_DELAY: "window_delay_min",
    CONF_RECOVERY: "recovery",
    CONF_DEAD_TIME: "dead_time",
    CONF_PUFFER: "puffer",
}


def _new_check_stats() -> dict[str, float]:
    return {
        "minutes": 0.0,
        "cold_min": 0.0,
        "max_over": -99.0,
        "cycles": 0.0,
        "on_min": 0.0,
        "min_t": 99.0,
        "max_t": -99.0,
        "window_min": 0.0,
        "over_kh": 0.0,
        "sun_over_kh": 0.0,
        "deg_h": 0.0,
    }


type AiHeatingConfigEntry = ConfigEntry[HeatingCoordinator]


class HeatingCoordinator(DataUpdateCoordinator[int]):
    """Runs the control loop every minute and on relevant state changes."""

    config_entry: AiHeatingConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AiHeatingConfigEntry) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=TICK_SECONDS),
            always_update=True,
            request_refresh_debouncer=Debouncer(hass, LOGGER, cooldown=3, immediate=False),
        )
        self.store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.areas: dict[str, Area] = {}
        self.day_state: dict[str, Any] = {}
        self.ai_state: dict[str, Any] = {}
        self.budget = Budget()
        self.meter = HeatMeter()
        self.client: ClaudeClient | None = None
        self.global_device_id: str | None = None
        self.outdoor_temp: float | None = None
        self.pv_kw: float | None = 0.0  # None: sensor configured but without a value by day
        self.pv_assumed: float = 0.0  # pv_kw, or the expected power while it is unknown
        self._pv_measured = False  # pv_kw comes from the sensor (calibration allowed)
        self._pv_missing_min = 0.0  # daytime minutes the PV sensor had no value
        self._pv_warned = False
        self.sun_scale = SunScale()
        self._pv_points: list[Point] = []
        self._hourly: list[dict[str, Any]] = []
        self._hourly_ts: float | None = None
        self.season_active = False
        self.vacation = False
        self._last_tick: float | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._unsub_check: Callable[[], None] | None = None
        self._deciding = False
        self._checking = False
        self._tick_count = 0
        self._unit_warned: set[str] = set()  # entities already warned about an odd unit

    # ------------------------------------------------------------------ config

    @property
    def opts(self) -> dict[str, Any]:
        return {**DEFAULTS, **self.config_entry.options}

    def opt(self, key: str) -> Any:
        return self.opts.get(key, DEFAULTS.get(key))

    @property
    def language(self) -> str:
        return self.hass.config.language or "en"

    @property
    def prices(self) -> Prices:
        return Prices(
            float(self.opt(CONF_PRICE_INPUT)),
            float(self.opt(CONF_PRICE_OUTPUT)),
            float(self.opt(CONF_PRICE_CACHE_WRITE)),
            float(self.opt(CONF_PRICE_CACHE_READ)),
        )

    @property
    def limits(self) -> dict[str, dict[str, float]]:
        limits = default_limits()
        for key, value in (self.opt(CONF_LIMITS) or {}).items():
            if key in limits and isinstance(value, dict):
                limits[key].update(
                    {k: float(v) for k, v in value.items() if k in ("min", "max", "step")}
                )
        return limits

    @property
    def ai_configured(self) -> bool:
        return bool(self.config_entry.data.get(CONF_API_KEY))

    @property
    def ai_enabled(self) -> bool:
        return self.ai_configured and bool(self.ai_state.get("enabled", True))

    @property
    def theta(self) -> float:
        return float(self.day_state.get("theta", self.opt(CONF_THETA_START)))

    @property
    def phase(self) -> hd.Phase:
        try:
            return hd.Phase(self.day_state.get("phase", hd.Phase.AI_LEADS))
        except ValueError:
            return hd.Phase.AI_LEADS

    @property
    def current_day(self) -> dict[str, Any] | None:
        return self.day_state.get("current")

    @property
    def heating_day(self) -> bool:
        """Today's decision. Without a valid decision heating is allowed (safe default)."""
        override = self.day_state.get("override", hd.Override.AUTO)
        if override == hd.Override.HEAT:
            return True
        if override == hd.Override.OFF:
            return False
        current = self.current_day
        if current is None:
            return True
        return bool(current.get("heat", True))

    def _eval_settings(self) -> hd.EvalSettings:
        limits = self.limits
        return hd.EvalSettings(
            too_cold_minutes=float(self.opt(CONF_TOO_COLD_MINUTES)),
            theta_up=float(self.opt(CONF_THETA_UP)),
            theta_down=float(self.opt(CONF_THETA_DOWN)),
            puffer_up=float(self.opt(CONF_PUFFER_UP)),
            puffer_down=float(self.opt(CONF_PUFFER_DOWN)),
            theta_min=limits["theta"]["min"],
            theta_max=limits["theta"]["max"],
            puffer_min=limits["puffer"]["min"],
            puffer_max=limits["puffer"]["max"],
        )

    def _phase_settings(self) -> hd.PhaseSettings:
        return hd.PhaseSettings(
            shared_min_days=int(self.opt(CONF_SHARED_DAYS)),
            shared_min_agreement=float(self.opt(CONF_SHARED_AGREEMENT)) / 100,
            shared_max_rule_errors=int(self.opt(CONF_PHASE_MAX_ERRORS)),
            rule_min_days=int(self.opt(CONF_RULE_DAYS)),
            rule_min_agreement=float(self.opt(CONF_RULE_AGREEMENT)) / 100,
            rule_max_rule_errors=int(self.opt(CONF_PHASE_MAX_ERRORS)),
            fallback_errors_7d=int(self.opt(CONF_FALLBACK_ERRORS)),
            ai_check_every_days=int(self.opt(CONF_AI_CHECK_DAYS)),
        )

    # ------------------------------------------------------------------ setup

    async def _async_setup(self) -> None:
        """Load stored state, build areas, start timers and listeners."""
        stored = await self.store.async_load() or {}
        self.day_state = stored.get("day", {})
        self.ai_state = stored.get("ai", {})
        self.budget = Budget.from_dict(self.ai_state.get("budget"))
        self.meter = HeatMeter.from_dict(stored.get("meter"))
        scale = (stored.get("sun") or {}).get("scale")
        self.sun_scale = SunScale(float(scale) if isinstance(scale, int | float) else None)
        stored_areas: dict[str, Any] = stored.get("areas", {})

        for index, subentry in enumerate(
            s for s in self.config_entry.subentries.values() if s.subentry_type == SUBENTRY_AREA
        ):
            self.areas[subentry.subentry_id] = self._build_area(
                subentry.subentry_id,
                subentry.title,
                dict(subentry.data),
                stored_areas.get(subentry.subentry_id, {}),
                index,
            )

        if self.ai_configured:
            self.client = await ClaudeClient.create(
                self.hass,
                self.config_entry.data[CONF_API_KEY],
                str(self.opt(CONF_AI_MODEL)),
                str(self.opt(CONF_AI_EFFORT)),
            )

        self._register_listeners()
        nightly = _parse_time(str(self.opt(CONF_NIGHTLY_TIME)))
        self._unsubs.append(
            async_track_time_change(
                self.hass,
                self._nightly_callback,
                hour=nightly.hour,
                minute=nightly.minute,
                second=nightly.second,
            )
        )
        self._restore_check_schedule()
        self._save()  # applied start values are on record from now on

    def _build_area(
        self, area_id: str, title: str, cfg: dict[str, Any], stored: dict[str, Any], index: int
    ) -> Area:
        start = _start_values(cfg)
        params = ControlParams.from_dict(
            stored.get("params"),
            window_delay_min=start["window_delay_min"],
            puffer=start["puffer"],
        )
        settings = AreaSettings(
            min_on_s=float(cfg.get(CONF_MIN_ON, 10)) * 60,
            min_off_s=float(cfg.get(CONF_MIN_OFF, 10)) * 60,
            emergency_enabled=bool(self.opt(CONF_EMERGENCY_ENABLED)),
            emergency_delta=float(self.opt(CONF_EMERGENCY_DELTA)),
            emergency_duration_s=float(self.opt(CONF_EMERGENCY_DURATION)) * 60,
            emergency_window_quiet_s=float(self.opt(CONF_EMERGENCY_QUIET)) * 60,
        )
        learner = (
            AreaLearner.from_dict(stored.get("learner"), start["dead_time"], start["recovery"])
            if cfg.get(CONF_SWITCH)
            else None
        )
        area = Area(
            area_id=area_id,
            name=title,
            prompt_id=f"a{index + 1}",
            cfg=cfg,
            params=params,
            settings=settings,
            learner=learner,
            runtime=AreaRuntime.from_dict(stored.get("runtime")),
            # Without a circuit there is no thermostat card: the configured value is the reference.
            target=float(
                stored.get("target", cfg.get(CONF_DEFAULT_TARGET, 21.0))
                if cfg.get(CONF_SWITCH)
                else cfg.get(CONF_DEFAULT_TARGET, 21.0)
            ),
            hvac_on=bool(stored.get("hvac_on", True)),
            day=hd.DayAreaStats.from_dict(stored.get("day")),
            check=stored.get("check") or _new_check_stats(),
        )
        self._apply_start_values(area, start, stored.get("start"))
        return area

    def _apply_start_values(self, area: Area, configured: dict[str, float], stored: Any) -> None:
        """A start value changed in the configuration replaces the stored one, and the
        configuration is then on record (see ``logic.start_values``)."""
        applied = apply_start_values(configured, read_record(stored), area.learner, area.params)
        if applied:
            self._forget_check_history(area)
        for name, old, new in applied:
            divisor, unit = _START_UNITS[name]
            self._log(
                "start_value",
                area,
                name=text(self.language, name),
                old=f"{old / divisor:g}",
                new=f"{new / divisor:g}",
                unit=unit,
            )
        area.start = configured

    def _forget_check_history(self, area: Area) -> None:
        """Earlier checks of an area say nothing about its values after a reset."""
        for entry in self.ai_state.get("check_history", []):
            entry.get("areas", {}).pop(area.prompt_id, None)

    def _register_listeners(self) -> None:
        watched: set[str] = set()
        for key in (CONF_OUTDOOR_TEMP, CONF_RETURN_ENTITY):
            if self.opt(key):
                watched.add(self.opt(key))
        watched.update(self.opt(CONF_VACATION_ENTITIES) or [])
        switches: dict[str, str] = {}
        for area in self.areas.values():
            for key in (CONF_TEMP_SENSOR, CONF_VENT_BLOCK):
                if area.cfg.get(key):
                    watched.add(area.cfg[key])
            watched.update(area.cfg.get(CONF_WINDOWS) or [])
            if area.has_circuit:
                switches[area.cfg[CONF_SWITCH]] = area.area_id
        self._switch_map = switches
        if watched:
            self._unsubs.append(
                async_track_state_change_event(self.hass, sorted(watched), self._on_input_change)
            )
        if switches:
            self._unsubs.append(
                async_track_state_change_event(self.hass, sorted(switches), self._on_switch_change)
            )

    @callback
    def _on_input_change(self, event: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(self.async_request_refresh(), eager_start=True)

    @callback
    def _on_switch_change(self, event: Event[EventStateChangedData]) -> None:
        area = self.areas.get(self._switch_map.get(event.data["entity_id"], ""))
        old: State | None = event.data["old_state"]
        new: State | None = event.data["new_state"]
        if area is None or new is None or old is None:
            return
        if (
            old.state not in ("on", "off")
            or new.state not in ("on", "off")
            or old.state == new.state
        ):
            return
        turned_on = new.state == STATE_ON
        ts = new.last_changed.timestamp()
        run_hours = (ts - area.on_since) / 3600 if (not turned_on and area.on_since) else 0.0
        if area.learner is not None:
            area.learner.on_switch(ts, area.temp, turned_on, run_hours)
        area.on_since = ts if turned_on else None
        area.off_at = None if turned_on else ts
        if turned_on:
            area.check["cycles"] = area.check.get("cycles", 0) + 1
        own = (
            area.commanded is not None
            and area.commanded[0] == turned_on
            and ts - area.commanded[1] < EXTERNAL_SWITCH_GRACE
        )
        area.commanded = None
        if not own:
            if turned_on:
                area.day.manual_heat = True
            self._log(
                "external_switch", area, state=text(self.language, "on" if turned_on else "off")
            )
        self._save()
        self.hass.async_create_task(self.async_request_refresh(), eager_start=True)

    async def async_shutdown(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._unsub_check:
            self._unsub_check()
            self._unsub_check = None
        await self.store.async_save(self._data_to_save())
        await super().async_shutdown()

    # ------------------------------------------------------------------ helpers

    def _state(self, entity_id: str | None) -> State | None:
        return self.hass.states.get(entity_id) if entity_id else None

    def _float(self, entity_id: str | None) -> float | None:
        state = self._state(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _temp(self, entity_id: str | None) -> float | None:
        """Temperature of a sensor in °C, whatever unit the sensor reports."""
        value = self._float(entity_id)
        if value is None:
            return None
        state = self._state(entity_id)
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
        return self._to_celsius(value, unit, str(entity_id))

    def _to_celsius(self, value: float, unit: str | None, source: str) -> float | None:
        """Convert a temperature to °C. Without a unit the unit system of HA applies;
        a unit that is no temperature unit makes the value unknown (warned once)."""
        unit = unit or self.hass.config.units.temperature_unit
        if unit == UnitOfTemperature.CELSIUS:
            return value
        try:
            return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
        except HomeAssistantError:
            if source not in self._unit_warned:
                self._unit_warned.add(source)
                LOGGER.warning(
                    "%s reports the unit %r instead of a temperature unit (°C, °F or K); "
                    "its value is ignored",
                    source,
                    unit,
                )
            return None

    def _is_on(self, entity_id: str | None) -> bool:
        state = self._state(entity_id)
        return state is not None and state.state == STATE_ON

    def _is_active(self, entity_id: str | None) -> bool:
        """True for 'on' and any running state (e.g. an air conditioner in cool mode)."""
        state = self._state(entity_id)
        return state is not None and state.state not in INACTIVE_STATES

    def _pv_kw(self) -> float | None:
        """Current PV power in kW. None if the sensor is configured but has no value."""
        entity_id = self.opt(CONF_PV_POWER)
        if not entity_id:
            return 0.0
        state = self._state(entity_id)
        value = self._float(entity_id)
        if value is None:
            return None
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
        if unit == UnitOfPower.KILO_WATT:
            return max(0.0, value)
        if unit == UnitOfPower.MEGA_WATT:
            return max(0.0, value * 1000)
        return max(0.0, value / 1000)

    def _return_ts(self) -> float | None:
        state = self._state(self.opt(CONF_RETURN_ENTITY))
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        stamp = state.attributes.get("timestamp")
        if isinstance(stamp, int | float) and state.attributes.get("has_date", True):
            return float(stamp)
        parsed = dt_util.parse_datetime(state.state)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
        return parsed.timestamp()

    def _season(self) -> bool:
        try:
            start = parse_day_month(str(self.opt(CONF_SEASON_START)))
            end = parse_day_month(str(self.opt(CONF_SEASON_END)))
        except ValueError:
            return True
        return in_season(dt_util.now().date(), start, end)

    def climate_entity_id(self, area: Area) -> str | None:
        return er.async_get(self.hass).async_get_entity_id(
            "climate", DOMAIN, f"{area.area_id}_climate"
        )

    @callback
    def _log(self, key: str, area: Area | None = None, **kwargs: Any) -> None:
        message = text(self.language, key, **kwargs)
        data: dict[str, Any] = {"message": message, "name": area.name if area else NAME}
        if area is not None and (entity_id := self.climate_entity_id(area)):
            data[ATTR_ENTITY_ID] = entity_id
        self.hass.bus.async_fire(EVENT_LOGBOOK, data)
        LOGGER.info("%s: %s", data["name"], message)

    def _save(self) -> None:
        self.store.async_delay_save(self._data_to_save, SAVE_DELAY)

    def _data_to_save(self) -> dict[str, Any]:
        self.ai_state["budget"] = self.budget.as_dict()
        return {
            "areas": {
                area.area_id: {
                    "target": area.target,
                    "hvac_on": area.hvac_on,
                    "params": area.params.as_dict(),
                    "learner": area.learner.as_dict() if area.learner else None,
                    "runtime": area.runtime.as_dict(),
                    "day": area.day.as_dict(),
                    "check": area.check,
                    "start": area.start,
                }
                for area in self.areas.values()
            },
            "day": self.day_state,
            "ai": self.ai_state,
            "sun": {"scale": self.sun_scale.value},
            "meter": self.meter.as_dict(),
        }

    def diagnostics(self) -> dict[str, Any]:
        return self._data_to_save()

    # ------------------------------------------------------------------ control loop

    async def _async_update_data(self) -> int:
        now = dt_util.utcnow()
        ts = now.timestamp()
        minutes = 0.0 if self._last_tick is None else clamp((ts - self._last_tick) / 60, 0.0, 5.0)
        self._last_tick = ts

        self.outdoor_temp = self._temp(self.opt(CONF_OUTDOOR_TEMP))
        self.pv_kw = self._pv_kw()
        self._pv_measured = self.pv_kw is not None
        await self._update_pv_forecast(ts)
        if self.pv_kw is None:
            self._pv_missing(minutes, ts)
            if self._pv_negligible(ts):
                self.pv_kw = 0.0  # inverter asleep: no sun worth mentioning, no power
        else:
            self._pv_missing_min, self._pv_warned = 0.0, False
        self.pv_assumed = self.pv_kw if self.pv_kw is not None else (self._pv_estimate(ts) or 0.0)
        self.season_active = self._season()
        self.vacation = any(self._is_on(e) for e in self.opt(CONF_VACATION_ENTITIES) or [])
        return_ts = self._return_ts() if self.vacation else None
        heating_day = self.heating_day

        for area in self.areas.values():
            await self._tick_area(area, ts, minutes, heating_day, return_ts)
        self._update_meter(ts, minutes)

        # Missing or expired decision (first start, HA was down at the nightly run).
        # Started after the areas were read so the decision sees current values.
        if self.season_active and not self._deciding and self._decision_expired(now):
            self.config_entry.async_create_background_task(
                self.hass, self.async_decide_heating_day("startup"), f"{DOMAIN} heating day"
            )

        self._tick_count += 1
        if self._tick_count % SAVE_EVERY_TICKS == 0:
            self._save()
        return self._tick_count

    def _update_meter(self, ts: float, minutes: float) -> None:
        """Heating demand of this tick and the latest heat meter reading."""
        entity_id = self.opt(CONF_HEAT_METER)
        if not entity_id:
            if self.meter.entity:
                self.meter = HeatMeter()  # set again later: the gap would count as one span
            return
        if self.meter.entity != entity_id:
            self.meter = HeatMeter(entity=entity_id)  # readings of another meter do not compare
        controlled = [a for a in self.areas.values() if a.has_circuit and a.hvac_on]
        if self.season_active and controlled and self.outdoor_temp is not None and minutes > 0:
            # The meter covers all circuits: the demand is the mean over the areas.
            diff = sum(
                max(0.0, (a.effective_target or a.target) - self.outdoor_temp) for a in controlled
            ) / len(controlled)
            self.meter.add_demand(diff * minutes / 60)
        # Calendar periods roll before taking the value: a reading that arrives after
        # midnight already belongs to the new day.
        today = dt_util.now().date()
        self.meter.roll(
            "today", today.isoformat(), "yesterday", (today - timedelta(days=1)).isoformat()
        )
        first = today.replace(day=1)
        self.meter.roll(
            "month",
            first.strftime("%Y-%m"),
            "last_month",
            (first - timedelta(days=1)).strftime("%Y-%m"),
        )
        value = self._float(entity_id)
        state = self._state(entity_id)
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
        kwh = None if value is None else to_kwh(value, unit)
        if kwh is not None:
            self.meter.update(kwh, ts)
            for name in ("check", "day", "today", "month"):  # periods start with the first reading
                if name not in self.meter.baselines:
                    self.meter.rebase(name)

    def _heat_payload(self) -> dict[str, Any] | None:
        """Measured heat since the last check, between two meter readings."""
        if not self.opt(CONF_HEAT_METER):
            return None
        span = self.meter.since("check")
        if span is None:
            return None
        return {
            "kwh": r(span.kwh, 1),
            "hours": r(span.hours, 1),
            "kwh_per_kh": r(span.kwh_per_kh, 3),
        }

    def _decision_expired(self, now: datetime) -> bool:
        current = self.current_day
        if current is None:
            return True
        until = dt_util.parse_datetime(str(current.get("valid_until", "")))
        return until is None or until <= now

    async def _update_pv_forecast(self, ts: float) -> None:
        """Expected PV power of the next hours. Empty: only the current PV power is used."""
        self._pv_points = []
        if not self.opt(CONF_PV_POWER):
            return
        if forecast_id := self.opt(CONF_PV_FORECAST):
            state = self._state(forecast_id)
            unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
            if (point := sensor_point(ts, self._float(forecast_id), unit)) is not None:
                self._pv_points = [point]
            return
        weather = self._state(self.opt(CONF_WEATHER))
        if weather is None:
            return
        lat, lon = self.hass.config.latitude, self.hass.config.longitude
        if self._pv_measured and self.pv_kw is not None:
            self.sun_scale.update(self.pv_kw, self._sun_index(ts), self._cloud_now())
        if self.sun_scale.value is None:
            return
        if self._hourly_ts is None or ts - self._hourly_ts >= WEATHER_PV_REFRESH_S:
            self._hourly_ts = ts
            self._hourly = await self._forecast("hourly")
        self._pv_points = weather_points(self._hourly, self.sun_scale.value, lat, lon)

    def _sun_index(self, ts: float) -> float:
        """Clear sky index at the configured location (0 while the sun is down)."""
        return clear_sky_index(
            solar_elevation(ts, self.hass.config.latitude, self.hass.config.longitude)
        )

    def _cloud_now(self) -> float | None:
        weather = self._state(self.opt(CONF_WEATHER))
        if weather is None:
            return None
        return cloud_pct({"condition": weather.state, **weather.attributes})

    def _pv_estimate(self, ts: float) -> float | None:
        """PV power expected now: from the forecast points, else from sun position, clouds
        and the learned clear sky scale; None without any basis."""
        if (expected := expected_now(self._pv_points, ts)) is not None:
            return expected
        scale = self.sun_scale.value
        index = self._sun_index(ts)
        if scale is None:
            return None
        if index <= 0:
            return 0.0
        cloud = self._cloud_now()
        return scale * index * cloud_factor(100.0 if cloud is None else cloud) * FORECAST_TRUST

    def _pv_negligible(self, ts: float) -> bool:
        """A missing PV value may be read as zero: the sun is low or little is expected."""
        if self._sun_index(ts) < TWILIGHT_INDEX:
            return True
        expected = self._pv_estimate(ts)
        return expected is not None and expected < PV_NEGLIGIBLE_KW

    def _pv_missing(self, minutes: float, ts: float) -> None:
        """Warn once when the PV sensor has had no value for a while by day."""
        if self._sun_index(ts) < TWILIGHT_INDEX:
            return
        self._pv_missing_min += minutes
        if self._pv_missing_min >= PV_MISSING_WARN_MIN and not self._pv_warned:
            self._pv_warned = True
            LOGGER.warning(
                "PV power sensor %s has had no value for %.0f minutes by day: sun and model "
                "are not learned until it delivers again",
                self.opt(CONF_PV_POWER),
                self._pv_missing_min,
            )

    def _learned_values(self, area: Area, run_hours: float, ts: float) -> LearnedValues:
        learner = area.learner
        if learner is None:
            return LearnedValues()
        diff = (
            (area.temp - self.outdoor_temp)
            if (area.temp is not None and self.outdoor_temp is not None)
            else 10.0
        )
        model = learner.model
        # Cooling over the lead time uses the sun expected in that time, not only the
        # current PV power. Heating rates (preheating) keep the current value.
        pv_now = self.pv_assumed
        lead_s = learner.dead_time.value * area.params.lead_factor
        pv_plan = planning_pv(ts, pv_now, self._pv_points, lead_s)
        return LearnedValues(
            cool_rate_kph=model.cool_rate(diff, pv_plan, area.params.sun_factor),
            heat_rate_kph=model.heat_rate(diff, pv_now, area.params.sun_factor),
            dead_time_s=learner.dead_time.value,
            recovery_s=learner.recovery.value,
            overshoot_k=learner.expected_overshoot(run_hours),
            pv_plan_kw=round(pv_plan, 2),
        )

    async def _tick_area(
        self, area: Area, ts: float, minutes: float, heating_day: bool, return_ts: float | None
    ) -> None:
        cfg = area.cfg
        area.temp = self._temp(cfg.get(CONF_TEMP_SENSOR))
        area.humidity = self._float(cfg.get(CONF_HUMIDITY_SENSOR))
        area.window_open = any(self._is_on(w) for w in cfg.get(CONF_WINDOWS) or [])

        if area.has_circuit:
            switch_state = self._state(cfg[CONF_SWITCH])
            area.switch_available = switch_state is not None and switch_state.state in ("on", "off")
            area.switch_on = switch_state is not None and switch_state.state == STATE_ON
            area.last_switch_change = (
                switch_state.last_changed.timestamp() if switch_state else None
            )
            if area.switch_on and area.on_since is None:
                area.on_since = area.last_switch_change
            await self._control_area(area, ts, minutes, heating_day, return_ts)
        else:
            area.status = AreaStatus.NO_CIRCUIT
            area.effective_target = None

        self._ventilation(area, heating_day)

    async def _control_area(
        self, area: Area, ts: float, minutes: float, heating_day: bool, return_ts: float | None
    ) -> None:
        assert area.learner is not None
        rt = area.runtime
        run_hours = (ts - area.on_since) / 3600 if (area.switch_on and area.on_since) else 0.0
        learned = self._learned_values(area, run_hours, ts)
        area.learned_values = learned

        # vacation and preheating for the return
        area.vacation = self.vacation
        area.preheat = False
        target = area.target
        if self.vacation:
            # A return time in the past (e.g. vacation switched on manually with an old
            # date) is ignored, otherwise the vacation temperature would never apply.
            if return_ts is not None and return_ts > ts:
                start = preheat_start(
                    return_ts,
                    area.temp,
                    area.target,
                    learned.heat_rate_kph,
                    learned.dead_time_s,
                    float(self.opt(CONF_PREHEAT_RESERVE)) * 60,
                )
                area.preheat = ts >= start
            if not area.preheat:
                target = float(self.opt(CONF_VACATION_TEMP))
        area.effective_target = target

        window_open_since = rt.window_open_since
        temp_before = rt.temp_before_open
        decision = step(
            ControlInput(
                now=ts,
                temp=area.temp,
                target=target,
                hvac_on=area.hvac_on,
                season_active=self.season_active,
                heating_day=heating_day or area.preheat,
                frost_temp=float(self.opt(CONF_FROST_TEMP)),
                window_open=area.window_open,
                switch_on=area.switch_on,
                last_switch_change=area.last_switch_change,
                vacation=self.vacation,
                preheat=area.preheat,
            ),
            area.params,
            area.settings,
            learned,
            rt,
        )
        area.decision = decision
        area.status = decision.status
        self._handle_events(area, ts, window_open_since, temp_before)

        if area.switch_available and decision.want_on != area.switch_on and decision.may_switch:
            await self._switch(area, decision.want_on, ts)

        area.learner.add_sample(
            Sample(
                ts,
                area.temp,
                area.switch_on,
                self.outdoor_temp,
                self.pv_assumed,
                area.airing or area.temp is None,
                pv_unknown=self.pv_kw is None,
            )
        )
        # The virtual room first: on the first tick of a day it starts at the real
        # temperature even if the circuit is running at that moment.
        self._track_virtual(area, minutes, target)
        self._count(area, minutes, target, ts)

    def _handle_events(
        self, area: Area, ts: float, open_since: float | None, temp_before: float | None
    ) -> None:
        assert area.learner is not None
        for event in area.runtime.events:
            if event == "window_opened":
                area.learner.on_window_opened()
            elif event == "window_closed":
                open_seconds = ts - open_since if open_since else 0.0
                until = area.runtime.recovery_until
                area.learner.on_window_closed(
                    ts, temp_before, open_seconds, None if until is None else until - ts
                )
            elif event == "window_pause":
                self._log("window_pause", area)
            elif event == "recovery_start" and area.runtime.recovery_until:
                until = dt_util.as_local(dt_util.utc_from_timestamp(area.runtime.recovery_until))
                self._log("recovery_start", area, until=until.strftime("%H:%M"))
            elif event == "recovery_end":
                self._log("recovery_end", area)
            elif event == "emergency":
                # The rule fires on the expected temperature; for the day's evaluation only
                # a room that is really that cold counts as observed need.
                target = area.effective_target or area.target
                limit = emergency_limit(target, area.params, area.settings)
                area.day.emergency = area.temp is not None and area.temp < limit
                self._log(
                    "emergency",
                    area,
                    temp=area.temp,
                    predicted=area.decision.predicted_temp if area.decision else None,
                    limit=round(limit, 2),
                )
            elif event in ("frost_start", "frost_end"):
                self._log(event, area, temp=area.temp)

    async def _switch(self, area: Area, turn_on: bool, ts: float) -> None:
        entity_id = area.cfg[CONF_SWITCH]
        domain = entity_id.split(".", 1)[0]
        area.commanded = (turn_on, ts)
        try:
            await self.hass.services.async_call(
                domain,
                "turn_on" if turn_on else "turn_off",
                {ATTR_ENTITY_ID: entity_id},
                blocking=False,
            )
        except HomeAssistantError as err:
            LOGGER.warning("Switching %s failed: %s", entity_id, err)

    def _count(self, area: Area, minutes: float, target: float, ts: float) -> None:
        if minutes <= 0 or area.temp is None:
            return
        margin = float(self.opt(CONF_TOO_COLD_MARGIN))
        day, check = area.day, area.check
        if area.window_open:
            day.window_min += minutes
            check["window_min"] = check.get("window_min", 0.0) + minutes
        if area.switch_on:
            day.relay_min += minutes
            check["on_min"] = check.get("on_min", 0.0) + minutes
        if area.hvac_on and not area.airing:
            day.observed_min += minutes
            if area.temp < target - margin:
                day.too_cold_min += minutes
            if area.temp < target - CHECK_COLD_MARGIN:
                check["cold_min"] = check.get("cold_min", 0.0) + minutes
            # Heat above the target shortly after heating was wasted; warmth from sun
            # alone on a day without heating costs nothing.
            excess = area.temp - target - OVERHEAT_MARGIN
            heated = area.switch_on or (
                area.off_at is not None and 0 <= ts - area.off_at < OVERHEAT_AFTER_S
            )
            if excess > 0 and heated:
                over = excess * minutes / 60
                day.over_kh += over
                check["over_kh"] = check.get("over_kh", 0.0) + over
                if self.pv_assumed >= SUN_OVERHEAT_KW:
                    check["sun_over_kh"] = check.get("sun_over_kh", 0.0) + over
            if self.outdoor_temp is not None and target > self.outdoor_temp:
                check["deg_h"] = (
                    check.get("deg_h", 0.0) + (target - self.outdoor_temp) * minutes / 60
                )
        check["minutes"] = check.get("minutes", 0.0) + minutes
        check["max_over"] = max(check.get("max_over", -99.0), area.temp - target)
        check["min_t"] = min(check.get("min_t", 99.0), area.temp)
        check["max_t"] = max(check.get("max_t", -99.0), area.temp)

    def _track_virtual(self, area: Area, minutes: float, target: float) -> None:
        """Follow the temperature the area would have without any heating today.

        The evaluation of a heating day needs it: once a circuit ran, the real room was
        kept warm by the decision itself. The virtual room cools with the learned model
        and is never warmer than the real one.
        """
        if area.temp is None or area.learner is None:
            return
        model = area.learner.model
        outdoor, pv, sun = self.outdoor_temp, self.pv_assumed, area.params.sun_factor
        hd.track_virtual(
            area.day,
            area.temp,
            minutes,
            lambda t: model.cool_rate((t - outdoor) if outdoor is not None else 10.0, pv, sun),
            target,
            float(self.opt(CONF_TOO_COLD_MARGIN)),
            ready=model.n_cool >= VIRTUAL_MIN_COOL_UPDATES,
            counting=area.hvac_on and not area.airing,
            airing=area.airing,
        )

    def _ventilation(self, area: Area, heating_day: bool) -> None:
        cfg = area.cfg
        indoor_ref = bool(cfg.get(CONF_REF_TEMP))
        if indoor_ref:
            ref_temp = self._temp(cfg.get(CONF_REF_TEMP))
            ref_hum = self._float(cfg.get(CONF_REF_HUMIDITY))
        else:
            ref_temp = self.outdoor_temp
            ref_hum = self._float(self.opt(CONF_OUTDOOR_HUMIDITY))
            if ref_hum is None and (weather := self._state(self.opt(CONF_WEATHER))):
                humidity = weather.attributes.get("humidity")
                ref_hum = float(humidity) if isinstance(humidity, int | float) else None
        hour = dt_util.now().hour
        start, end = int(self.opt(CONF_NIGHT_START)), int(self.opt(CONF_NIGHT_END))
        is_night = (hour >= start or hour < end) if start > end else (start <= hour < end)
        heating_active = (
            self.season_active and heating_day and (area.hvac_on or not area.has_circuit)
        )
        area.ventilation = recommend(
            VentilationInput(
                temp=area.temp,
                humidity=area.humidity,
                ref_temp=ref_temp,
                ref_humidity=ref_hum,
                window_open=area.window_open,
                heating_active=heating_active,
                blocked=self._is_active(cfg.get(CONF_VENT_BLOCK)),
                reference_is_indoor=indoor_ref,
                is_night=is_night,
                target=area.effective_target or area.target,
                season_active=self.season_active,
            ),
            VentilationSettings(
                rh_threshold=float(cfg.get(CONF_VENT_RH, 60.0)),
                min_ah_advantage=float(self.opt(CONF_VENT_MIN_AH)),
                max_reference_excess=float(self.opt(CONF_VENT_MAX_EXCESS)),
                min_cooling_advantage=float(self.opt(CONF_VENT_MIN_COOLING)),
                cooling_margin=float(self.opt(CONF_VENT_COOL_MARGIN)),
                cooling_min_temp=float(self.opt(CONF_VENT_COOL_MIN_TEMP)),
            ),
        )

    # ------------------------------------------------------------------ user actions

    async def async_set_target(self, area_id: str, value: float) -> None:
        area = self.areas[area_id]
        area.target = round(float(value), 2)
        self._config_changed()
        self.async_update_listeners()
        await self.async_request_refresh()

    async def async_set_hvac(self, area_id: str, on: bool) -> None:
        area = self.areas[area_id]
        area.hvac_on = on
        self._config_changed()
        self.async_update_listeners()
        await self.async_request_refresh()

    async def async_set_ai_enabled(self, enabled: bool) -> None:
        self.ai_state["enabled"] = enabled
        if not enabled:
            self._schedule_check(None)
        elif self.heating_day and self.season_active:
            self._schedule_check(dt_util.utcnow() + timedelta(minutes=5))
        self._save()
        self.async_update_listeners()

    async def async_set_override(self, option: str) -> None:
        override = hd.Override(option)
        today = dt_util.now().date().isoformat()
        self.day_state["override"] = override
        self.day_state["override_date"] = today
        if override != hd.Override.AUTO:
            # Marks the day being decided and, before the nightly run, also the day
            # still running: both ran partly under the override.
            days = {today, str((self.current_day or {}).get("date") or today)}
            manual = [d for d in self.day_state.get("manual_days", []) if d not in days]
            self.day_state["manual_days"] = (manual + sorted(days))[-5:]
        self._config_changed()  # heating day may have changed: plan a check again (and save)
        self.async_update_listeners()
        await self.async_request_refresh()

    def _config_changed(self) -> None:
        """A user change makes the AI look again soon."""
        self.ai_state["stable"] = 0
        if self.ai_enabled and self.heating_day and self.season_active:
            now = dt_util.utcnow()
            soon = now + timedelta(hours=float(self.opt(CONF_CHECK_INTERVAL)))
            current = dt_util.parse_datetime(str(self.ai_state.get("next_check") or ""))
            if current is None or current <= now or current > soon:
                self._schedule_check(soon)
        self._save()

    # ------------------------------------------------------------------ heating day

    @callback
    def _nightly_callback(self, now: datetime) -> None:
        self.config_entry.async_create_background_task(
            self.hass, self.async_decide_heating_day("nightly"), f"{DOMAIN} nightly"
        )

    @property
    def next_nightly(self) -> datetime:
        """Time of the next nightly run (UTC)."""
        return self._valid_until()

    def _valid_until(self) -> datetime:
        nightly = _parse_time(str(self.opt(CONF_NIGHTLY_TIME)))
        local_now = dt_util.now()
        candidate = local_now.replace(
            hour=nightly.hour, minute=nightly.minute, second=nightly.second, microsecond=0
        )
        if candidate <= local_now + timedelta(minutes=1):
            candidate += timedelta(days=1)
        return dt_util.as_utc(candidate)

    async def _forecast(self, kind: str) -> list[dict[str, Any]]:
        weather = self.opt(CONF_WEATHER)
        if not weather or self._state(weather) is None:
            return []
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": kind},
                target={ATTR_ENTITY_ID: weather},
                blocking=True,
                return_response=True,
            )
        except (HomeAssistantError, ValueError) as err:
            LOGGER.debug("No %s forecast from %s: %s", kind, weather, err)
            return []
        data = (response or {}).get(weather, {})
        forecast = data.get("forecast") if isinstance(data, dict) else None
        if not isinstance(forecast, list):
            return []
        # The service answers in the temperature unit of the weather entity (the unit
        # system of HA unless set per entity); the logic works in °C.
        state = self._state(weather)
        unit = state.attributes.get("temperature_unit") if state else None
        items = []
        for item in forecast:
            if not isinstance(item, dict):
                continue
            item = dict(item)
            for key in ("temperature", "templow"):
                value = item.get(key)
                if isinstance(value, int | float) and not isinstance(value, bool):
                    celsius = self._to_celsius(float(value), unit, weather)
                    item[key] = None if celsius is None else round(celsius, 1)
            items.append(item)
        return items

    async def async_decide_heating_day(self, trigger: str, use_ai: bool = True) -> None:
        """Evaluate the previous day and decide whether today is a heating day."""
        if self._deciding:
            return
        self._deciding = True
        try:
            await self._decide(trigger, use_ai)
        finally:
            self._deciding = False
            self._save()
            self.async_update_listeners()

    async def _decide(self, trigger: str, use_ai: bool) -> None:
        now = dt_util.utcnow()
        local_today = dt_util.now().date().isoformat()
        self.season_active = self._season()
        current = self.current_day
        # An expired decision of the same date (made between midnight and the nightly
        # time) is decided again, not evaluated as a day of its own.
        new_day = current is None or current.get("date") != local_today

        if new_day and current is not None and not current.get("evaluated"):
            self._evaluate(current)
        if new_day:
            self.meter.rebase("day")
            # A manual override only applies to the day it was set on; one set after
            # midnight for the day about to be decided stays.
            if self.day_state.get("override_date") != local_today:
                self.day_state["override"] = hd.Override.AUTO
            for area in self.areas.values():
                area.runtime.emergency_active = False
                area.runtime.below_emergency_since = None
                area.day = hd.DayAreaStats()  # also outside the season: nothing piles up

        if not self.season_active:
            self.day_state["current"] = {
                "date": local_today,
                "valid_until": self._valid_until().isoformat(),
                "decided_at": now.isoformat(),
                "trigger": trigger,
                "heat": False,
                "source": "season",
                "phase": self.phase,
                "reason": "",
                "confidence": None,
                "rule": None,
                "ai": None,
                "vacation": self.vacation,
                "evaluated": True,
            }
            self._schedule_check(None)
            return

        daily = await self._forecast("daily")
        hourly = await self._forecast("hourly")
        tmax, tmin = _today_extremes(daily, hourly)
        snapshots = [
            hd.AreaSnapshot(
                a.area_id, a.name, a.temp, a.effective_target or a.target, a.params.puffer
            )
            for a in self.areas.values()
            if a.has_circuit and a.hvac_on
        ]
        rule = hd.rule_proposal(tmax, snapshots, self.theta, hd.RuleSettings())
        phase = self.phase

        ai_decision: hd.AiDecision | None = None
        last_ai = self.day_state.get("last_ai_date")
        days_since_ai = (
            (dt_util.now().date() - datetime.fromisoformat(last_ai).date()).days
            if last_ai
            else None
        )
        if (
            use_ai
            and self.ai_enabled
            and not self.vacation
            and hd.should_ask_ai(phase, rule, days_since_ai, self._phase_settings())
        ):
            ai_decision = await self._ask_nightly(tmax, tmin, hourly, rule)
            if ai_decision is not None:
                self.day_state["last_ai_date"] = local_today

        heat, source = hd.final_decision(phase, rule, ai_decision)
        if self.vacation:
            source = "vacation_rule"
        self.day_state["current"] = {
            "date": local_today,
            "valid_until": self._valid_until().isoformat(),
            "decided_at": now.isoformat(),
            "trigger": trigger,
            "heat": heat,
            "source": source,
            "phase": phase,
            "confidence": ai_decision.confidence if ai_decision else None,
            "reason": ai_decision.reason if ai_decision else "",
            "critical_area": ai_decision.critical_area if ai_decision else "",
            "rule": rule.as_dict(),
            "ai": None
            if ai_decision is None
            else {"heat": ai_decision.heat, "confidence": ai_decision.confidence},
            "vacation": self.vacation,
            "evaluated": False,
        }
        reason = ai_decision.reason if ai_decision else self._rule_reason(rule)
        self._log(
            "heating_day",
            decision=text(self.language, "yes" if heat else "no"),
            source=source,
            phase=phase,
            reason=reason,
        )
        if self.heating_day and self.ai_enabled:  # honours a manual override
            # A check already planned keeps its date: the interval grows while nothing
            # changes, and a daily reset would undo that. A room that was too cold since
            # the last check does not wait for it, though.
            pending = dt_util.parse_datetime(str(self.ai_state.get("next_check") or ""))
            soon = now + timedelta(hours=float(self.opt(CONF_CHECK_INTERVAL)))
            too_cold = float(self.opt(CONF_TOO_COLD_MINUTES))
            cold = any(
                a.check.get("cold_min", 0) >= too_cold for a in self.areas.values() if a.has_circuit
            )
            if pending is None or pending <= now or (cold and pending > soon):
                self._schedule_check(soon)
        else:
            self._schedule_check(None)
        await self.async_request_refresh()

    def _rule_reason(self, rule: hd.RuleResult) -> str:
        parts = []
        if rule.tmax is not None:
            parts.append(
                f"Tmax {rule.tmax} {'<' if rule.outdoor_rule else '>='} theta {rule.theta}"
            )
        if rule.cold_areas:
            names = [a.name for a in self.areas.values() if a.area_id in rule.cold_areas]
            parts.append("< target + puffer: " + ", ".join(names))
        return "; ".join(parts)

    def _evaluate(self, current: dict[str, Any]) -> None:
        """Evaluate the finished decision day, learn the rule and update the phase."""
        current["evaluated"] = True
        stats = {a.area_id: a.day for a in self.areas.values() if a.has_circuit}
        need = hd.evaluate_need(stats, self._eval_settings())
        rule_data = current.get("rule") or {}
        ai = current.get("ai")
        # Under a manual override the day ran as overridden, not as decided. The
        # override still set counts if it was set on this day; one set earlier in the
        # day and taken back still marks the day as manual.
        date = str(current.get("date"))
        override = self.day_state.get("override", hd.Override.AUTO)
        active = override != hd.Override.AUTO and self.day_state.get("override_date", date) == date
        manual = active or date in self.day_state.get("manual_days", [])
        record = hd.DayRecord(
            date=date,
            final=override == hd.Override.HEAT if active else bool(current.get("heat")),
            source="override" if manual else str(current.get("source")),
            rule=bool(rule_data.get("heat", current.get("heat"))),
            ai=None if not ai else bool(ai.get("heat")),
            need=need,
            phase=str(current.get("phase", self.phase)),
            manual=manual,
            vacation=bool(current.get("vacation")),
        )
        record.extra = {
            "on_min": round(sum(s.relay_min for s in stats.values())),
            "over_kh": round(sum(s.over_kh for s in stats.values()), 2),
        }
        if self.opt(CONF_HEAT_METER) and (kwh := self.meter.kwh_since("day")) is not None:
            record.extra["kwh"] = kwh
        record.err_final = hd.error_of(record.final, need)
        record.err_rule = hd.error_of(record.rule, need)
        record.err_ai = hd.error_of(record.ai, need)

        if rule_data and need != hd.Need.UNCLEAR and not current.get("vacation") and not manual:
            rule = hd.RuleResult(
                **{k: rule_data[k] for k in hd.RuleResult.__dataclass_fields__ if k in rule_data}
            )
            puffers = {a.area_id: a.params.puffer for a in self.areas.values() if a.has_circuit}
            theta, new_puffers, changes = hd.learn_rule(
                self.theta, puffers, rule, need, stats, self._eval_settings()
            )
            if changes:
                self.day_state["theta"] = theta
                for area_id, value in new_puffers.items():
                    self.areas[area_id].params.puffer = value
                record.learned = True
                self._log(
                    "rule_learned",
                    theta=theta,
                    puffer=", ".join(f"{self.areas[k].name} {v}" for k, v in new_puffers.items()),
                )

        history = [hd.DayRecord.from_dict(h) for h in self.day_state.get("history", [])]
        history.append(record)
        history = history[-HISTORY_DAYS:]
        self.day_state["history"] = [h.as_dict() for h in history]
        self._log(
            "evaluation",
            date=record.date,
            need=need,
            err_final=record.err_final or "-",
            err_rule=record.err_rule or "-",
            err_ai=record.err_ai or "-",
        )

        phase = self.phase
        phase_since = self.day_state.get("phase_since")
        days_in_phase = len([h for h in history if phase_since is None or h.date >= phase_since])
        new_phase = hd.next_phase(phase, history, days_in_phase, self._phase_settings())
        if new_phase != phase:
            self.day_state["phase"] = new_phase
            self.day_state["phase_since"] = dt_util.now().date().isoformat()
            self._log("phase_change", old=phase, new=new_phase)
        for area in self.areas.values():
            area.day = hd.DayAreaStats()

    async def _ask_nightly(
        self,
        tmax: float | None,
        tmin: float | None,
        hourly: list[dict[str, Any]],
        rule: hd.RuleResult,
    ) -> hd.AiDecision | None:
        history = self.day_state.get("history", [])[-14:]
        payload = {
            "date": dt_util.now().date().isoformat(),
            "outdoor_now": r(self.outdoor_temp, 1),
            "forecast": {
                "tmax": r(tmax, 1),
                "tmin": r(tmin, 1),
                "hourly": _hourly_compact(hourly, 24),
            },
            "pv_kw_now": r(self.pv_kw, 2),
            "areas": [
                {
                    "id": a.prompt_id,
                    "name": a.name,
                    "temp": r(a.temp),
                    "target": a.effective_target or a.target,
                    "puffer": a.params.puffer,
                    "window_open": a.window_open,
                    "cool_kph": r(a.learned_values.cool_rate_kph, 3),
                    "confidence": a.learner.confidence() if a.learner else 0,
                }
                for a in self.areas.values()
                if a.has_circuit and a.hvac_on
            ],
            "rule": {
                "theta": rule.theta,
                "proposal": rule.heat,
                "sure": rule.sure,
                "cold_areas": [self._prompt_id(x) for x in rule.cold_areas],
            },
            "history": [
                {
                    "d": h.get("date"),
                    "final": h.get("final"),
                    "need": h.get("need"),
                    "err": h.get("err_final"),
                    **({"manual": True} if h.get("manual") else {}),
                    **{
                        k: v
                        for k, v in (h.get("extra") or {}).items()
                        if k in ("on_min", "over_kh", "kwh")
                    },
                }
                for h in history
            ],
        }
        system, user = nightly_messages(payload, self.language)
        data = await self._ai_call("nightly", system, user, NIGHTLY_SCHEMA)
        if data is None:
            return None
        try:
            decision = validate_nightly(data)
        except AnswerError as err:
            self._ai_failed("nightly", str(err))
            return None
        decision.critical_area = next(
            (a.name for a in self.areas.values() if a.prompt_id == decision.critical_area),
            decision.critical_area,
        )
        return decision

    def _prompt_id(self, area_id: str) -> str:
        area = self.areas.get(area_id)
        return area.prompt_id if area else area_id

    # ------------------------------------------------------------------ AI calls

    async def _ai_call(
        self, kind: str, system: str, user: str, schema: dict[str, Any]
    ) -> dict[str, Any] | None:
        if self.client is None or not self.ai_enabled:
            return None
        month = dt_util.now().strftime("%Y-%m")
        self.budget.roll(month)
        limit = float(self.opt(CONF_BUDGET))
        max_tokens = int(self.opt(CONF_MAX_OUTPUT_TOKENS))
        estimate = estimate_cost(len(system) + len(user), max_tokens, self.prices)
        if not self.budget.can_spend(estimate, limit):
            if self.ai_state.get("budget_logged") != month:
                self.ai_state["budget_logged"] = month
                self._log("ai_budget", spent=round(self.budget.spent, 2), budget=limit)
            return None
        self.client.model = str(self.opt(CONF_AI_MODEL))
        self.client.effort = str(self.opt(CONF_AI_EFFORT))
        usage: dict[str, Any] = {}
        try:
            data, usage = await self.client.structured(system, user, schema, max_tokens)
        except AiError as err:
            usage = err.usage
            self._ai_failed(kind, str(err))
            data = None
        finally:
            if usage:
                self.budget.add(cost_eur(usage, self.prices), usage)
            self._save()
        if data is not None:
            self.ai_state["last_error"] = None
        return data

    def _ai_failed(self, kind: str, error: str) -> None:
        self.ai_state["last_error"] = f"{kind}: {error}"
        self.ai_state["last_error_at"] = dt_util.utcnow().isoformat()
        self._log("ai_error", kind=kind, error=error)

    def _restore_check_schedule(self) -> None:
        when = dt_util.parse_datetime(str(self.ai_state.get("next_check") or ""))
        if when is None:
            return
        earliest = dt_util.utcnow() + timedelta(minutes=5)
        self._schedule_check(max(when, earliest))

    def _schedule_check(self, when: datetime | None) -> None:
        if self._unsub_check:
            self._unsub_check()
            self._unsub_check = None
        self.ai_state["next_check"] = when.isoformat() if when else None
        if when is not None:
            self._unsub_check = async_track_point_in_utc_time(self.hass, self._check_due, when)

    @callback
    def _check_due(self, now: datetime) -> None:
        self._unsub_check = None
        self.config_entry.async_create_background_task(
            self.hass, self.async_run_ai_check("scheduled"), f"{DOMAIN} ai check"
        )

    async def async_run_ai_check(self, trigger: str) -> None:
        """Periodic AI review of the parameters."""
        if self._checking:
            return
        manual = trigger == "manual"
        if not self.ai_enabled or not self.season_active or (not self.heating_day and not manual):
            self._schedule_check(None)
            return
        self._checking = True
        try:
            await self._run_check()
        finally:
            self._checking = False
            self._save()
            self.async_update_listeners()

    async def _run_check(self) -> None:
        now = dt_util.utcnow()
        hourly = await self._forecast("hourly")
        controlled = [a for a in self.areas.values() if a.has_circuit and a.learner is not None]
        current: dict[str, dict[str, float]] = {GLOBAL: {"theta": self.theta}}
        areas_payload = []
        for area in controlled:
            assert area.learner is not None
            values = {k: getattr(area.params, k) for k, p in PARAMS.items() if p.scope == "area"}
            current[area.prompt_id] = values
            model = area.learner.model
            check = area.check
            areas_payload.append(
                {
                    "id": area.prompt_id,
                    "name": area.name,
                    "target": area.effective_target or area.target,
                    "temp": r(area.temp),
                    "status": area.status,
                    "hvac_on": area.hvac_on,
                    "learned": {
                        "heat_kph": r(area.learned_values.heat_rate_kph, 3),
                        "cool_kph": r(area.learned_values.cool_rate_kph, 3),
                        "k": r(model.k, 4),
                        "sun": r(model.s, 3),
                        "overshoot_k": r(area.learner.overshoot.value),
                        "overshoot_per_h": r(area.learner.overshoot_rate.value, 3),
                        "dead_time_min": r(area.learner.dead_time.value / 60, 0),
                        "recovery_min": r(area.learner.recovery.value / 60, 0),
                        "confidence": area.learner.confidence(),
                    },
                    "params": values,
                    "stats": {
                        "minutes": r(check.get("minutes"), 0),
                        "cold_min": r(check.get("cold_min"), 0),
                        "max_over": r(
                            check.get("max_over") if check.get("max_over", -99) > -99 else None
                        ),
                        "cycles": int(check.get("cycles", 0)),
                        "on_min": r(check.get("on_min"), 0),
                        "avg_run_min": r(check["on_min"] / check["cycles"], 0)
                        if check.get("cycles") and check.get("on_min")
                        else None,
                        "on_per_kh": r(check.get("on_min", 0.0) / check["deg_h"], 3)
                        if check.get("deg_h", 0) >= 1
                        else None,
                        "over_kh": r(check.get("over_kh", 0.0)),
                        "sun_over_kh": r(check.get("sun_over_kh", 0.0)),
                        "min_t": r(check.get("min_t") if check.get("min_t", 99) < 99 else None),
                        "max_t": r(check.get("max_t") if check.get("max_t", -99) > -99 else None),
                        "window_min": r(check.get("window_min"), 0),
                    },
                }
            )
        limits = self.limits
        payload = {
            "time": dt_util.now().strftime("%Y-%m-%d %H:%M"),
            "heating_day": self.heating_day,
            "outdoor": r(self.outdoor_temp, 1),
            "pv_kw": r(self.pv_kw, 2),
            "forecast_12h": _hourly_compact(hourly, 12),
            "theta": self.theta,
            "areas": areas_payload,
            "heat": self._heat_payload(),
            "history": self.ai_state.get("check_history", []),
            "limits": {k: [v["min"], v["max"], v["step"]] for k, v in limits.items()},
        }
        system, user = check_messages(payload, self.language)
        data = await self._ai_call("check", system, user, CHECK_SCHEMA)
        self.ai_state["last_check"] = now.isoformat()
        comfort_issue = any(
            a.check.get("cold_min", 0) >= float(self.opt(CONF_TOO_COLD_MINUTES)) for a in controlled
        )
        efficiency_issue = any(
            overheat_issue(a.check.get("over_kh", 0.0), a.check.get("minutes", 0.0))
            for a in controlled
        )
        relevant = False
        if data is not None:
            try:
                result = validate_check(data, current, limits)
            except AnswerError as err:
                self._ai_failed("check", str(err))
                result = None
            if result is not None:
                relevant = result.relevant_change
                by_prompt = {a.prompt_id: a for a in controlled}
                for adj in result.applied:
                    area = by_prompt.get(adj.area)
                    if adj.area == GLOBAL:
                        self.day_state["theta"] = adj.new
                    elif area is not None:
                        setattr(area.params, adj.parameter, adj.new)
                    self._log(
                        "ai_adjust",
                        area,
                        parameter=adj.parameter,
                        old=adj.old,
                        new=adj.new,
                        clamped=text(self.language, "clamped") if adj.clamped else "",
                        reason=adj.reason,
                    )
                self.ai_state["last_summary"] = result.summary
                self.ai_state["last_confidence"] = result.confidence
                self.ai_state["last_rejected"] = result.rejected[:10]
                stable = update_stable_count(
                    int(self.ai_state.get("stable", 0)), relevant, comfort_issue, efficiency_issue
                )
                self.ai_state["stable"] = stable
                hours = next_interval_hours(
                    float(self.opt(CONF_CHECK_INTERVAL)),
                    float(self.opt(CONF_CHECK_MAX_INTERVAL)),
                    stable,
                )
                self._schedule_check(now + timedelta(hours=hours))
                self._log(
                    "ai_check",
                    count=len(result.applied),
                    confidence=result.confidence,
                    summary=result.summary,
                    hours=round(hours, 1),
                )
                self._add_check_history(areas_payload, result.applied, payload["heat"])
                self.meter.rebase("check")
                for area in controlled:
                    area.check = _new_check_stats()
                return
        # failure or no answer: try again after the base interval
        self._schedule_check(now + timedelta(hours=float(self.opt(CONF_CHECK_INTERVAL))))

    def _add_check_history(
        self,
        areas_payload: list[dict[str, Any]],
        applied: list[Any],
        heat: dict[str, Any] | None,
    ) -> None:
        """Keep the key figures of this check and its changes for the next checks."""
        keys = ("cold_min", "over_kh", "sun_over_kh", "on_per_kh", "cycles")
        entry: dict[str, Any] = {
            "t": dt_util.now().strftime("%m-%d %H:%M"),
            "areas": {a["id"]: {k: a["stats"].get(k) for k in keys} for a in areas_payload},
            "changes": [f"{a.area} {a.parameter} {a.old:g}>{a.new:g}" for a in applied],
        }
        if heat is not None:
            entry["kwh_per_kh"] = heat["kwh_per_kh"]
        history = [*self.ai_state.get("check_history", []), entry]
        self.ai_state["check_history"] = history[-CHECK_HISTORY:]

    # ------------------------------------------------------------------ services

    def export_parameters(self, area_ids: list[str] | None = None) -> dict[str, Any]:
        areas = {}
        for area in self.areas.values():
            if area_ids and area.area_id not in area_ids:
                continue
            entry: dict[str, Any] = {
                "id": area.area_id,
                "target": area.target,
                "params": area.params.as_dict(),
            }
            if area.learner is not None:
                lr = area.learner
                entry["learned"] = {
                    "heat_effect_kph": round(lr.model.a, 4),
                    "loss_per_h": round(lr.model.k, 5),
                    "sun_kph_per_kw": round(lr.model.s, 4),
                    "overshoot_k": round(lr.overshoot.value, 3),
                    "overshoot_per_h": round(lr.overshoot_rate.value, 4),
                    "dead_time_min": round(lr.dead_time.value / 60, 1),
                    "recovery_min": round(lr.recovery.value / 60, 1),
                }
                entry["counts"] = {
                    "model_heat": lr.model.n_heat,
                    "model_cool": lr.model.n_cool,
                    "overshoot": lr.overshoot.count,
                    "overshoot_per_h": lr.overshoot_rate.count,
                    "dead_time": lr.dead_time.count,
                    "recovery": lr.recovery.count,
                }
            areas[area.name] = entry
        return {
            "format": DOMAIN,
            "version": 1,
            "exported": dt_util.utcnow().isoformat(),
            "global": {"theta": self.theta, "phase": self.phase},
            "areas": areas,
        }

    def import_parameters(
        self, data: dict[str, Any], area_ids: list[str] | None = None
    ) -> list[str]:
        if not isinstance(data, dict) or not isinstance(data.get("areas", {}), dict):
            raise HomeAssistantError("invalid parameter data")
        limits = self.limits
        theta = (data.get("global") or {}).get("theta")
        if isinstance(theta, int | float) and not area_ids:
            self.day_state["theta"] = clamp(
                float(theta), limits["theta"]["min"], limits["theta"]["max"]
            )
        imported = []
        by_name = {a.name: a for a in self.areas.values()}
        for key, values in (data.get("areas") or {}).items():
            if not isinstance(values, dict):
                continue
            area = self.areas.get(str(values.get("id"))) or by_name.get(key)
            if area is None or (area_ids and area.area_id not in area_ids):
                continue
            for name, value in (values.get("params") or {}).items():
                spec = PARAMS.get(name)
                if spec is not None and spec.scope == "area" and isinstance(value, int | float):
                    lim = limits[name]
                    setattr(area.params, name, clamp(float(value), lim["min"], lim["max"]))
            if isinstance(values.get("target"), int | float):
                area.target = clamp(
                    float(values["target"]),
                    float(area.cfg.get("min_target", 5)),
                    float(area.cfg.get("max_target", 30)),
                )
            learned = values.get("learned") or {}
            counts = values.get("counts") or {}
            if area.learner is not None and isinstance(learned, dict):
                _import_learned(area.learner, learned, counts)
            imported.append(area.name)
        # An import is no configuration change: the start value record stays as it is.
        self._config_changed()
        self._log("import", areas=", ".join(imported) or "-")
        return imported

    def reset_learned(self, area_ids: list[str], include_parameters: bool) -> None:
        for area_id in area_ids:
            area = self.areas[area_id]
            start = _start_values(area.cfg)
            if area.learner is not None:
                area.learner = AreaLearner.create(start["dead_time"], start["recovery"])
            if include_parameters:
                area.params = ControlParams(
                    window_delay_min=start["window_delay_min"], puffer=start["puffer"]
                )
            area.start = start  # the configuration is in effect again
            self._forget_check_history(area)
            self._log("reset", area)
        self._config_changed()

    # --------------------------------------------------------- learned values (user edits)

    def learned_ranges(self) -> dict[str, tuple[float, float]]:
        """Allowed range of each editable learned value, in the units of the configuration."""
        limits = self.limits
        ranges = {"theta": (limits["theta"]["min"], limits["theta"]["max"])}
        for key, name in LEARNED_NAMES.items():
            if name in LEARNED_BOUNDS:
                low, high = LEARNED_BOUNDS[name]
                ranges[key] = (low / 60, high / 60)
            else:
                ranges[key] = (limits[name]["min"], limits[name]["max"])
        return ranges

    def learned_values(self, area_id: str) -> dict[str, float]:
        """Values in effect instead of the start values of an area, in configuration units."""
        area = self.areas.get(area_id)
        if area is None:
            return {}
        values = {CONF_WINDOW_DELAY: area.params.window_delay_min, CONF_PUFFER: area.params.puffer}
        if area.learner is not None:
            values[CONF_DEAD_TIME] = area.learner.dead_time.value / 60
            values[CONF_RECOVERY] = area.learner.recovery.value / 60
        return {k: round(v, 2) for k, v in values.items()}

    def set_learned(self, area_id: str, values: dict[str, float]) -> None:
        """Replace learned values of an area; learning continues from the new value."""
        area = self.areas[area_id]
        ranges = self.learned_ranges()
        current = self.learned_values(area_id)
        changed = False
        for key, value in values.items():
            if key not in current or math.isclose(current[key], float(value), abs_tol=1e-6):
                continue
            name = LEARNED_NAMES[key]
            new = clamp(float(value), *ranges[key])
            if name in LEARNED_BOUNDS:
                assert area.learner is not None
                ewma: Ewma = getattr(area.learner, name)
                ewma.value = new * 60
                # a value set by hand counts as an observation, like an imported one
                ewma.count = max(1, ewma.count)
            else:
                setattr(area.params, name, new)
            _, unit = _START_UNITS[name]
            self._log(
                "learned_edit",
                area,
                name=text(self.language, name),
                old=f"{current[key]:g}",
                new=f"{round(new, 2):g}",
                unit=unit,
            )
            changed = True
        if changed:
            self._forget_check_history(area)
            self._config_changed()
            self.async_update_listeners()

    def set_theta(self, value: float) -> None:
        """Replace the learned theta of the heating day rule."""
        new = clamp(float(value), *self.learned_ranges()["theta"])
        old = self.theta
        if math.isclose(round(old, 2), new, abs_tol=1e-6):
            return
        self.day_state["theta"] = new
        self._log("learned_edit", name="theta", old=f"{round(old, 2):g}", new=f"{new:g}", unit="°C")
        self._config_changed()
        self.async_update_listeners()


def _import_learned(learner: AreaLearner, learned: dict[str, Any], counts: dict[str, Any]) -> None:
    def num(key: str) -> float | None:
        value = learned.get(key)
        return float(value) if isinstance(value, int | float) else None

    model = learner.model
    for index, key in enumerate(("heat_effect_kph", "loss_per_h", "sun_kph_per_kw")):
        if (value := num(key)) is not None:
            model.theta[index] = value
    model.theta = [
        clamp(v, *b)
        for v, b in zip(model.theta, ((0.02, 5.0), (0.0, 0.3), (0.0, 3.0)), strict=True)
    ]
    model.p = [[P_START[i] if i == j else 0.0 for j in range(3)] for i in range(3)]
    model.n_heat = int(counts.get("model_heat", 0) or 0)
    model.n_cool = int(counts.get("model_cool", 0) or 0)
    pairs = (
        ("overshoot_k", learner.overshoot, 1.0, (0.0, 2.0), "overshoot"),
        ("overshoot_per_h", learner.overshoot_rate, 1.0, (0.0, 2.0), "overshoot_per_h"),
        ("dead_time_min", learner.dead_time, 60.0, DEAD_TIME_BOUNDS, "dead_time"),
        ("recovery_min", learner.recovery, 60.0, RECOVERY_BOUNDS, "recovery"),
    )
    for key, ewma, factor, bounds, count_key in pairs:
        if (value := num(key)) is not None:
            ewma.value = clamp(value * factor, *bounds)
            # An imported value is a deliberate one: it counts as an observation, so a
            # later start value only replaces it when the configuration changes.
            ewma.count = max(1, int(counts.get(count_key, 0) or 0))


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError:
        return time(3, 0)


def _local_date(item: dict[str, Any]) -> str | None:
    parsed = dt_util.parse_datetime(str(item.get("datetime", "")))
    return dt_util.as_local(parsed).date().isoformat() if parsed else None


def _today_extremes(
    daily: list[dict[str, Any]], hourly: list[dict[str, Any]]
) -> tuple[float | None, float | None]:
    today = dt_util.now().date().isoformat()
    for item in daily:
        if _local_date(item) == today and isinstance(item.get("temperature"), int | float):
            low = item.get("templow")
            return float(item["temperature"]), float(low) if isinstance(low, int | float) else None
    temps = [
        float(h["temperature"])
        for h in hourly
        if _local_date(h) == today and isinstance(h.get("temperature"), int | float)
    ]
    if temps:
        return max(temps), min(temps)
    return None, None


def _hourly_compact(hourly: list[dict[str, Any]], hours: int) -> list[str]:
    """Every second hour as 'HHh T C cloud% condition' to keep the prompt short."""
    result = []
    for item in hourly[:hours:2]:
        parsed = dt_util.parse_datetime(str(item.get("datetime", "")))
        if parsed is None:
            continue
        hour = dt_util.as_local(parsed).hour
        result.append(
            f"{hour}h {item.get('temperature')}C {item.get('cloud_coverage', '?')}% {item.get('condition', '')}"
        )
    return result
