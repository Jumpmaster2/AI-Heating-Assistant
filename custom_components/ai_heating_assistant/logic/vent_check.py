"""Key figures of the ventilation recommendation between two AI checks."""

from __future__ import annotations

from typing import Any

from .ventilation import MOULD_RH, RECOMMENDED_STATES, VentilationResult, VentilationState


def new_vent_stats() -> dict[str, float]:
    return {
        "minutes": 0.0,
        "humid_min": 0.0,
        "mould_min": 0.0,
        "rh_sum": 0.0,
        "rh_max": 0.0,
        "rec_min": 0.0,
        "window_min": 0.0,
        "window_rec_min": 0.0,
        "cross_min": 0.0,
        "useless_min": 0.0,
        "heat_window_min": 0.0,
        "blocked_min": 0.0,
        "energy_hold_min": 0.0,
        "pause_hold_min": 0.0,
        "flips": 0.0,
    }


def count_vent(
    stats: dict[str, float],
    minutes: float,
    humidity: float | None,
    result: VentilationResult | None,
    previous: VentilationState | None,
    window_open: bool,
    heating: bool,
    mould_rh: float = MOULD_RH,
    cross: bool = False,
) -> None:
    """Add one tick of ``minutes`` to the statistics of an area. ``cross``: an own
    window is open together with windows in other rooms (cross ventilation)."""
    if minutes <= 0 or humidity is None or result is None:
        return
    if result.state == VentilationState.UNKNOWN:
        return

    def add(key: str, value: float = minutes) -> None:
        stats[key] = stats.get(key, 0.0) + value

    add("minutes")
    add("rh_sum", humidity * minutes)
    stats["rh_max"] = max(stats.get("rh_max", 0.0), humidity)
    if result.rh_high:
        add("humid_min")
    if humidity >= mould_rh:
        add("mould_min")
    if result.state in RECOMMENDED_STATES:
        add("rec_min")
    if window_open:
        add("window_min")
        if result.state in RECOMMENDED_STATES:
            add("window_rec_min")
        if cross:
            add("cross_min")
        if result.state == VentilationState.CLOSE_WINDOW:
            add("useless_min")
        if heating:
            add("heat_window_min")
    if result.state == VentilationState.BLOCKED:
        add("blocked_min")
    if result.energy_hold:
        add("energy_hold_min")
    if result.pause_hold:
        add("pause_hold_min")
    if previous not in (None, VentilationState.UNKNOWN) and previous != result.state:
        add("flips", 1.0)


def stats_payload(stats: dict[str, float]) -> dict[str, Any]:
    """Statistics as sent to the AI (rounded, mean instead of the sum)."""
    minutes = stats.get("minutes", 0.0)
    payload: dict[str, Any] = {
        key: round(stats.get(key, 0.0))
        for key in (
            "minutes",
            "humid_min",
            "mould_min",
            "rec_min",
            "window_min",
            "window_rec_min",
            "cross_min",
            "useless_min",
            "heat_window_min",
            "blocked_min",
            "energy_hold_min",
            "pause_hold_min",
            "flips",
        )
    }
    payload["rh_mean"] = round(stats.get("rh_sum", 0.0) / minutes, 1) if minutes else None
    payload["rh_max"] = round(stats.get("rh_max", 0.0), 1) if minutes else None
    return payload
