"""Control decision for one heating area (pure logic, called every tick)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
from typing import Any

FROST_HYSTERESIS = 0.5  # K above the frost limit before frost protection ends
RECOVERED_MARGIN = 0.1  # K below the temperature before airing counts as recovered
FORCE_ON_BELOW = 1.0  # K below target: heat regardless of predictions
SHORT_AIRING_S = 120.0  # shorter openings are ignored after closing
PEAK_PASSED_K = 0.15  # K below the highest temperature since switch-off: overshoot has arrived
# The overshoot expected at switch-off is forgotten after this at the latest. It ends
# earlier once the temperature falls again; the peak comes several dead times after
# the switch-off, so the limit is not tied to the dead time.
PEAK_CARRY_MAX_S = 4 * 3600.0
EPS = 1e-6  # tolerance for comparing sensor values in 0.1 K steps (21.0 - 0.1 > 20.9)


class AreaStatus(StrEnum):
    """Status shown per area."""

    OFF = "off"
    OUT_OF_SEASON = "out_of_season"
    NO_HEATING_DAY = "no_heating_day"
    IDLE = "idle"
    HEATING = "heating"
    WINDOW_OPEN = "window_open"
    RECOVERY = "recovery"
    FROST_PROTECTION = "frost_protection"
    VACATION = "vacation"
    PREHEAT = "preheat"
    EMERGENCY = "emergency"
    SENSOR_ERROR = "sensor_error"
    NO_CIRCUIT = "no_circuit"


@dataclass(slots=True)
class ControlParams:
    """Policy parameters of one area. The AI may adjust them within limits."""

    hysteresis_on: float = 0.2
    hysteresis_off: float = 0.0
    overshoot_factor: float = 1.0
    lead_factor: float = 1.0
    sun_factor: float = 1.0
    window_delay_min: float = 5.0
    recovery_bias_min: float = 0.0
    puffer: float = 0.7

    def as_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, **defaults: float) -> ControlParams:
        params = cls(**defaults)
        if data:
            for f in fields(cls):
                if f.name in data:
                    try:
                        setattr(params, f.name, float(data[f.name]))
                    except (TypeError, ValueError):
                        continue
        return params


@dataclass(slots=True)
class AreaSettings:
    """Fixed settings of one area (from configuration)."""

    min_on_s: float = 600.0
    min_off_s: float = 600.0
    emergency_enabled: bool = True
    emergency_delta: float = 1.0
    emergency_duration_s: float = 45 * 60.0
    emergency_window_quiet_s: float = 30 * 60.0


@dataclass(slots=True)
class LearnedValues:
    """Snapshot of learned values used for one decision."""

    cool_rate_kph: float = 0.05  # positive: room cools without heating
    heat_rate_kph: float = 0.5
    dead_time_s: float = 1800.0
    recovery_s: float = 1800.0
    overshoot_k: float = 0.0  # expected overshoot if switched off now
    pv_plan_kw: float = 0.0  # PV power expected over the lead time (used in cool_rate_kph)


@dataclass
class AreaRuntime:
    """Controller memory, persisted across restarts."""

    window_open_since: float | None = None
    temp_before_open: float | None = None
    window_paused: bool = False
    recovery_until: float | None = None
    short_recovery: bool = False  # recovery after airing shorter than the window delay
    last_window_change: float | None = None
    below_emergency_since: float | None = None
    emergency_active: bool = False
    frost_active: bool = False
    heating_since: float | None = None
    # Overshoot carried over a switch-off: the floor keeps warming the room for a while.
    was_on: bool = False
    last_peak: float | None = None  # expected peak on the last tick with the circuit on
    carry_peak: float | None = None  # expected peak after switch-off, until it has arrived
    carry_max: float | None = None  # highest temperature seen since switch-off
    carry_since: float | None = None
    events: list[str] = field(default_factory=list)

    # Not stored and not restored: after a restart a stale peak must not start a carry
    # (a carry already running keeps its real start time and expires on schedule).
    TRANSIENT = ("events", "was_on", "last_peak")

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for name in self.TRANSIENT:
            data.pop(name)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AreaRuntime:
        runtime = cls()
        if data:
            for f in fields(cls):
                if f.name not in cls.TRANSIENT and f.name in data:
                    setattr(runtime, f.name, data[f.name])
        return runtime


@dataclass(slots=True)
class ControlInput:
    """Everything the controller needs for one decision."""

    now: float
    temp: float | None
    target: float
    hvac_on: bool
    season_active: bool
    heating_day: bool
    frost_temp: float
    window_open: bool
    switch_on: bool
    last_switch_change: float | None
    vacation: bool = False
    preheat: bool = False


@dataclass(slots=True)
class ControlDecision:
    """Result of one controller step."""

    want_on: bool
    status: AreaStatus
    may_switch: bool
    predicted_temp: float | None = None
    expected_peak: float | None = None


def _may_switch(data: ControlInput, settings: AreaSettings) -> bool:
    if data.last_switch_change is None:
        return True
    elapsed = data.now - data.last_switch_change
    if elapsed < 0:
        # Clock jumped backwards: do not block the circuit forever.
        return True
    return elapsed >= (settings.min_on_s if data.switch_on else settings.min_off_s)


def _update_window(
    data: ControlInput, params: ControlParams, learned: LearnedValues, rt: AreaRuntime
) -> bool:
    """Track window state. Returns True while recovering after airing.

    Airing shorter than the window delay but at least ``SHORT_AIRING_S`` starts a
    short recovery, scaled by the share of the window delay the window was open.
    """
    if data.window_open:
        if rt.window_open_since is None:
            rt.window_open_since = data.now
            if rt.recovery_until is None or rt.temp_before_open is None:
                # Opened again while still recovering: the room has to get back to
                # the temperature before the first airing, not to the lowered one.
                rt.temp_before_open = data.temp
            rt.last_window_change = data.now
            rt.events.append("window_opened")
        if not rt.window_paused and data.now - rt.window_open_since >= params.window_delay_min * 60:
            rt.window_paused = True
            rt.recovery_until = None
            rt.short_recovery = False
            rt.events.append("window_pause")
    elif rt.window_open_since is not None:
        rt.events.append("window_closed")
        rt.last_window_change = data.now
        recovery = max(0.0, learned.recovery_s + params.recovery_bias_min * 60)
        open_s = data.now - rt.window_open_since
        if rt.window_paused:
            rt.recovery_until = data.now + recovery
            rt.short_recovery = False
            rt.events.append("recovery_start")
        elif open_s >= SHORT_AIRING_S and params.window_delay_min > 0:
            share = min(1.0, open_s / (params.window_delay_min * 60))
            rt.recovery_until = data.now + recovery * share
            rt.short_recovery = True
            rt.events.append("short_recovery_start")
        rt.window_open_since = None
        rt.window_paused = False

    if rt.recovery_until is None:
        return False
    recovered = (
        data.temp is not None
        and rt.temp_before_open is not None
        and data.temp - rt.temp_before_open >= -RECOVERED_MARGIN - EPS
    )
    if recovered or data.now >= rt.recovery_until:
        rt.recovery_until = None
        rt.events.append("short_recovery_end" if rt.short_recovery else "recovery_end")
        rt.short_recovery = False
        return False
    return True


def _update_carry(data: ControlInput, rt: AreaRuntime) -> None:
    """Keep the overshoot expected at switch-off until the temperature falls again.

    Without it the switch-on prediction starts from the current temperature, which is
    below target by the very overshoot the switch-off counted on, and the circuit would
    come back after the minimum off time while the floor is still delivering heat.
    """
    if data.switch_on:
        rt.was_on = True
        rt.carry_peak = None
        return
    if rt.was_on:
        rt.was_on = False
        rt.carry_peak = rt.last_peak
        rt.carry_max = data.temp
        rt.carry_since = data.now
        rt.last_peak = None
    if rt.carry_peak is None or data.temp is None:
        return
    rt.carry_max = data.temp if rt.carry_max is None else max(rt.carry_max, data.temp)
    expired = rt.carry_since is None or data.now - rt.carry_since >= PEAK_CARRY_MAX_S
    if expired or data.temp - rt.carry_max <= -PEAK_PASSED_K + EPS:
        rt.carry_peak = None


def predict_temp(
    data: ControlInput,
    params: ControlParams,
    learned: LearnedValues,
    carry_peak: float | None = None,
) -> float:
    """Temperature expected after the lead time (dead time scaled by the lead factor).

    ``carry_peak`` is the peak expected from the heat still in the floor after a
    switch-off; while it is pending the prediction starts from it, not from the
    current temperature.
    """
    assert data.temp is not None
    lead_h = learned.dead_time_s * params.lead_factor / 3600.0
    basis = data.temp if data.switch_on or carry_peak is None else max(data.temp, carry_peak)
    return basis - learned.cool_rate_kph * lead_h


def _update_emergency(
    data: ControlInput,
    params: ControlParams,
    settings: AreaSettings,
    learned: LearnedValues,
    rt: AreaRuntime,
) -> None:
    """Emergency rule on days without heating: expected to stay clearly too cold, no airing.

    The temperature expected after the lead time counts, not the current one: heating
    shows only after the dead time, so judging the current temperature would leave the
    room too cold for the persistence plus that dead time. Same prediction as the
    thermostat, so the two agree.
    """
    if not settings.emergency_enabled or data.temp is None or rt.emergency_active:
        return
    quiet = (
        rt.last_window_change is None
        or data.now - rt.last_window_change >= settings.emergency_window_quiet_s
    )
    predicted = predict_temp(data, params, learned, rt.carry_peak)
    if predicted < data.target - settings.emergency_delta and quiet and not data.window_open:
        if rt.below_emergency_since is None:
            rt.below_emergency_since = data.now
        elif data.now - rt.below_emergency_since >= settings.emergency_duration_s:
            rt.emergency_active = True
            rt.events.append("emergency")
    else:
        rt.below_emergency_since = None


def thermostat(
    data: ControlInput,
    params: ControlParams,
    learned: LearnedValues,
    carry_peak: float | None = None,
) -> tuple[bool, float, float]:
    """Predictive on/off decision. Returns (want_on, predicted_temp, expected_peak).

    ``carry_peak`` is the peak expected from the heat still in the floor after a
    switch-off (see ``predict_temp``).
    """
    assert data.temp is not None
    predicted = predict_temp(data, params, learned, carry_peak)
    peak = data.temp + learned.overshoot_k * params.overshoot_factor
    if not data.switch_on and carry_peak is not None:
        peak = max(peak, carry_peak)  # the peak still expected from the last run
    on_threshold = data.target - params.hysteresis_on
    off_threshold = data.target + params.hysteresis_off
    if data.temp < data.target - FORCE_ON_BELOW:
        want = True
    elif data.switch_on:
        want = peak < off_threshold
    else:
        want = predicted < on_threshold
    return want, round(predicted, 2), round(peak, 2)


def step(
    data: ControlInput,
    params: ControlParams,
    settings: AreaSettings,
    learned: LearnedValues,
    rt: AreaRuntime,
) -> ControlDecision:
    """Decide whether the circuit of one area should be on."""
    rt.events.clear()
    may_switch = _may_switch(data, settings)
    _update_carry(data, rt)
    recovering = _update_window(data, params, learned, rt)

    if data.temp is None:
        return ControlDecision(False, AreaStatus.SENSOR_ERROR, may_switch)

    if data.temp < data.frost_temp:
        if not rt.frost_active:
            rt.events.append("frost_start")
        rt.frost_active = True
    elif rt.frost_active and data.temp >= data.frost_temp + FROST_HYSTERESIS:
        rt.frost_active = False
        rt.events.append("frost_end")
    if rt.frost_active:
        return ControlDecision(True, AreaStatus.FROST_PROTECTION, may_switch)

    if not data.hvac_on:
        return ControlDecision(False, AreaStatus.OFF, may_switch)
    if not data.season_active:
        return ControlDecision(False, AreaStatus.OUT_OF_SEASON, may_switch)
    if rt.window_paused:
        return ControlDecision(False, AreaStatus.WINDOW_OPEN, may_switch)
    # Short airing: a window open shorter than the window delay, or the short recovery
    # after it, must not switch the circuit on. A running circuit keeps its normal logic.
    hold = data.window_open or (recovering and rt.short_recovery)
    if recovering and not rt.short_recovery:
        return ControlDecision(False, AreaStatus.RECOVERY, may_switch)

    if not data.heating_day:
        _update_emergency(data, params, settings, learned, rt)
        if not rt.emergency_active:
            return ControlDecision(False, AreaStatus.NO_HEATING_DAY, may_switch)

    want, predicted, peak = thermostat(data, params, learned, rt.carry_peak)
    if data.switch_on:
        rt.last_peak = peak
    if hold and want and not data.switch_on:
        status = AreaStatus.WINDOW_OPEN if data.window_open else AreaStatus.RECOVERY
        return ControlDecision(False, status, may_switch, predicted, peak)
    if not data.heating_day:
        status = AreaStatus.EMERGENCY
    elif data.preheat:
        status = AreaStatus.PREHEAT
    elif data.vacation:
        status = AreaStatus.VACATION
    else:
        status = AreaStatus.HEATING if want else AreaStatus.IDLE
    return ControlDecision(want, status, may_switch, predicted, peak)


def preheat_start(
    return_ts: float,
    temp: float | None,
    target: float,
    heat_rate_kph: float,
    dead_time_s: float,
    reserve_s: float,
) -> float:
    """Timestamp at which heating for the return has to start."""
    if temp is None:
        return return_ts - dead_time_s - reserve_s - 24 * 3600
    rate = max(heat_rate_kph, 0.05)
    hours = max(0.0, target - temp) / rate
    return return_ts - hours * 3600 - dead_time_s - reserve_s
