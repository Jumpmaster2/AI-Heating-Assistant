"""Short prompts for the AI. Data is sent as compact JSON to keep costs low."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .ai_schema import PARAMS, VENT_PARAMS, ParamSpec

LANGUAGES = {"de": "German", "en": "English"}

# How the heating type of an area (field "type") behaves.
TYPES_HINT = (
    "Each area has a type: underfloor (the floor stores heat for hours, so rooms cool slowly "
    "and react late), radiator (heats and cools within minutes to an hour, little stored heat) "
    "or other (in between, e.g. wall heating)."
)


@dataclass(frozen=True, slots=True)
class PromptBlock:
    """A standard building block of a system prompt; it can be switched off or reworded."""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class PromptSpec:
    """System prompt of one AI call: a fixed head and tail around the blocks.

    Head and tail hold the task and the answer format, so they stay fixed and the
    answer keeps matching the schema.
    """

    head: str
    blocks: tuple[PromptBlock, ...]
    tail: str


NIGHTLY = "nightly"
CHECK = "check"
VENT = "ventilation"
MAX_CUSTOM_BLOCKS = 10
MAX_BLOCK_CHARS = 2000
CUSTOM_HEAD = "Additional instructions from the user:"

PROMPTS: dict[str, PromptSpec] = {
    NIGHTLY: PromptSpec(
        head=(
            "You decide once per night whether a heating system is needed today "
            "(from now until the same time tomorrow)."
        ),
        blocks=(
            PromptBlock(
                "rules",
                "Each area has its own on/off circuit; the local controller keeps every area at "
                "its target on heating days. On a no-heating day all circuits stay off except "
                "frost protection and an emergency rule (temperature expected after the lead "
                "time long and clearly below target, without airing).",
            ),
            PromptBlock("types", TYPES_HINT),
            PromptBlock(
                "goal",
                "cool_kph is the learned cooling in K per hour without heating. Goal: every area "
                "at least at its target all day; comfort has priority, but every unnecessary "
                "heating day costs energy. With enough margin the stored heat (rooms, and floors "
                "in particular) often carries a day without heating.",
            ),
            PromptBlock(
                "data",
                "The local rule (theta = forecast maximum below which heating is needed, puffer "
                "= margin above target an area needs now) and the evaluated history (error A = "
                "no heating although too cold, error B = heating although unnecessary; manual = "
                "the day ran under a manual override, its final is not a decision of the system; "
                "on_min = minutes heated by all circuits, over_kh = Kelvin hours above target "
                "after heating, i.e. wasted heat; kwh = heat measured by the heat meter, if "
                "present) are in the data. window_open also covers draft through windows open "
                "in other rooms (draft).",
            ),
            PromptBlock("learn", "Learn from recent errors."),
        ),
        tail=(
            "Answer with: heating_day, confidence 0-100, reason (max 3 short sentences, no "
            "dashes), critical_area (area id or empty)."
        ),
    ),
    CHECK: PromptSpec(
        head=(
            "You tune a local heating controller to use as little heat as possible while every "
            "area stays at its target. You never switch anything; you only propose parameter "
            "values."
        ),
        blocks=(
            PromptBlock("types", TYPES_HINT),
            PromptBlock(
                "controller",
                "Per area the controller switches on when the predicted temperature (after "
                "dead_time_min * lead_factor, using the learned cooling rate) falls below target "
                "- hysteresis_on, and switches off when temperature + expected overshoot * "
                "overshoot_factor reaches target + hysteresis_off. Heating pauses after a window "
                "(or a draft through windows open in other rooms) was open window_delay_min and "
                "waits the learned recovery time + recovery_bias_min after closing.",
            ),
            PromptBlock(
                "stats",
                "stats are since the last check: cold_min = minutes below target - 0.3 K (not "
                "airing), max_over = highest K above target, over_kh = Kelvin hours more than "
                "0.2 K above target within 4 h after heating (wasted heat), sun_over_kh = part "
                "of over_kh with notable sun, on_per_kh = heating minutes per Kelvin hour of "
                "heating demand (target minus outdoor; lower is more efficient), cycles = "
                "switch-ons, on_min = minutes heating, avg_run_min = average run. heat (if a "
                "heat meter exists) is the measured heat of all circuits between two meter "
                "readings since the last check: kwh, hours and kwh_per_kh = kWh per Kelvin hour "
                "of demand, the best efficiency measure; the meter reports seldom and coarsely, "
                "so trust it over longer spans and the history more than one check.",
            ),
            PromptBlock(
                "comfort",
                "Comfort is a hard limit, not the goal: cold_min must stay near 0, never trade "
                "it for savings. Within that, reduce over_kh and on_per_kh.",
            ),
            PromptBlock(
                "levers",
                "Levers: over_kh high without sun: raise overshoot_factor or lower "
                "hysteresis_off; sun_over_kh high: raise sun_factor; cold_min > 0: raise "
                "lead_factor or lower hysteresis_on; very short avg_run_min with many cycles and "
                "cold_min 0: raise hysteresis_on a little.",
            ),
            PromptBlock(
                "history",
                "history lists earlier checks, oldest first, each with the stats of its period "
                "and the changes made at its end; judge the effect of a change by the periods "
                "after it and undo a change that cost comfort or saved nothing.",
            ),
            PromptBlock(
                "changes",
                "At most two changes per area; prefer no change when data is thin. Values "
                "outside the limits are clamped.",
            ),
        ),
        tail="Reasons: one short sentence each, no dashes.",
    ),
    VENT: PromptSpec(
        head=(
            "You tune the local ventilation recommendation of a home, separately for every "
            "area. You never open or close anything; you only propose parameter values."
        ),
        blocks=(
            PromptBlock(
                "rules",
                "Per area the recommendation compares the room with its reference air (outdoor, "
                "or another room if ref is indoor) by absolute humidity (ah, g/m3). Humidity is "
                "high from rh_threshold on and stays high until it falls below rh_threshold - "
                "rh_hysteresis. ventilate_now: humidity high, reference air at least "
                "min_ah_advantage drier, at most max_reference_excess warmer, and the humidity "
                "an airing reaches (achievable_now, from the learned profile) at least "
                "min_rh_drop below the current one; in the heating period airing costs heat, so the "
                "humidity must also exceed rh_threshold by energy_rh_per_k per K the reference "
                "is colder than the room (capped at 70 %), otherwise energy_hold. "
                "ventilation_useful: cooling, the room is "
                "min_cooling_advantage warmer than the reference, nobody heats, in the heating "
                "period only cooling_margin above target and from cooling_min_temp on, and "
                "only if the humidity after the exchange stays below rh_threshold. "
                "do_not_ventilate: humidity high but airing does not help. close_window: a "
                "window is open although airing brings nothing.",
            ),
            PromptBlock(
                "profile",
                "profile is learned from the sensors of each area: typical = usual daily "
                "minimum, mean, maximum, day and night mean of the relative humidity (and mean "
                "ah) in this season over days days; floor_14d = lowest humidity of the last 14 "
                "days, airing included; achievable_now = humidity a usual airing leaves now "
                "once moisture from walls came back; load_gph = rise of ah per hour with "
                "windows closed; airing.share = part of the difference to the reference air "
                "an airing removes, rebound = part of that coming back within 30 minutes; "
                "last_airings = recent airings (minutes, humidity at start, lowest, 30 "
                "minutes after closing).",
            ),
            PromptBlock(
                "ranges",
                "Choose the thresholds of each area from its own profile, not from textbook "
                "values: a bathroom or a cellar can be humid by nature, and some humidity "
                "cannot be aired away. Put rh_threshold above the usual level of the room "
                "where airing really helps, with enough distance to floor_14d and "
                "achievable_now; an alarm that airing can never clear is useless.",
            ),
            PromptBlock(
                "stats",
                "stats are since the last check: minutes observed, humid_min = minutes with "
                "high humidity, mould_min = minutes at 70 % or more, rh_mean and rh_max, "
                "rec_min = minutes airing was recommended, window_min = minutes an own window "
                "was open, window_rec_min = of that while recommended, useless_min = minutes "
                "the window was open although airing brought nothing, heat_window_min = "
                "minutes open while the area was heated, blocked_min = minutes a blocking "
                "entity held back the recommendation, energy_hold_min = minutes drying would help "
                "but was held back to save heat, flips = changes of the recommendation "
                "(many flips annoy the residents).",
            ),
            PromptBlock(
                "goal",
                "Protection against mould is the hard limit: humidity of 70 % or more must not "
                "last, and rooms must not stay humid for long. Within that, avoid "
                "recommendations that bring little and save heating energy: in the heating period "
                "a room only slightly above its threshold waits for milder air or clearly "
                "higher humidity, and airing is short and intense (heat_window_min, "
                "useless_min). Avoid flipping and keep recommendations few and clear.",
            ),
            PromptBlock(
                "levers",
                "Levers: humid for long or mould_min > 0: lower rh_threshold or "
                "min_ah_advantage, if the profile shows that airing helps; recommendations "
                "that barely lower the humidity: raise min_rh_drop or min_ah_advantage; many "
                "flips: raise rh_hysteresis; airing too often in the heating period without "
                "need: raise rh_threshold towards the usual level or raise energy_rh_per_k; a room "
                "humid for long while energy_hold_min is high: lower energy_rh_per_k; summer overheating: lower "
                "min_cooling_advantage or cooling_min_temp.",
            ),
            PromptBlock(
                "history",
                "history lists earlier checks, oldest first, each with key stats of its period "
                "and the changes made at its end; judge a change by the periods after it and "
                "undo a change that made things worse.",
            ),
            PromptBlock(
                "changes",
                "At most two changes per area; prefer no change when data is thin (few days "
                "in the profile, short stats). Values outside the limits are clamped.",
            ),
        ),
        tail="Reasons: one short sentence each, no dashes.",
    ),
}


def block_ids(kind: str) -> tuple[str, ...]:
    return tuple(b.id for b in PROMPTS[kind].blocks)


def build_system(kind: str, config: dict[str, Any] | None = None) -> str:
    """System prompt of an AI call from its blocks and the user configuration.

    ``config`` is the stored entry of this call: ``disabled`` (ids of standard blocks
    left out), ``overrides`` (id -> own wording) and ``custom`` (own blocks, each with
    ``text`` and ``enabled``). Without a configuration the standard prompt results.
    """
    spec = PROMPTS[kind]
    config = config or {}
    disabled = set(config.get("disabled") or ())
    overrides = config.get("overrides") or {}
    parts = [spec.head]
    for block in spec.blocks:
        if block.id not in disabled:
            parts.append(str(overrides.get(block.id) or block.text).strip())
    custom = [
        str(c.get("text") or "").strip()
        for c in config.get("custom") or ()
        if isinstance(c, dict) and c.get("enabled", True)
    ]
    text = " ".join(p for p in parts if p)
    if custom := [c for c in custom if c]:
        # own blocks as a list of their own, so they do not run into the answer format
        return "\n".join([text, CUSTOM_HEAD, *(f"- {c}" for c in custom), spec.tail])
    return f"{text} {spec.tail}"


class PromptError(ValueError):
    """Invalid prompt configuration; the message is the error code for the panel."""


def clean_prompts(value: Any) -> dict[str, Any]:
    """Validated prompt configuration of all calls; raises PromptError.

    Unchanged parts are left out: a wording equal to the standard text, empty own
    blocks and calls without any change.
    """
    if not isinstance(value, dict):
        raise PromptError("invalid_value")
    result: dict[str, Any] = {}
    for kind, config in value.items():
        if kind not in PROMPTS or not isinstance(config, dict):
            raise PromptError("invalid_value")
        standard = {b.id: b.text for b in PROMPTS[kind].blocks}
        disabled = config.get("disabled") or []
        overrides = config.get("overrides") or {}
        custom = config.get("custom") or []
        if not isinstance(disabled, list) or not isinstance(overrides, dict):
            raise PromptError("invalid_value")
        if not isinstance(custom, list):
            raise PromptError("invalid_value")
        if any(i not in standard for i in (*disabled, *overrides)):
            raise PromptError("invalid_value")
        clean: dict[str, Any] = {}
        if disabled:
            clean["disabled"] = [i for i in standard if i in disabled]
        texts = {}
        for key, text in overrides.items():
            text = _text(text)
            if text and text != standard[key]:
                texts[key] = text
        if texts:
            clean["overrides"] = texts
        blocks = []
        for item in custom:
            if not isinstance(item, dict):
                raise PromptError("invalid_value")
            if text := _text(item.get("text")):
                blocks.append({"text": text, "enabled": bool(item.get("enabled", True))})
        if len(blocks) > MAX_CUSTOM_BLOCKS:
            raise PromptError("too_many_blocks")
        if blocks:
            clean["custom"] = blocks
        if clean:
            result[kind] = clean
    return result


def _text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise PromptError("invalid_value")
    text = value.strip()
    if len(text) > MAX_BLOCK_CHARS:
        raise PromptError("text_too_long")
    return text


def prompt_defaults() -> dict[str, Any]:
    """Fixed parts and standard blocks of all calls, for the panel."""
    return {
        kind: {
            "head": spec.head,
            "tail": spec.tail,
            "custom_head": CUSTOM_HEAD,
            "blocks": [{"id": b.id, "text": b.text} for b in spec.blocks],
        }
        for kind, spec in PROMPTS.items()
    }


def _lang_hint(language: str) -> str:
    """Language of the free text answers: the Home Assistant language, regional
    variants included (de-CH is German); another code is passed on as it is."""
    code = (language or "en").strip()
    name = LANGUAGES.get(code.split("-")[0].split("_")[0].lower())
    if name is None:
        name = f"the language with the code '{code}'"
    return f" Write all reasons and the summary in {name}."


def nightly_messages(
    payload: dict[str, Any], language: str, prompts: dict[str, Any] | None = None
) -> tuple[str, str]:
    """Return (system, user) for the nightly decision. ``prompts`` is the stored
    prompt configuration of all calls."""
    config = (prompts or {}).get(NIGHTLY)
    return build_system(NIGHTLY, config) + _lang_hint(language), dumps(payload)


def _param_hints(specs: dict[str, ParamSpec]) -> str:
    return dumps({k: f"{p.hint} [{p.unit}]" if p.unit else p.hint for k, p in specs.items()})


def check_messages(
    payload: dict[str, Any], language: str, prompts: dict[str, Any] | None = None
) -> tuple[str, str]:
    """Return (system, user) for the periodic parameter check."""
    config = (prompts or {}).get(CHECK)
    return (
        build_system(CHECK, config) + _lang_hint(language) + " Parameters: " + _param_hints(PARAMS),
        dumps(payload),
    )


def vent_check_messages(
    payload: dict[str, Any], language: str, prompts: dict[str, Any] | None = None
) -> tuple[str, str]:
    """Return (system, user) for the periodic check of the ventilation parameters."""
    config = (prompts or {}).get(VENT)
    return (
        build_system(VENT, config)
        + _lang_hint(language)
        + " Parameters: "
        + _param_hints(VENT_PARAMS),
        dumps(payload),
    )


def dumps(data: Any) -> str:
    """Compact, deterministic JSON."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)


def r(value: float | None, digits: int = 2) -> float | None:
    """Round for the prompt (fewer tokens)."""
    return None if value is None else round(value, digits)
