"""Ventilation recommendation based on absolute humidity and temperature.

The decision order follows a proven template based solution:
1. a blocking entity (air conditioner running, sun protection closed, ...)
2. window open although ventilating brings nothing -> close window
3. relative humidity high and outside air is drier -> ventilate now (only if airing
   can lower the humidity noticeably: with a learned humidity profile the humidity
   reachable by airing must lie at least ``min_rh_drop`` below the current one).
   Airing in the heating period costs heat, the more the colder the reference air:
   there the humidity must exceed the threshold by ``energy_rh_per_k`` per Kelvin the
   reference is colder than the room, but never more than up to the mould limit.
   After an airing the room gets ``airing_pause_min`` to settle (moisture comes back
   from walls) before drying is recommended again, unless it is at the mould limit.
4. room is warmer than the reference and nobody heats -> ventilating is useful
   (within the heating period only if the room is clearly above its target, never
   below the optional minimum room temperature and never if the outside air would
   push the relative humidity of the room above its threshold)
5. humidity high but outside air not drier -> do not ventilate
6. otherwise everything is fine
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from enum import StrEnum
from typing import Any

from .physics import absolute_humidity


class VentilationState(StrEnum):
    """Possible recommendations."""

    UNKNOWN = "unknown"
    CLOSE_WINDOW = "close_window"
    VENTILATE_NOW = "ventilate_now"
    VENTILATION_USEFUL = "ventilation_useful"
    DO_NOT_VENTILATE = "do_not_ventilate"
    BLOCKED = "blocked"
    OPTIMAL = "optimal"


MOULD_RH = 70.0  # default relative humidity from which mould grows if it lasts
# Airing time by reference temperature while the exchange rate of the room is not
# learned yet: cold air exchanges fast and costs heat.
AIRING_MINUTES = ((0.0, 5), (10.0, 10), (15.0, 15))
AIRING_MINUTES_WARM = 20

RECOMMENDED_STATES = {VentilationState.VENTILATE_NOW, VentilationState.VENTILATION_USEFUL}

# Domains whose entity blocks the ventilation recommendation while it is "on".
ON_OFF_DOMAINS = {"binary_sensor", "input_boolean", "switch", "fan", "humidifier", "light"}
# domains with a defined blocking state (offered in the dialog; others still work)
BLOCK_DOMAINS = (*sorted(ON_OFF_DOMAINS), "climate", "cover", "water_heater")
NO_STATE = {"unavailable", "unknown", "none", ""}


def is_blocking(domain: str, state: str) -> bool:
    """Does an entity in this state block the recommendation?

    A cover blocks while closed (sun protection down), a climate entity or water heater
    while not off (e.g. an air conditioner running), on/off entities while on; any
    other entity while it is active (not off or idle).
    """
    if state in NO_STATE:
        return False
    if domain == "cover":
        return state in ("closed", "closing")
    if domain in ("climate", "water_heater"):
        return state != "off"
    if domain in ON_OFF_DOMAINS:
        return state == "on"
    return state not in ("off", "idle")


@dataclass(slots=True)
class VentilationSettings:
    """Thresholds of one area. The configuration gives the start values, the AI may
    adjust them within limits."""

    rh_threshold: float = 60.0
    rh_hysteresis: float = 3.0  # humidity stays "high" until this far below the threshold
    min_ah_advantage: float = 0.8
    max_reference_excess: float = 4.0
    min_cooling_advantage: float = 1.0
    cooling_margin: float = 1.0  # heating period: cool only this far above target
    cooling_min_temp: float = 0.0  # cool only from this room temperature on (0 = off)
    min_rh_drop: float = 3.0  # airing must lower the humidity at least this far
    # heating period: extra humidity above the threshold needed per Kelvin colder air
    energy_rh_per_k: float = 0.25
    mould_rh: float = MOULD_RH  # from here airing is always recommended
    airing_target_below: float = 5.0  # airing aims this far below the threshold
    airing_time_factor: float = 1.0  # scales the computed airing time
    airing_min_minutes: float = 3.0
    airing_max_minutes: float = 20.0
    airing_pause_min: float = 30.0  # no new drying recommendation this soon after airing

    def as_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, **defaults: float) -> VentilationSettings:
        settings = cls(**defaults)
        if data:
            for f in fields(cls):
                if f.name in data:
                    try:
                        setattr(settings, f.name, float(data[f.name]))
                    except (TypeError, ValueError):
                        continue
        return settings


@dataclass(slots=True)
class VentilationInput:
    """Measured values for one area."""

    temp: float | None
    humidity: float | None
    ref_temp: float | None
    ref_humidity: float | None
    window_open: bool = False
    heating_active: bool = False
    blocked: bool = False
    # Cooling advantage counts only at night when the reference is another room.
    reference_is_indoor: bool = False
    is_night: bool = False
    target: float | None = None
    season_active: bool = False
    was_rh_high: bool = False  # humidity was high at the last evaluation (hysteresis)
    was_drying: bool = False  # "ventilate now" at the last evaluation (hysteresis)
    # relative humidity a usual airing reaches according to the learned profile
    achievable_rh: float | None = None
    # minutes the room needs to reach the airing target (learned exchange rate)
    learned_airing_minutes: float | None = None
    minutes_since_airing: float | None = None  # since the own window was last closed


@dataclass(slots=True)
class VentilationResult:
    """Recommendation plus the values it is based on."""

    state: VentilationState
    ah_inside: float | None = None
    ah_reference: float | None = None
    delta_ah: float | None = None
    delta_t: float | None = None
    rh_high: bool = False
    drying_useful: bool = False
    cooling_useful: bool = False
    rh_after_exchange: float | None = None
    achievable_rh: float | None = None
    energy_hold: bool = False  # drying would help but costs too much heat for now
    pause_hold: bool = False  # drying would help but the room settles after airing
    required_rh: float | None = None  # humidity from which drying is worth its heat
    airing_minutes: int | None = None  # suggested airing time while recommended

    @property
    def recommended(self) -> bool:
        """Return True if opening the window is recommended."""
        return self.state in RECOMMENDED_STATES


def recommend(data: VentilationInput, settings: VentilationSettings) -> VentilationResult:
    """Return the ventilation recommendation for one area."""
    if None in (data.temp, data.humidity, data.ref_temp, data.ref_humidity):
        return VentilationResult(VentilationState.UNKNOWN)
    assert data.temp is not None and data.humidity is not None
    assert data.ref_temp is not None and data.ref_humidity is not None

    ah_inside = absolute_humidity(data.temp, data.humidity)
    ah_ref = absolute_humidity(data.ref_temp, data.ref_humidity)
    delta_ah = ah_inside - ah_ref
    delta_t = data.temp - data.ref_temp
    reference_excess = data.ref_temp - data.temp

    rh_high = data.humidity >= settings.rh_threshold or (
        data.was_rh_high and data.humidity > settings.rh_threshold - settings.rh_hysteresis
    )
    # Relative humidity of the room if its air were replaced by reference air
    # (walls and floor keep the room temperature).
    rh_after = 100.0 * ah_ref / absolute_humidity(data.temp, 100.0)
    drying_useful = (
        delta_ah >= settings.min_ah_advantage
        and reference_excess <= settings.max_reference_excess
        and (
            data.achievable_rh is None or data.humidity - data.achievable_rh >= settings.min_rh_drop
        )
    )
    cooling_useful = (
        delta_t >= settings.min_cooling_advantage
        and not data.heating_active
        and (not data.reference_is_indoor or data.is_night)
        and (
            not data.season_active
            or data.target is None
            or data.temp >= data.target + settings.cooling_margin
        )
        and (settings.cooling_min_temp <= 0 or data.temp >= settings.cooling_min_temp)
        and rh_after <= settings.rh_threshold
    )
    # Heat lost by airing grows with the temperature difference: in the heating period
    # a room only slightly humid waits until it is clearly humid (or the air is milder).
    required_rh = settings.rh_threshold
    if data.season_active or data.heating_active:
        extra = settings.energy_rh_per_k * max(0.0, delta_t)
        required_rh = min(
            settings.rh_threshold + extra, max(settings.mould_rh, settings.rh_threshold)
        )
    # once airing runs it goes on down to the hysteresis below the required humidity
    start_rh = required_rh - settings.rh_hysteresis if data.was_drying else required_rh
    energy_hold = (
        required_rh > settings.rh_threshold
        and drying_useful
        and rh_high
        and data.humidity < start_rh
    )
    pause_hold = (
        drying_useful
        and rh_high
        and not energy_hold
        and not data.window_open
        and data.minutes_since_airing is not None
        and data.minutes_since_airing < settings.airing_pause_min
        and data.humidity < settings.mould_rh
    )
    worth_drying = drying_useful and not energy_hold and not pause_hold
    benefit = worth_drying or cooling_useful

    if data.blocked:
        if data.window_open:
            state = VentilationState.CLOSE_WINDOW
        elif benefit:
            state = VentilationState.BLOCKED
        else:
            state = VentilationState.OPTIMAL
    elif data.window_open and not benefit:
        state = VentilationState.CLOSE_WINDOW
    elif rh_high and worth_drying:
        state = VentilationState.VENTILATE_NOW
    elif cooling_useful:
        state = VentilationState.VENTILATION_USEFUL
    elif rh_high:
        state = VentilationState.DO_NOT_VENTILATE
    else:
        state = VentilationState.OPTIMAL

    airing_minutes = None
    if state in RECOMMENDED_STATES:
        base: float | None = None
        if state == VentilationState.VENTILATE_NOW:
            base = data.learned_airing_minutes
        if base is None:
            base = next(
                (m for limit, m in AIRING_MINUTES if data.ref_temp <= limit), AIRING_MINUTES_WARM
            )
        airing_minutes = round(
            max(
                settings.airing_min_minutes,
                min(settings.airing_max_minutes, base * settings.airing_time_factor),
            )
        )
    return VentilationResult(
        state=state,
        ah_inside=round(ah_inside, 2),
        ah_reference=round(ah_ref, 2),
        delta_ah=round(delta_ah, 2),
        delta_t=round(delta_t, 2),
        rh_high=rh_high,
        drying_useful=drying_useful,
        cooling_useful=cooling_useful,
        rh_after_exchange=round(rh_after, 1),
        achievable_rh=None if data.achievable_rh is None else round(data.achievable_rh, 1),
        energy_hold=energy_hold,
        pause_hold=pause_hold,
        required_rh=round(required_rh, 1),
        airing_minutes=airing_minutes,
    )
