"""Ventilation recommendation based on absolute humidity and temperature.

The decision order follows a proven template based solution:
1. a blocking entity (air conditioner running, sun protection closed, ...)
2. window open although ventilating brings nothing -> close window
3. relative humidity high and outside air is drier -> ventilate now
4. room is warmer than the reference and nobody heats -> ventilating is useful
5. humidity high but outside air not drier -> do not ventilate
6. otherwise everything is fine
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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


RECOMMENDED_STATES = {VentilationState.VENTILATE_NOW, VentilationState.VENTILATION_USEFUL}


@dataclass(slots=True)
class VentilationSettings:
    """Thresholds, all configurable."""

    rh_threshold: float = 60.0
    min_ah_advantage: float = 0.8
    max_reference_excess: float = 4.0
    min_cooling_advantage: float = 1.0


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

    rh_high = data.humidity >= settings.rh_threshold
    drying_useful = (
        delta_ah >= settings.min_ah_advantage and reference_excess <= settings.max_reference_excess
    )
    cooling_useful = (
        delta_t >= settings.min_cooling_advantage
        and not data.heating_active
        and (not data.reference_is_indoor or data.is_night)
    )
    benefit = drying_useful or cooling_useful

    if data.blocked:
        if data.window_open:
            state = VentilationState.CLOSE_WINDOW
        elif benefit:
            state = VentilationState.BLOCKED
        else:
            state = VentilationState.OPTIMAL
    elif data.window_open and not benefit:
        state = VentilationState.CLOSE_WINDOW
    elif rh_high and drying_useful:
        state = VentilationState.VENTILATE_NOW
    elif cooling_useful:
        state = VentilationState.VENTILATION_USEFUL
    elif rh_high:
        state = VentilationState.DO_NOT_VENTILATE
    else:
        state = VentilationState.OPTIMAL

    return VentilationResult(
        state=state,
        ah_inside=round(ah_inside, 2),
        ah_reference=round(ah_ref, 2),
        delta_ah=round(delta_ah, 2),
        delta_t=round(delta_t, 2),
        rh_high=rh_high,
        drying_useful=drying_useful,
        cooling_useful=cooling_useful,
    )
