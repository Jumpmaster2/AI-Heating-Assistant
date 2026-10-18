"""Heat meter: consumption between meter readings (pure logic).

A heat meter often reports seldom and in coarse steps (e.g. every two hours in
MWh). Consumption is therefore always taken between two readings, never between
arbitrary points in time, and the heating demand (Kelvin hours of target minus
outdoor temperature) is kept along with every reading so both cover exactly the
same span.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Factor to kWh per unit of the meter entity.
UNIT_TO_KWH = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0, "MJ": 1 / 3.6, "GJ": 1000 / 3.6}
MIN_HOURS = 1.0  # shorter spans between readings are too coarse to report
EPS = 1e-9


def to_kwh(value: float, unit: str | None) -> float | None:
    """Meter value in kWh, None for an unknown unit."""
    factor = UNIT_TO_KWH.get(unit or "")
    return None if factor is None else value * factor


@dataclass(slots=True)
class Reading:
    """One meter reading with the cumulative heating demand at that time."""

    kwh: float
    ts: float
    demand_kh: float

    def as_dict(self) -> dict[str, float]:
        return {"kwh": self.kwh, "ts": self.ts, "demand_kh": self.demand_kh}

    @classmethod
    def from_dict(cls, data: Any) -> Reading | None:
        try:
            return cls(float(data["kwh"]), float(data["ts"]), float(data["demand_kh"]))
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(slots=True)
class Span:
    """Consumption between two readings."""

    kwh: float
    hours: float
    demand_kh: float

    @property
    def kwh_per_kh(self) -> float | None:
        """kWh per Kelvin hour of heating demand (lower is more efficient)."""
        return self.kwh / self.demand_kh if self.demand_kh >= 1 else None


@dataclass
class HeatMeter:
    """Latest reading, a running demand counter and named baselines."""

    demand_kh: float = 0.0  # cumulative, only ever grows
    last: Reading | None = None
    baselines: dict[str, Reading] = field(default_factory=dict)
    closed: dict[str, float] = field(default_factory=dict)  # finished periods, e.g. yesterday
    marks: dict[str, str] = field(default_factory=dict)  # current calendar period per name
    entity: str = ""  # meter entity the readings come from

    def add_demand(self, kelvin_hours: float) -> None:
        if kelvin_hours > 0:
            self.demand_kh += kelvin_hours

    def update(self, kwh: float, ts: float) -> bool:
        """Take a meter value. Returns True if it is a new reading.

        A falling value means a reset or a new meter: every baseline starts again
        from it, the consumption until then is lost.
        """
        if self.last is not None and abs(kwh - self.last.kwh) < EPS:
            return False
        reset = self.last is not None and kwh < self.last.kwh
        self.last = Reading(kwh, ts, self.demand_kh)
        if reset:
            self.baselines = dict.fromkeys(self.baselines, self.last)
        return True

    def rebase(self, name: str) -> None:
        """Start the named period at the latest reading (or the next one)."""
        if self.last is None:
            self.baselines.pop(name, None)
        else:
            self.baselines[name] = self.last

    def since(self, name: str, min_hours: float = MIN_HOURS) -> Span | None:
        """Consumption from the named baseline to the latest reading."""
        base = self.baselines.get(name)
        if base is None:
            if self.last is not None:
                self.baselines[name] = self.last  # the period starts with the first reading
            return None
        if self.last is None:
            return None
        hours = (self.last.ts - base.ts) / 3600
        if hours < min_hours:
            return None
        return Span(
            max(0.0, self.last.kwh - base.kwh),
            hours,
            max(0.0, self.last.demand_kh - base.demand_kh),
        )

    def kwh_since(self, name: str) -> float | None:
        """kWh of the named period so far, also for short spans."""
        span = self.since(name, min_hours=0.0)
        return None if span is None else round(span.kwh, 1)

    def roll(self, name: str, mark: str, closed_as: str, previous: str | None) -> None:
        """Start a calendar period (day, month) when ``mark`` changes.

        The finished period is kept under ``closed_as`` if it was the one just
        before (``previous``); after a gap nothing is known about it.
        """
        old = self.marks.get(name)
        if old == mark:
            return
        kwh = self.kwh_since(name) if old is not None and old == previous else None
        if kwh is None:
            self.closed.pop(closed_as, None)
        else:
            self.closed[closed_as] = kwh
        self.marks[name] = mark
        self.rebase(name)

    def as_dict(self) -> dict[str, Any]:
        return {
            "demand_kh": self.demand_kh,
            "last": self.last.as_dict() if self.last else None,
            "baselines": {k: v.as_dict() for k, v in self.baselines.items()},
            "closed": dict(self.closed),
            "marks": dict(self.marks),
            "entity": self.entity,
        }

    @classmethod
    def from_dict(cls, data: Any) -> HeatMeter:
        meter = cls()
        if not isinstance(data, dict):
            return meter
        try:
            meter.demand_kh = float(data.get("demand_kh", 0.0))
        except (TypeError, ValueError):
            meter.demand_kh = 0.0
        meter.last = Reading.from_dict(data.get("last"))
        for name, value in (data.get("baselines") or {}).items():
            if (reading := Reading.from_dict(value)) is not None:
                meter.baselines[str(name)] = reading
        for name, value in (data.get("closed") or {}).items():
            if isinstance(value, int | float):
                meter.closed[str(name)] = float(value)
        meter.marks = {str(k): str(v) for k, v in (data.get("marks") or {}).items()}
        meter.entity = str(data.get("entity") or "")
        return meter
