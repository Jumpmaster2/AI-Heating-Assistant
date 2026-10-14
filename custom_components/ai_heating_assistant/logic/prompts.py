"""Short prompts for the AI. Data is sent as compact JSON to keep costs low."""

from __future__ import annotations

import json
from typing import Any

from .ai_schema import PARAMS

LANGUAGES = {"de": "German", "en": "English"}

NIGHTLY_SYSTEM = (
    "You decide once per night whether an underfloor heating system is needed today "
    "(from now until the same time tomorrow). Each area has its own on/off circuit; "
    "the local controller keeps every area at its target on heating days. On a no-heating day "
    "all circuits stay off except frost protection and an emergency rule (temperature expected "
    "after the dead time long and clearly below target, without airing). Floors store a lot of "
    "heat, so rooms cool slowly; "
    "cool_kph is the learned cooling in K per hour without heating. Goal: every area at least "
    "at its target all day; avoid unnecessary heating, comfort has priority. "
    "The local rule (theta = forecast maximum below which heating is needed, puffer = margin above "
    "target an area needs now) and the evaluated history (error A = no heating although too cold, "
    "error B = heating although unnecessary; manual = the day ran under a manual override, "
    "its final is not a decision of the system) are in the data. Learn from recent errors. "
    "Answer with: heating_day, confidence 0-100, reason (max 3 short sentences, no dashes), "
    "critical_area (area id or empty)."
)

CHECK_SYSTEM = (
    "You tune a local underfloor heating controller. You never switch anything; you only "
    "propose parameter values. Per area the controller switches on when the predicted temperature "
    "(after dead_time_min * lead_factor, using the learned cooling rate) falls below "
    "target - hysteresis_on, and switches off when temperature + expected overshoot * overshoot_factor "
    "reaches target + hysteresis_off. Heating pauses after a window was open window_delay_min and "
    "waits the learned recovery time + recovery_bias_min after closing. stats are since the last check: "
    "cold_min = minutes below target - 0.3 K (not airing), max_over = highest K above target, "
    "cycles = switch-ons, on_min = minutes heating. Propose only changes that clearly improve comfort "
    "(too cold) or efficiency (overshoot, short cycling); prefer no change when data is thin. "
    "Values outside the limits are clamped. Reasons: one short sentence each, no dashes."
)


def _lang_hint(language: str) -> str:
    return f" Write all reasons and the summary in {LANGUAGES.get(language, 'English')}."


def nightly_messages(payload: dict[str, Any], language: str) -> tuple[str, str]:
    """Return (system, user) for the nightly decision."""
    return NIGHTLY_SYSTEM + _lang_hint(language), dumps(payload)


def check_messages(payload: dict[str, Any], language: str) -> tuple[str, str]:
    """Return (system, user) for the periodic parameter check."""
    params = {k: f"{p.hint} [{p.unit}]" if p.unit else p.hint for k, p in PARAMS.items()}
    return (
        CHECK_SYSTEM + _lang_hint(language) + " Parameters: " + dumps(params),
        dumps(payload),
    )


def dumps(data: Any) -> str:
    """Compact, deterministic JSON."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)


def r(value: float | None, digits: int = 2) -> float | None:
    """Round for the prompt (fewer tokens)."""
    return None if value is None else round(value, digits)
