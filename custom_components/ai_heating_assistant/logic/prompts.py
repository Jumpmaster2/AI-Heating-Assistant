"""Short prompts for the AI. Data is sent as compact JSON to keep costs low."""

from __future__ import annotations

import json
from typing import Any

from .ai_schema import PARAMS

LANGUAGES = {"de": "German", "en": "English"}

# How the heating type of an area (field "type") behaves.
TYPES_HINT = (
    "Each area has a type: underfloor (the floor stores heat for hours, so rooms cool slowly "
    "and react late), radiator (heats and cools within minutes to an hour, little stored heat) "
    "or other (in between, e.g. wall heating). "
)

NIGHTLY_SYSTEM = (
    "You decide once per night whether a heating system is needed today "
    "(from now until the same time tomorrow). Each area has its own on/off circuit; "
    "the local controller keeps every area at its target on heating days. On a no-heating day "
    "all circuits stay off except frost protection and an emergency rule (temperature expected "
    "after the lead time long and clearly below target, without airing). "
    + TYPES_HINT
    + "cool_kph is the learned cooling in K per hour without heating. Goal: every area at least "
    "at its target all day; comfort has priority, but every unnecessary heating day costs energy. "
    "With enough margin the stored heat (rooms, and floors in particular) often carries a day "
    "without heating. "
    "The local rule (theta = forecast maximum below which heating is needed, puffer = margin above "
    "target an area needs now) and the evaluated history (error A = no heating although too cold, "
    "error B = heating although unnecessary; manual = the day ran under a manual override, "
    "its final is not a decision of the system; on_min = minutes heated by all circuits, "
    "over_kh = Kelvin hours above target after heating, i.e. wasted heat; kwh = heat measured by "
    "the heat meter, if present) are in the data. "
    "Learn from recent errors. "
    "Answer with: heating_day, confidence 0-100, reason (max 3 short sentences, no dashes), "
    "critical_area (area id or empty)."
)

CHECK_SYSTEM = (
    "You tune a local heating controller to use as little heat as possible while "
    "every area stays at its target. You never switch anything; you only propose parameter values. "
    + TYPES_HINT
    + "Per area the controller switches on when the predicted temperature "
    "(after dead_time_min * lead_factor, using the learned cooling rate) falls below "
    "target - hysteresis_on, and switches off when temperature + expected overshoot * overshoot_factor "
    "reaches target + hysteresis_off. Heating pauses after a window was open window_delay_min and "
    "waits the learned recovery time + recovery_bias_min after closing. stats are since the last check: "
    "cold_min = minutes below target - 0.3 K (not airing), max_over = highest K above target, "
    "over_kh = Kelvin hours more than 0.2 K above target within 4 h after heating (wasted heat), "
    "sun_over_kh = part of over_kh with notable sun, on_per_kh = heating minutes per Kelvin hour of "
    "heating demand (target minus outdoor; lower is more efficient), cycles = switch-ons, "
    "on_min = minutes heating, avg_run_min = average run. heat (if a heat meter exists) is the "
    "measured heat of all circuits between two meter readings since the last check: kwh, hours "
    "and kwh_per_kh = kWh per Kelvin hour of demand, the best efficiency measure; the meter "
    "reports seldom and coarsely, so trust it over longer spans and the history more than one check. "
    "Comfort is a hard limit, not the goal: cold_min must stay near 0, never trade it for savings. "
    "Within that, reduce over_kh and on_per_kh. Levers: over_kh high without sun: raise "
    "overshoot_factor or lower hysteresis_off; sun_over_kh high: raise sun_factor; cold_min > 0: "
    "raise lead_factor or lower hysteresis_on; very short avg_run_min with many cycles and "
    "cold_min 0: raise hysteresis_on a little. history lists earlier checks, oldest first, each with the stats of its period "
    "and the changes made at its end; judge the effect of a change by the periods after it and "
    "undo a change that cost comfort or saved nothing. At most two changes per area; prefer no "
    "change when data is thin. Values outside the limits are clamped. "
    "Reasons: one short sentence each, no dashes."
)


def _lang_hint(language: str) -> str:
    """Language of the free text answers: the Home Assistant language, regional
    variants included (de-CH is German); another code is passed on as it is."""
    code = (language or "en").strip()
    name = LANGUAGES.get(code.split("-")[0].split("_")[0].lower())
    if name is None:
        name = f"the language with the code '{code}'"
    return f" Write all reasons and the summary in {name}."


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
