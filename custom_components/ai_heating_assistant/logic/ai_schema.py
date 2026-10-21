"""Adjustable parameters, JSON schemas for the AI answers and their validation.

The AI never switches anything. It may only propose new values for the
parameters below; every value is clamped to configurable limits and to a
maximum change per check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .heating_day import AiDecision
from .physics import clamp

GLOBAL = "global"
RELEVANT_SHARE = 0.25  # a change counts as relevant if >= 25 % of the max step


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """One parameter the AI may adjust."""

    key: str
    scope: str  # "area" or "global"
    default: float
    min: float
    max: float
    step: float
    unit: str
    hint: str  # short English description for the prompt


PARAMS: dict[str, ParamSpec] = {
    p.key: p
    for p in (
        ParamSpec(
            "hysteresis_on",
            "area",
            0.2,
            0.0,
            0.6,
            0.1,
            "K",
            "switch on below target minus this (predicted)",
        ),
        ParamSpec(
            "hysteresis_off",
            "area",
            0.0,
            -0.3,
            0.3,
            0.1,
            "K",
            "switch off when expected peak reaches target plus this",
        ),
        ParamSpec("overshoot_factor", "area", 1.0, 0.5, 1.5, 0.1, "", "scales learned overshoot"),
        ParamSpec(
            "lead_factor",
            "area",
            1.0,
            0.5,
            2.0,
            0.2,
            "",
            "scales learned dead time for switch-on prediction",
        ),
        ParamSpec("sun_factor", "area", 1.0, 0.0, 2.0, 0.2, "", "scales learned solar gain"),
        ParamSpec(
            "window_delay_min",
            "area",
            5.0,
            1.0,
            15.0,
            2.0,
            "min",
            "window open time before heating pauses",
        ),
        ParamSpec(
            "recovery_bias_min",
            "area",
            0.0,
            -30.0,
            60.0,
            10.0,
            "min",
            "added to learned recovery time after airing",
        ),
        ParamSpec(
            "puffer",
            "area",
            0.7,
            0.0,
            2.0,
            0.2,
            "K",
            "heating-day rule: needed margin above target at night",
        ),
        ParamSpec(
            "theta",
            GLOBAL,
            16.0,
            10.0,
            20.0,
            1.0,
            "C",
            "heating-day rule: forecast max below this means heating",
        ),
    )
}


# Thresholds of the ventilation recommendation, per area (see logic.ventilation).
VENT_PARAMS: dict[str, ParamSpec] = {
    p.key: p
    for p in (
        ParamSpec(
            "rh_threshold", "area", 60.0, 30.0, 95.0, 3.0, "%", "relative humidity counting as high"
        ),
        ParamSpec(
            "rh_hysteresis",
            "area",
            3.0,
            0.0,
            10.0,
            1.0,
            "%",
            "humidity stays high until this far below rh_threshold",
        ),
        ParamSpec(
            "min_ah_advantage",
            "area",
            0.8,
            0.1,
            5.0,
            0.2,
            "g/m3",
            "reference air must be at least this much drier (absolute) to dry",
        ),
        ParamSpec(
            "max_reference_excess",
            "area",
            4.0,
            0.0,
            15.0,
            1.0,
            "K",
            "drying only while the reference is at most this much warmer",
        ),
        ParamSpec(
            "min_rh_drop",
            "area",
            3.0,
            0.0,
            15.0,
            1.0,
            "%",
            "airing must lower the humidity at least this far (learned effect)",
        ),
        ParamSpec(
            "energy_rh_per_k",
            "area",
            0.25,
            0.0,
            1.0,
            0.05,
            "%/K",
            "heating period: extra humidity above rh_threshold per K colder reference air "
            "before drying is worth its heat (capped at 70 %)",
        ),
        ParamSpec(
            "min_cooling_advantage",
            "area",
            1.0,
            0.0,
            10.0,
            0.5,
            "K",
            "room must be this much warmer than the reference to cool",
        ),
        ParamSpec(
            "cooling_margin",
            "area",
            1.0,
            0.0,
            5.0,
            0.3,
            "K",
            "heating period: cool only this far above target",
        ),
        ParamSpec(
            "cooling_min_temp",
            "area",
            0.0,
            0.0,
            35.0,
            1.0,
            "C",
            "cool only from this room temperature on (0 = off)",
        ),
    )
}
ALL_PARAMS: dict[str, ParamSpec] = {**PARAMS, **VENT_PARAMS}


def default_limits() -> dict[str, dict[str, float]]:
    """Limits as stored in the options (heating and ventilation parameters)."""
    return {k: {"min": p.min, "max": p.max, "step": p.step} for k, p in ALL_PARAMS.items()}


NIGHTLY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "heating_day": {"type": "boolean"},
        "confidence": {"type": "integer"},
        "reason": {"type": "string"},
        "critical_area": {"type": "string"},
    },
    "required": ["heating_day", "confidence", "reason", "critical_area"],
    "additionalProperties": False,
}


def _check_schema(specs: dict[str, ParamSpec]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "adjustments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "parameter": {"type": "string", "enum": sorted(specs)},
                        "value": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["area", "parameter", "value", "reason"],
                    "additionalProperties": False,
                },
            },
            "summary": {"type": "string"},
            "confidence": {"type": "integer"},
        },
        "required": ["adjustments", "summary", "confidence"],
        "additionalProperties": False,
    }


CHECK_SCHEMA: dict[str, Any] = _check_schema(PARAMS)
VENT_CHECK_SCHEMA: dict[str, Any] = _check_schema(VENT_PARAMS)


class AnswerError(ValueError):
    """The AI answer does not match the expected structure."""


def _text(value: Any, limit: int = 500) -> str:
    return str(value).strip()[:limit] if value is not None else ""


def _confidence(value: Any) -> int:
    try:
        return int(clamp(float(value), 0, 100))
    except (TypeError, ValueError) as err:
        raise AnswerError("confidence is not a number") from err


def validate_nightly(data: Any) -> AiDecision:
    """Validate the nightly answer."""
    if not isinstance(data, dict) or not isinstance(data.get("heating_day"), bool):
        raise AnswerError("heating_day missing or not boolean")
    return AiDecision(
        heat=data["heating_day"],
        confidence=_confidence(data.get("confidence")),
        reason=_text(data.get("reason")),
        critical_area=_text(data.get("critical_area"), 60),
    )


@dataclass(slots=True)
class Adjustment:
    """One accepted change."""

    area: str
    parameter: str
    old: float
    new: float
    reason: str
    clamped: bool
    relevant: bool


@dataclass(slots=True)
class CheckResult:
    """Validated periodic check."""

    applied: list[Adjustment]
    rejected: list[str]
    summary: str
    confidence: int

    @property
    def relevant_change(self) -> bool:
        return any(a.relevant for a in self.applied)


def validate_check(
    data: Any,
    current: dict[str, dict[str, float]],
    limits: dict[str, dict[str, float]],
    specs: dict[str, ParamSpec] = PARAMS,
) -> CheckResult:
    """Validate a periodic check and clamp every proposed value.

    ``current`` maps area ids (and ``GLOBAL``) to their current parameter values,
    ``specs`` are the parameters this check may adjust.
    """
    if not isinstance(data, dict) or not isinstance(data.get("adjustments"), list):
        raise AnswerError("adjustments missing")
    applied: list[Adjustment] = []
    rejected: list[str] = []
    seen: set[tuple[str, str]] = set()
    for item in data["adjustments"]:
        if not isinstance(item, dict):
            rejected.append("item is not an object")
            continue
        key = item.get("parameter")
        spec = specs.get(key) if isinstance(key, str) else None
        if spec is None:
            rejected.append(f"unknown parameter {key!r}")
            continue
        area = GLOBAL if spec.scope == GLOBAL else str(item.get("area", ""))
        if area not in current or key not in current[area]:
            rejected.append(f"unknown area {item.get('area')!r} for {key}")
            continue
        if (area, key) in seen:
            rejected.append(f"duplicate {key} for {area}")
            continue
        try:
            wanted = float(item.get("value"))
        except (TypeError, ValueError):
            rejected.append(f"value of {key} is not a number")
            continue
        limit = limits.get(key, {})
        low = float(limit.get("min", spec.min))
        high = float(limit.get("max", spec.max))
        step = abs(float(limit.get("step", spec.step)))
        old = float(current[area][key])
        new = clamp(wanted, low, high)
        new = clamp(new, old - step, old + step)
        # A value outside narrowed limits must not stay outside by the step limit.
        new = round(clamp(new, low, high), 3)
        if abs(new - old) < 1e-6:
            continue
        seen.add((area, key))
        applied.append(
            Adjustment(
                area=area,
                parameter=key,
                old=old,
                new=new,
                reason=_text(item.get("reason"), 300),
                clamped=abs(new - wanted) > 1e-6,
                relevant=abs(new - old) >= RELEVANT_SHARE * step if step > 0 else True,
            )
        )
    return CheckResult(
        applied, rejected, _text(data.get("summary")), _confidence(data.get("confidence"))
    )
