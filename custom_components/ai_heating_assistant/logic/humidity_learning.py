"""Learned humidity profile of one area: what is usual, how low it gets and what
airing really achieves.

Textbook thresholds do not fit every room: a bathroom is humid after every shower, a
cellar never gets dry, and in some weather airing lowers the humidity only a little.
The profile learns from the measured values

* the usual daily course per season (heating period / rest of the year): daily
  minimum, mean and maximum of the relative humidity, by day and at night,
* the floor: the lowest relative humidity of the last days, airing included,
* the moisture load: how fast the absolute humidity rises with the windows closed,
* the effect of an airing: which share of the difference to the reference air an
  airing removes, how fast, and how much of it comes back after closing (walls and
  furniture release moisture again).

The local recommendation uses the humidity an airing is expected to reach; the AI
gets the whole profile to choose thresholds that fit the room.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .learning import Ewma
from .physics import absolute_humidity, clamp

SEASONS = ("heating", "summer")
TYPICAL_KEYS = ("rh_min", "rh_mean", "rh_max", "rh_day", "rh_night", "ah_mean")
FLOOR_DAYS = 14  # days whose minimum makes the floor
EVENT_COUNT = 5  # airings kept for the AI
MIN_AIRING_S = 120.0  # shorter openings say nothing about airing
REBOUND_S = 1800.0  # s after closing at which the rebound is judged
MIN_GAP = 0.5  # g/m³ the room must be above the reference to judge an airing
MIN_DROP = 0.2  # g/m³ an airing must remove before its rebound counts
MIN_AIRINGS = 2  # judged airings before the expected effect is used
MIN_DAY_SAMPLES = 360  # samples (minutes) a day needs to count for the usual course
TYPICAL_ALPHA = 0.1  # the usual course follows the season slowly
EFFECT_ALPHA = 0.2


def _ewma(data: Any, default: float, alpha: float) -> Ewma:
    ewma = Ewma.from_dict(data if isinstance(data, dict) else None, default)
    ewma.alpha_min = alpha
    return ewma


def _learn(ewma: Ewma, value: float) -> None:
    """Add an observation; the first one replaces the meaningless start value."""
    if ewma.count == 0:
        ewma.value, ewma.count = value, 1
    else:
        ewma.add(value)


def _num(value: Any) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


@dataclass(slots=True)
class DayStats:
    """Running statistics of the current local day."""

    date: str = ""
    season: str = SEASONS[0]
    n: int = 0
    rh_sum: float = 0.0
    rh_min: float = 100.0
    rh_max: float = 0.0
    ah_sum: float = 0.0
    night_n: int = 0
    night_sum: float = 0.0

    def add(self, rh: float, ah: float, is_night: bool) -> None:
        self.n += 1
        self.rh_sum += rh
        self.ah_sum += ah
        self.rh_min = min(self.rh_min, rh)
        self.rh_max = max(self.rh_max, rh)
        if is_night:
            self.night_n += 1
            self.night_sum += rh

    def values(self) -> dict[str, float | None]:
        """Key figures of the day, as in ``TYPICAL_KEYS``."""
        day_n = self.n - self.night_n
        return {
            "rh_min": self.rh_min,
            "rh_mean": self.rh_sum / self.n,
            "rh_max": self.rh_max,
            "rh_day": (self.rh_sum - self.night_sum) / day_n if day_n else None,
            "rh_night": self.night_sum / self.night_n if self.night_n else None,
            "ah_mean": self.ah_sum / self.n,
        }

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> DayStats:
        day = cls()
        if isinstance(data, dict):
            day.date = str(data.get("date", ""))
            day.season = str(data.get("season", SEASONS[0]))
            for key in ("n", "night_n"):
                setattr(day, key, int(_num(data.get(key)) or 0))
            for key in ("rh_sum", "rh_min", "rh_max", "ah_sum", "night_sum"):
                if (value := _num(data.get(key))) is not None:
                    setattr(day, key, value)
        return day


@dataclass
class HumidityProfile:
    """Learned humidity behaviour of one area."""

    typical: dict[str, dict[str, Ewma]] = field(
        default_factory=lambda: {
            s: {k: _ewma(None, 0.0, TYPICAL_ALPHA) for k in TYPICAL_KEYS} for s in SEASONS
        }
    )
    floor: list[list[Any]] = field(default_factory=list)  # [date, lowest rh] per day
    load: Ewma = field(default_factory=lambda: _ewma(None, 0.0, EFFECT_ALPHA))
    exchange: Ewma = field(default_factory=lambda: _ewma(None, 0.5, EFFECT_ALPHA))
    rebound: Ewma = field(default_factory=lambda: _ewma(None, 0.2, EFFECT_ALPHA))
    drop_rate: Ewma = field(default_factory=lambda: _ewma(None, 0.0, EFFECT_ALPHA))
    events: list[dict[str, Any]] = field(default_factory=list)
    day: DayStats = field(default_factory=DayStats)
    hour: list[float] | None = None  # [start ts, absolute humidity] of the load sample
    airing: dict[str, Any] | None = None  # airing in progress
    pending: dict[str, Any] | None = None  # closed airing waiting for its rebound

    # ------------------------------------------------------------------ learning

    def add_sample(
        self,
        ts: float,
        date: str,
        season: str,
        is_night: bool,
        temp: float | None,
        rh: float | None,
        ah_ref: float | None,
        window_open: bool,
    ) -> None:
        """One measurement (every minute). ``date`` is the local date, ``season`` one
        of ``SEASONS``, ``ah_ref`` the absolute humidity of the reference air."""
        if date != self.day.date:
            self._close_day()
            self.day = DayStats(date=date, season=season)
        if temp is None or rh is None:
            self.hour = None
            return
        ah = absolute_humidity(temp, rh)
        self.day.add(rh, ah, is_night)
        if window_open:
            self.hour = None
            self.pending = None  # opened again: the rebound cannot be judged
            if self.airing is None:
                self.airing = {
                    "ts": ts,
                    "ah": ah,
                    "rh": rh,
                    "ah_ref": ah_ref,
                    "min_ah": ah,
                    "min_rh": rh,
                }
            else:
                self.airing["min_ah"] = min(self.airing["min_ah"], ah)
                self.airing["min_rh"] = min(self.airing["min_rh"], rh)
            return
        if self.airing is not None:
            self._close_airing(ts)
        if self.pending is not None:
            if ts - self.pending["closed"] >= REBOUND_S:
                self._judge_rebound(ah, rh)
            return  # the load is not measured while the room recovers from airing
        if self.hour is None:
            self.hour = [ts, ah]
        elif ts - self.hour[0] >= 3600:
            rise = (ah - self.hour[1]) * 3600 / (ts - self.hour[0])
            _learn(self.load, max(0.0, rise))
            self.hour = [ts, ah]

    def _close_day(self) -> None:
        day = self.day
        if not day.date or day.n == 0:
            return
        self.floor = [*self.floor, [day.date, round(day.rh_min, 1)]][-FLOOR_DAYS:]
        if day.n < MIN_DAY_SAMPLES or day.season not in self.typical:
            return
        typical = self.typical[day.season]
        for key, value in day.values().items():
            if value is not None:
                _learn(typical[key], value)

    def _close_airing(self, ts: float) -> None:
        airing, self.airing = self.airing, None
        assert airing is not None
        seconds = ts - airing["ts"]
        if seconds < MIN_AIRING_S:
            return
        drop = airing["ah"] - airing["min_ah"]
        event: dict[str, Any] = {
            "min": round(seconds / 60),
            "rh_start": round(airing["rh"], 1),
            "rh_min": round(airing["min_rh"], 1),
            "ah_drop": round(drop, 2),
        }
        ah_ref = airing["ah_ref"]
        if ah_ref is not None and airing["ah"] - ah_ref >= MIN_GAP:
            self.exchange.add(clamp(drop / (airing["ah"] - ah_ref), 0.0, 1.0))
            _learn(self.drop_rate, drop / (seconds / 60))
            event["share"] = round(clamp(drop / (airing["ah"] - ah_ref), 0.0, 1.0), 2)
        self.events = [*self.events, event][-EVENT_COUNT:]
        self.pending = {"closed": ts, "drop": drop, "min_ah": airing["min_ah"]}

    def _judge_rebound(self, ah: float, rh: float) -> None:
        pending, self.pending = self.pending, None
        assert pending is not None
        if self.events:
            self.events[-1]["rh_after_30"] = round(rh, 1)
        if pending["drop"] >= MIN_DROP:
            self.rebound.add(clamp((ah - pending["min_ah"]) / pending["drop"], 0.0, 1.0))

    # ------------------------------------------------------------------ use

    @property
    def known_effect(self) -> bool:
        return self.exchange.count >= MIN_AIRINGS

    @property
    def floor_rh(self) -> float | None:
        values = [float(v) for _, v in self.floor]
        return min(values) if values else None

    def achievable_rh(
        self, temp: float | None, rh: float | None, ah_ref: float | None
    ) -> float | None:
        """Relative humidity a usual airing leaves once the rebound has passed, or None
        while the effect of airing is not known yet."""
        if not self.known_effect or None in (temp, rh, ah_ref):
            return None
        assert temp is not None and rh is not None and ah_ref is not None
        ah = absolute_humidity(temp, rh)
        gap = ah - ah_ref
        if gap <= 0:
            return rh
        lasting = self.exchange.value * (1.0 - self.rebound.value)
        return 100.0 * (ah - lasting * gap) / absolute_humidity(temp, 100.0)

    def summary(
        self, season: str, temp: float | None, rh: float | None, ah_ref: float | None
    ) -> dict[str, Any]:
        """Compact profile for the AI and the panel."""
        typical = self.typical.get(season, {})
        days = typical["rh_mean"].count if typical else 0
        achievable = self.achievable_rh(temp, rh, ah_ref)
        return {
            "season": season,
            "days": days,
            "typical": {k: round(e.value, 1) for k, e in typical.items()} if days else None,
            "floor_14d": self.floor_rh,
            "achievable_now": None if achievable is None else round(achievable, 1),
            "load_gph": round(self.load.value, 2) if self.load.count else None,
            "airing": {
                "judged": self.exchange.count,
                "share": round(self.exchange.value, 2),
                "rebound": round(self.rebound.value, 2),
                "drop_per_min": round(self.drop_rate.value, 3),
            }
            if self.known_effect
            else None,
            "last_airings": list(self.events),
        }

    # ------------------------------------------------------------------ storage

    def as_dict(self) -> dict[str, Any]:
        return {
            "typical": {
                s: {k: e.as_dict() for k, e in values.items()} for s, values in self.typical.items()
            },
            "floor": self.floor,
            "load": self.load.as_dict(),
            "exchange": self.exchange.as_dict(),
            "rebound": self.rebound.as_dict(),
            "drop_rate": self.drop_rate.as_dict(),
            "events": self.events,
            "day": self.day.as_dict(),
            "hour": self.hour,
            "airing": self.airing,
            "pending": self.pending,
        }

    @classmethod
    def from_dict(cls, data: Any) -> HumidityProfile:
        profile = cls()
        if not isinstance(data, dict):
            return profile
        typical = data.get("typical")
        if isinstance(typical, dict):
            for season in SEASONS:
                stored = typical.get(season)
                if isinstance(stored, dict):
                    for key in TYPICAL_KEYS:
                        profile.typical[season][key] = _ewma(stored.get(key), 0.0, TYPICAL_ALPHA)
        floor = data.get("floor")
        if isinstance(floor, list):
            profile.floor = [
                [str(item[0]), float(item[1])]
                for item in floor
                if isinstance(item, list | tuple) and len(item) == 2 and _num(item[1]) is not None
            ][-FLOOR_DAYS:]
        profile.load = _ewma(data.get("load"), 0.0, EFFECT_ALPHA)
        profile.exchange = _ewma(data.get("exchange"), 0.5, EFFECT_ALPHA)
        profile.rebound = _ewma(data.get("rebound"), 0.2, EFFECT_ALPHA)
        profile.drop_rate = _ewma(data.get("drop_rate"), 0.0, EFFECT_ALPHA)
        events = data.get("events")
        if isinstance(events, list):
            profile.events = [e for e in events if isinstance(e, dict)][-EVENT_COUNT:]
        profile.day = DayStats.from_dict(data.get("day"))
        hour = data.get("hour")
        if isinstance(hour, list) and len(hour) == 2 and all(_num(v) is not None for v in hour):
            profile.hour = [float(hour[0]), float(hour[1])]
        for key, needed in (
            ("airing", ("ts", "ah", "rh", "min_ah", "min_rh")),
            ("pending", ("closed", "drop", "min_ah")),
        ):
            value = data.get(key)
            if isinstance(value, dict) and all(_num(value.get(k)) is not None for k in needed):
                setattr(profile, key, value)
        return profile
