"""Daily decision whether heating is needed at all (heating day yes/no).

A local rule proposes a decision, the AI may be asked, and a phase model
decides whose opinion counts. Every day is evaluated afterwards, which
teaches the rule (``theta`` = outdoor maximum below which heating is needed,
``puffer`` = margin above the target an area needs at decision time) and
decides when the local rule may take over.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from .physics import clamp


class Phase(StrEnum):
    """Who leads the heating day decision."""

    AI_LEADS = "ai_leads"
    SHARED = "shared"
    RULE_LEADS = "rule_leads"


class Override(StrEnum):
    """Manual override of today's decision."""

    AUTO = "auto"
    HEAT = "heat_today"
    OFF = "off_today"


class Need(StrEnum):
    """Outcome of the evaluation of a past day."""

    YES = "yes"
    NO = "no"
    UNCLEAR = "unclear"


@dataclass(slots=True)
class RuleSettings:
    """Margins that make the rule 'sure' about its proposal."""

    sure_margin_tmax: float = 2.0
    sure_margin_area: float = 0.5


@dataclass(slots=True)
class EvalSettings:
    """Thresholds of the daily evaluation and learning steps."""

    too_cold_minutes: float = 15.0
    theta_up: float = 1.0
    theta_down: float = 1.0
    puffer_up: float = 0.2
    puffer_down: float = 0.2
    theta_min: float = 10.0
    theta_max: float = 20.0
    puffer_min: float = 0.0
    puffer_max: float = 2.0


@dataclass(slots=True)
class PhaseSettings:
    """Conditions for changing the phase."""

    shared_min_days: int = 14
    shared_min_agreement: float = 0.8
    shared_max_rule_errors: int = 1
    rule_min_days: int = 21
    rule_min_agreement: float = 0.9
    rule_max_rule_errors: int = 1
    fallback_errors_7d: int = 2
    ai_check_every_days: int = 7


@dataclass(slots=True)
class AreaSnapshot:
    """Area values at decision time."""

    area_id: str
    name: str
    temp: float | None
    target: float
    puffer: float


@dataclass(slots=True)
class RuleResult:
    """Proposal of the local rule."""

    heat: bool
    sure: bool
    outdoor_rule: bool
    cold_areas: list[str]
    missing: list[str]
    min_margin: float | None
    tmax: float | None
    theta: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AiDecision:
    """Validated answer of the AI."""

    heat: bool
    confidence: int
    reason: str
    critical_area: str = ""


@dataclass(slots=True)
class DayAreaStats:
    """Counters of one area over one decision day."""

    too_cold_min: float = 0.0
    relay_min: float = 0.0
    window_min: float = 0.0
    observed_min: float = 0.0  # minutes with thermostat on, a temperature and no airing
    emergency: bool = False
    manual_heat: bool = False
    # Counterfactual: temperature the area would have without any heating today
    # (follows the learned cooling, None until the model knows enough) and the minutes
    # that virtual room was too cold.
    virtual_temp: float | None = None
    virtual_cold_min: float = 0.0

    @property
    def cold_min(self) -> float | None:
        """Minutes the area would have been too cold without heating.

        The real room is the truth while nothing heated. Once the circuit ran, the
        virtual room counts as well; None if it is not known yet.
        """
        if self.relay_min <= 0:
            return self.too_cold_min
        if self.virtual_temp is None:
            return None
        return max(self.too_cold_min, self.virtual_cold_min)

    @property
    def known_cold_min(self) -> float:
        """Like ``cold_min``, falling back to the real room when the virtual one is unknown."""
        cold = self.cold_min
        return self.too_cold_min if cold is None else cold

    @property
    def observed(self) -> bool:
        """Did the area deliver any evidence today?"""
        # The relay alone is no evidence: with the thermostat off nothing counts as cold.
        return self.observed_min > 0 or self.too_cold_min > 0 or self.emergency or self.manual_heat

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DayAreaStats:
        stats = cls()
        if data:
            for key in (
                "too_cold_min",
                "relay_min",
                "window_min",
                "observed_min",
                "virtual_cold_min",
            ):
                setattr(stats, key, float(data.get(key, 0.0)))
            stats.emergency = bool(data.get("emergency", False))
            stats.manual_heat = bool(data.get("manual_heat", False))
            virtual = data.get("virtual_temp")
            stats.virtual_temp = float(virtual) if isinstance(virtual, int | float) else None
        return stats


@dataclass
class DayRecord:
    """One evaluated decision day."""

    date: str
    final: bool
    source: str
    rule: bool
    ai: bool | None
    need: str = Need.UNCLEAR
    err_final: str | None = None
    err_rule: str | None = None
    err_ai: str | None = None
    phase: str = Phase.AI_LEADS
    learned: bool = False
    manual: bool = False  # the day ran under a manual override
    vacation: bool = False  # the day ran with the vacation target
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DayRecord:
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)


def rule_proposal(
    tmax: float | None,
    areas: list[AreaSnapshot],
    theta: float,
    settings: RuleSettings,
) -> RuleResult:
    """Local rule: heat if the forecast maximum is below theta or an area is too close to its target."""
    outdoor_rule = tmax is not None and tmax < theta
    cold: list[str] = []
    missing: list[str] = []
    margin: float | None = None
    for area in areas:
        if area.temp is None:
            missing.append(area.area_id)
            continue
        diff = area.temp - (area.target + area.puffer)
        margin = diff if margin is None else min(margin, diff)
        if diff < 0:
            cold.append(area.area_id)
    if tmax is None and margin is None:
        # Nothing known: heating is the safe choice.
        return RuleResult(True, False, False, cold, missing, None, None, theta)
    heat = outdoor_rule or bool(cold)
    if heat:
        sure = (tmax is not None and theta - tmax >= settings.sure_margin_tmax) or (
            margin is not None and margin <= -settings.sure_margin_area
        )
    else:
        sure = (
            tmax is not None
            and tmax - theta >= settings.sure_margin_tmax
            and (margin is None or margin >= settings.sure_margin_area)
        )
    return RuleResult(heat, bool(sure), outdoor_rule, cold, missing, margin, tmax, theta)


def should_ask_ai(
    phase: Phase, rule: RuleResult, days_since_ai: int | None, settings: PhaseSettings
) -> bool:
    """Ask the AI only when it is needed (fewer calls once the rule is reliable)."""
    if phase in (Phase.AI_LEADS, Phase.SHARED):
        return True
    if not rule.sure:
        return True
    return days_since_ai is None or days_since_ai >= settings.ai_check_every_days


def final_decision(phase: Phase, rule: RuleResult, ai: AiDecision | None) -> tuple[bool, str]:
    """Combine rule and AI according to the phase. Returns (heat, source)."""
    if phase == Phase.AI_LEADS:
        if ai is not None:
            return ai.heat, "ai"
        return rule.heat, "rule_fallback"
    if phase == Phase.SHARED:
        if ai is None:
            return rule.heat, "rule_fallback"
        if ai.heat == rule.heat:
            return rule.heat, "agreement"
        if rule.sure:
            return rule.heat, "rule"
        return ai.heat, "ai"
    # Rule leads; a 'heat' from the AI still wins for comfort.
    if ai is not None and ai.heat and not rule.heat:
        return True, "ai"
    return rule.heat, "rule"


def evaluate_need(stats: dict[str, DayAreaStats], settings: EvalSettings) -> Need:
    """Was heating needed on the evaluated day?

    While nothing heated, the real temperature is the truth. Once a circuit ran, the
    room was kept warm by the decision itself; then the counterfactual room (cooling
    without heating) tells whether it would have become too cold. Without it the
    day stays unclear, unless the real room was cold anyway.
    """
    observed = [s for s in stats.values() if s.observed]
    if not observed:
        return Need.UNCLEAR  # thermostats off or no temperature all day: nothing seen
    cold = max(s.known_cold_min for s in observed)
    if cold >= settings.too_cold_minutes or any(s.emergency or s.manual_heat for s in observed):
        return Need.YES
    if any(s.cold_min is None for s in observed):
        return Need.UNCLEAR
    if cold <= 0:
        return Need.NO
    return Need.UNCLEAR


def track_virtual(
    stats: DayAreaStats,
    temp: float,
    minutes: float,
    cool_rate_kph: Callable[[float], float],
    target: float,
    margin: float,
    *,
    ready: bool,
    counting: bool,
    airing: bool,
) -> None:
    """Advance the virtual room of one area by one tick.

    The virtual room starts at the real temperature on the first tick where the model
    is ``ready`` and nothing has heated yet today; later than that it stays unknown.
    It cools with ``cool_rate_kph`` (K/h for a given room temperature) and is never
    warmer than the real room, except while airing, whose dip it must not inherit.
    ``counting`` says whether cold minutes count on this tick (thermostat on, no airing).
    """
    if minutes <= 0:
        return
    if stats.virtual_temp is None:
        if not ready or stats.relay_min > 0:
            return
        stats.virtual_temp = temp
    virtual = stats.virtual_temp - cool_rate_kph(stats.virtual_temp) * minutes / 60
    if not airing:
        virtual = min(temp, virtual)
    stats.virtual_temp = virtual  # not rounded: ticks can be seconds apart
    if counting and virtual < target - margin:
        stats.virtual_cold_min += minutes


def error_of(decision: bool | None, need: Need) -> str | None:
    """'A' = no heating although needed, 'B' = heating although not needed."""
    if decision is None or need == Need.UNCLEAR:
        return None
    if need == Need.YES and not decision:
        return "A"
    if need == Need.NO and decision:
        return "B"
    return None


def learn_rule(
    theta: float,
    puffers: dict[str, float],
    rule: RuleResult,
    need: Need,
    stats: dict[str, DayAreaStats],
    settings: EvalSettings,
) -> tuple[float, dict[str, float], list[str]]:
    """Adapt theta and puffer after an error of the rule (counterfactual: also if it did not decide)."""
    new_theta = theta
    new_puffers = dict(puffers)
    changes: list[str] = []
    err = error_of(rule.heat, need)
    if err == "A":
        new_theta = theta + settings.theta_up
        changes.append("theta")
        for area_id, s in stats.items():
            if s.known_cold_min >= settings.too_cold_minutes and area_id in new_puffers:
                new_puffers[area_id] = new_puffers[area_id] + settings.puffer_up
                changes.append(f"puffer:{area_id}")
    elif err == "B":
        if rule.outdoor_rule:
            new_theta = theta - settings.theta_down
            changes.append("theta")
        else:
            for area_id in rule.cold_areas:
                if area_id in new_puffers:
                    new_puffers[area_id] = new_puffers[area_id] - settings.puffer_down
                    changes.append(f"puffer:{area_id}")
    new_theta = round(clamp(new_theta, settings.theta_min, settings.theta_max), 2)
    new_puffers = {
        k: round(clamp(v, settings.puffer_min, settings.puffer_max), 2)
        for k, v in new_puffers.items()
    }
    return new_theta, new_puffers, changes


def _window(history: list[DayRecord], days: int) -> list[DayRecord]:
    return history[-days:] if days > 0 else []


def agreement(history: list[DayRecord], days: int) -> float | None:
    """Share of days on which rule and AI agreed (days with an AI answer only)."""
    both = [r for r in _window(history, days) if r.ai is not None]
    if not both:
        return None
    return sum(1 for r in both if r.ai == r.rule) / len(both)


def rule_errors(history: list[DayRecord], days: int) -> int:
    """Number of rule errors within the last days (manual override and vacation days do not count)."""
    return sum(1 for r in _window(history, days) if r.err_rule and not r.manual and not r.vacation)


def next_phase(
    phase: Phase, history: list[DayRecord], days_in_phase: int, settings: PhaseSettings
) -> Phase:
    """Advance or fall back one phase."""
    if phase != Phase.AI_LEADS and rule_errors(history, 7) >= settings.fallback_errors_7d:
        return Phase.SHARED if phase == Phase.RULE_LEADS else Phase.AI_LEADS
    evaluated = [r for r in history if r.need != Need.UNCLEAR]
    if phase == Phase.AI_LEADS:
        agree = agreement(history, settings.shared_min_days)
        if (
            len(evaluated) >= settings.shared_min_days
            and agree is not None
            and agree >= settings.shared_min_agreement
            and rule_errors(history, settings.shared_min_days) <= settings.shared_max_rule_errors
        ):
            return Phase.SHARED
    elif phase == Phase.SHARED:
        agree = agreement(history, settings.rule_min_days)
        if (
            days_in_phase >= settings.rule_min_days
            and agree is not None
            and agree >= settings.rule_min_agreement
            and rule_errors(history, settings.rule_min_days) <= settings.rule_max_rule_errors
        ):
            return Phase.RULE_LEADS
    return phase
