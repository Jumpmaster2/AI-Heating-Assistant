"""Start values of the area configuration: applied once, and again whenever they change.

Stored learned values and parameters take precedence over the configuration, so a
start value changed later would never take effect. The record of the values last
applied tells whether the user changed one; a changed value replaces the stored one
and its learning starts again.
"""

from __future__ import annotations

import math
from typing import Any

from .controller import ControlParams
from .learning import DEAD_TIME_BOUNDS, RECOVERY_BOUNDS, AreaLearner, Ewma
from .physics import clamp

# Attribute names of AreaLearner (seconds) and ControlParams (minutes, K).
START_NAMES = ("dead_time", "recovery", "window_delay_min", "puffer")
LEARNED_BOUNDS = {"dead_time": DEAD_TIME_BOUNDS, "recovery": RECOVERY_BOUNDS}
TOL = 1e-6


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=TOL)


def read_record(data: Any) -> dict[str, float]:
    """Start values last applied, from the store. Names missing were never applied."""
    if not isinstance(data, dict):
        return {}
    record = {}
    for name in START_NAMES:
        value = data.get(name)
        if isinstance(value, int | float) and not isinstance(value, bool):
            record[name] = float(value)
    return record


def apply_start_values(
    configured: dict[str, float],
    recorded: dict[str, float],
    learner: AreaLearner | None,
    params: ControlParams,
) -> list[tuple[str, float, float]]:
    """Apply configured start values that changed since they were last applied.

    Without a record (store of an older version, new area) a value is applied only
    where nothing has been learned yet: a learned value with samples, or a parameter
    the AI has moved away from the default, is kept and merely recorded. Values are
    compared as configured, not clamped, so a value outside the bounds is applied once.
    Returns (name, old, new) per applied value; the caller records ``configured``.
    """
    applied: list[tuple[str, float, float]] = []
    defaults = ControlParams()
    for name in START_NAMES:
        new = configured[name]
        last = recorded.get(name)
        if last is not None and _same(last, new):
            continue
        first = last is None
        if name in LEARNED_BOUNDS:
            if learner is None:
                continue
            ewma: Ewma = getattr(learner, name)
            if first and ewma.count > 0:
                continue
            value = clamp(new, *LEARNED_BOUNDS[name])
            if _same(ewma.value, value):
                continue  # already in effect: keep the samples, nothing to log
            setattr(learner, name, Ewma(value))
            applied.append((name, ewma.value, value))
        else:
            current = float(getattr(params, name))
            if first and not _same(current, getattr(defaults, name)):
                continue
            if _same(current, new):
                continue
            setattr(params, name, new)
            applied.append((name, current, new))
    return applied


# Thresholds of the ventilation recommendation configured as start values (the area's
# humidity threshold and the global thresholds); names of VentilationSettings.
VENT_START_NAMES = (
    "rh_threshold",
    "min_ah_advantage",
    "max_reference_excess",
    "energy_rh_per_k",
    "mould_rh",
    "airing_target_below",
    "airing_time_factor",
    "airing_min_minutes",
    "airing_max_minutes",
    "airing_pause_min",
    "min_cooling_advantage",
    "cooling_margin",
    "cooling_min_temp",
)


def read_vent_record(data: Any) -> dict[str, float]:
    """Ventilation start values last applied, from the store."""
    if not isinstance(data, dict):
        return {}
    return {
        name: float(value)
        for name in VENT_START_NAMES
        if isinstance(value := data.get(name), int | float) and not isinstance(value, bool)
    }


def apply_vent_start_values(
    configured: dict[str, float], recorded: dict[str, float], settings: Any
) -> list[tuple[str, float, float]]:
    """Apply configured ventilation thresholds that changed since they were last applied.

    Without a record the stored values stay (they were built from the configuration or
    adjusted by the AI). Returns (name, old, new) per applied value.
    """
    applied: list[tuple[str, float, float]] = []
    for name in VENT_START_NAMES:
        new, last = configured[name], recorded.get(name)
        if last is None or _same(last, new):
            continue
        current = float(getattr(settings, name))
        if _same(current, new):
            continue
        setattr(settings, name, new)
        applied.append((name, current, new))
    return applied
