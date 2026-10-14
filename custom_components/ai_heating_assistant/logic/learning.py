"""Online learning of the thermal behaviour of one heating area.

Two kinds of learners are combined:

* ``ThermalModel``: recursive least squares (RLS) estimate of
  ``dT/dt [K/h] = a * valve - k * (T_room - T_out) + s * pv_kw``.
  ``a`` is the heating effect of the open circuit, ``k`` the heat loss
  coefficient (influence of the outdoor temperature) and ``s`` the solar gain
  per kW of PV power (used as a sunshine indicator).
* Event learners (exponentially weighted means) for the dead time after
  switching on, the overshoot after switching off and the recovery time after
  airing.

All values are plain floats so the state can be stored as JSON.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .physics import clamp

# Bounds keep a learner from drifting into nonsense if a sensor misbehaves.
MODEL_BOUNDS = ((0.02, 5.0), (0.0, 0.3), (0.0, 3.0))  # a [K/h], k [1/h], s [K/h per kW]
MODEL_START = (0.5, 0.005, 0.1)
P_START = (1.0, 0.0004, 0.25)  # initial variance of a, k, s (also the anti windup cap)
MAX_RATE_ERROR = 3.0  # K/h, larger residuals are treated as outliers

OVERSHOOT_BOUNDS = (0.0, 2.0)  # K
OVERSHOOT_RATE_BOUNDS = (0.0, 2.0)  # K per hour of heating
DEAD_TIME_BOUNDS = (300.0, 4 * 3600.0)  # s
RECOVERY_BOUNDS = (0.0, 4 * 3600.0)  # s

SAMPLE_INTERVAL = 15 * 60  # s between model updates
RATE_WINDOW = 60 * 60  # s window used to compute dT/dt
EDGE = 5 * 60  # s averaged at both ends of the window (sensor quantisation)
MAX_RUN_HOURS_FOR_OVERSHOOT = 3.0
TRACK_TIMEOUT = 4 * 3600.0


@dataclass(slots=True)
class Ewma:
    """Exponentially weighted mean that treats the start value as one observation."""

    value: float
    count: int = 0
    alpha_min: float = 0.2

    def add(self, sample: float) -> None:
        """Add a new observation."""
        alpha = max(self.alpha_min, 1.0 / (self.count + 2))
        self.value += alpha * (sample - self.value)
        self.count += 1

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "count": self.count}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, default: float) -> Ewma:
        if not data:
            return cls(default)
        return cls(float(data.get("value", default)), int(data.get("count", 0)))


@dataclass(slots=True)
class ThermalModel:
    """RLS estimate of the room temperature dynamics."""

    theta: list[float] = field(default_factory=lambda: list(MODEL_START))
    p: list[list[float]] = field(
        default_factory=lambda: [
            [P_START[i] if i == j else 0.0 for j in range(3)] for i in range(3)
        ]
    )
    n_heat: int = 0
    n_cool: int = 0
    forgetting: float = 0.998

    @property
    def a(self) -> float:
        return self.theta[0]

    @property
    def k(self) -> float:
        return self.theta[1]

    @property
    def s(self) -> float:
        return self.theta[2]

    def predict(
        self, valve: float, temp_diff: float, pv_kw: float, sun_factor: float = 1.0
    ) -> float:
        """Return the expected temperature change in K/h."""
        return self.a * valve - self.k * temp_diff + self.s * pv_kw * sun_factor

    def heat_rate(self, temp_diff: float, pv_kw: float = 0.0, sun_factor: float = 1.0) -> float:
        """Expected rise in K/h while heating."""
        return self.predict(1.0, temp_diff, pv_kw, sun_factor)

    def cool_rate(self, temp_diff: float, pv_kw: float = 0.0, sun_factor: float = 1.0) -> float:
        """Expected drop in K/h without heating (negative = the room warms up)."""
        return -self.predict(0.0, temp_diff, pv_kw, sun_factor)

    def update(self, valve: float, temp_diff: float, pv_kw: float, rate: float) -> bool:
        """Update with one observation. Returns False if it was rejected as outlier."""
        phi = (valve, -temp_diff, pv_kw)
        error = rate - sum(t * x for t, x in zip(self.theta, phi, strict=True))
        if abs(error) > MAX_RATE_ERROR:
            return False
        lam = self.forgetting
        p_phi = [sum(self.p[i][j] * phi[j] for j in range(3)) for i in range(3)]
        denom = lam + sum(phi[i] * p_phi[i] for i in range(3))
        gain = [v / denom for v in p_phi]
        for i in range(3):
            self.theta[i] += gain[i] * error
        self.p = [[(self.p[i][j] - gain[i] * p_phi[j]) / lam for j in range(3)] for i in range(3)]
        # Anti windup: directions without excitation must not explode.
        for i in range(3):
            if self.p[i][i] > P_START[i]:
                factor = (P_START[i] / self.p[i][i]) ** 0.5
                for j in range(3):
                    self.p[i][j] *= factor
                    self.p[j][i] *= factor
        for i, (low, high) in enumerate(MODEL_BOUNDS):
            self.theta[i] = clamp(self.theta[i], low, high)
        if valve > 0.2:
            self.n_heat += 1
        else:
            self.n_cool += 1
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "theta": list(self.theta),
            "p": [list(r) for r in self.p],
            "n_heat": self.n_heat,
            "n_cool": self.n_cool,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ThermalModel:
        model = cls()
        if not data:
            return model
        theta = data.get("theta")
        if isinstance(theta, list) and len(theta) == 3:
            model.theta = [clamp(float(v), *MODEL_BOUNDS[i]) for i, v in enumerate(theta)]
        p = data.get("p")
        if (
            isinstance(p, list)
            and len(p) == 3
            and all(isinstance(r, list) and len(r) == 3 for r in p)
        ):
            model.p = [[float(v) for v in row] for row in p]
        model.n_heat = int(data.get("n_heat", 0))
        model.n_cool = int(data.get("n_cool", 0))
        return model


@dataclass(slots=True)
class Sample:
    """One controller tick."""

    ts: float
    temp: float | None
    valve: bool
    outdoor: float | None
    pv_kw: float
    excluded: bool  # window open, recovery or other disturbance


@dataclass
class AreaLearner:
    """All learned values of one area plus the trackers that produce them."""

    model: ThermalModel = field(default_factory=ThermalModel)
    overshoot: Ewma = field(default_factory=lambda: Ewma(0.3))
    overshoot_rate: Ewma = field(default_factory=lambda: Ewma(0.3))
    dead_time: Ewma = field(default_factory=lambda: Ewma(1800.0))
    recovery: Ewma = field(default_factory=lambda: Ewma(1800.0))
    samples: deque[Sample] = field(default_factory=lambda: deque(maxlen=6 * 60 + 10))
    last_model_update: float | None = None
    # running trackers
    track_off: dict[str, float] | None = None
    track_on: dict[str, float] | None = None
    track_recovery: dict[str, float] | None = None

    # ---------- construction / persistence ----------

    @classmethod
    def create(cls, dead_time_s: float, recovery_s: float) -> AreaLearner:
        learner = cls()
        learner.dead_time = Ewma(clamp(dead_time_s, *DEAD_TIME_BOUNDS))
        learner.recovery = Ewma(clamp(recovery_s, *RECOVERY_BOUNDS))
        return learner

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model.as_dict(),
            "overshoot": self.overshoot.as_dict(),
            "overshoot_rate": self.overshoot_rate.as_dict(),
            "dead_time": self.dead_time.as_dict(),
            "recovery": self.recovery.as_dict(),
            "track_off": self.track_off,
            "track_on": self.track_on,
            "track_recovery": self.track_recovery,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any] | None, dead_time_s: float, recovery_s: float
    ) -> AreaLearner:
        if not data:
            return cls.create(dead_time_s, recovery_s)
        learner = cls()
        learner.model = ThermalModel.from_dict(data.get("model"))
        learner.overshoot = Ewma.from_dict(data.get("overshoot"), 0.3)
        learner.overshoot_rate = Ewma.from_dict(data.get("overshoot_rate"), 0.3)
        learner.dead_time = Ewma.from_dict(data.get("dead_time"), dead_time_s)
        learner.recovery = Ewma.from_dict(data.get("recovery"), recovery_s)
        learner.track_off = data.get("track_off")
        learner.track_on = data.get("track_on")
        learner.track_recovery = data.get("track_recovery")
        return learner

    # ---------- derived values ----------

    def expected_overshoot(self, run_hours: float, factor: float = 1.0) -> float:
        """Overshoot expected if the circuit is switched off now."""
        hours = clamp(run_hours, 0.0, MAX_RUN_HOURS_FOR_OVERSHOOT)
        return max(0.0, self.overshoot_rate.value * hours * factor)

    def confidence(self) -> float:
        """Learning progress 0..100 %."""
        score = (
            0.35 * min(1.0, self.model.n_heat / 48)
            + 0.25 * min(1.0, self.model.n_cool / 96)
            + 0.15 * min(1.0, self.overshoot.count / 5)
            + 0.15 * min(1.0, self.dead_time.count / 5)
            + 0.10 * min(1.0, self.recovery.count / 5)
        )
        return round(100.0 * score, 1)

    # ---------- events ----------

    def on_switch(self, ts: float, temp: float | None, turned_on: bool, run_hours: float) -> None:
        """Call when the circuit was switched on or off."""
        if temp is None:
            self.track_on = self.track_off = None
            return
        if turned_on:
            self.track_on = {"start": ts, "min": temp}
            self.track_off = None
        else:
            self.track_off = {"start": ts, "t_off": temp, "max": temp, "run_h": run_hours}
            self.track_on = None

    def on_window_closed(self, ts: float, temp_before: float | None, open_seconds: float) -> None:
        """Start measuring the recovery after airing."""
        if temp_before is None or open_seconds < 120:
            self.track_recovery = None
            return
        self.track_recovery = {"start": ts, "t_before": temp_before}

    def on_window_opened(self) -> None:
        """Opening a window disturbs all running measurements."""
        self.track_on = None
        self.track_off = None
        self.track_recovery = None

    # ---------- periodic ----------

    def add_sample(self, sample: Sample) -> list[str]:
        """Feed one tick. Returns names of values that changed."""
        changed: list[str] = []
        self.samples.append(sample)
        if sample.temp is not None and not sample.excluded:
            changed += self._track(sample)
        if self.last_model_update is None or sample.ts - self.last_model_update >= SAMPLE_INTERVAL:
            if self._update_model(sample.ts):
                changed.append("model")
            self.last_model_update = sample.ts
        return changed

    def _track(self, s: Sample) -> list[str]:
        changed: list[str] = []
        temp = s.temp
        assert temp is not None
        if self.track_on is not None:
            t = self.track_on
            if not s.valve or s.ts - t["start"] > TRACK_TIMEOUT:
                self.track_on = None
            else:
                t["min"] = min(t["min"], temp)
                if temp >= t["min"] + 0.1:
                    self.dead_time.add(clamp(s.ts - t["start"], *DEAD_TIME_BOUNDS))
                    self.track_on = None
                    changed.append("dead_time")
        if self.track_off is not None:
            t = self.track_off
            peak_passed = temp <= t["max"] - 0.15
            if s.valve and not peak_passed:
                self.track_off = None
            elif peak_passed or s.ts - t["start"] > TRACK_TIMEOUT:
                over = clamp(t["max"] - t["t_off"], *OVERSHOOT_BOUNDS)
                self.overshoot.add(over)
                run_h = t.get("run_h", 0.0)
                if run_h >= 0.25:
                    rate = over / min(run_h, MAX_RUN_HOURS_FOR_OVERSHOOT)
                    self.overshoot_rate.add(clamp(rate, *OVERSHOOT_RATE_BOUNDS))
                self.track_off = None
                changed.append("overshoot")
            else:
                t["max"] = max(t["max"], temp)
        if self.track_recovery is not None:
            t = self.track_recovery
            if s.valve or s.ts - t["start"] > TRACK_TIMEOUT:
                self.track_recovery = None  # censored, keep the old value
            elif temp >= t["t_before"] - 0.1:
                self.recovery.add(clamp(s.ts - t["start"], *RECOVERY_BOUNDS))
                self.track_recovery = None
                changed.append("recovery")
        return changed

    def _update_model(self, now: float) -> bool:
        """Estimate dT/dt over the last hour and update the RLS model."""
        start = now - RATE_WINDOW
        window = [s for s in self.samples if s.ts >= start - 1]
        if len(window) < 20 or window[0].ts > start + EDGE:
            return False
        if any(s.excluded or s.temp is None or s.outdoor is None for s in window):
            return False
        head = [s.temp for s in window if s.ts <= window[0].ts + EDGE]
        tail = [s.temp for s in window if s.ts >= now - EDGE]
        if not head or not tail:
            return False
        hours = (now - window[0].ts - EDGE) / 3600.0
        if hours <= 0.3:
            return False
        rate = (sum(tail) / len(tail) - sum(head) / len(head)) / hours  # type: ignore[arg-type]
        mean_temp = sum(s.temp for s in window) / len(window)  # type: ignore[misc]
        mean_out = sum(s.outdoor for s in window) / len(window)  # type: ignore[misc]
        pv = sum(s.pv_kw for s in window) / len(window)
        # Valve fraction shifted by the learned dead time.
        dead = self.dead_time.value
        shifted = [s for s in self.samples if start - dead <= s.ts <= now - dead]
        if not shifted:
            return False
        valve = sum(1.0 for s in shifted if s.valve) / len(shifted)
        return self.model.update(valve, mean_temp - mean_out, pv, rate)
