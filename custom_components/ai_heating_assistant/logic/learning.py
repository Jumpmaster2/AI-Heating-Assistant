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
RISE_K = 0.1  # K above the minimum: a rise may have started (one sensor step)
RISE_CONFIRM_K = 0.2  # K above the minimum: the rise is real, not sensor noise
RISE_CONFIRM_S = 5 * 60  # s a single step has to last to count as a real rise
PEAK_PASSED_K = 0.15  # K below the highest temperature after switch-off: overshoot is over
MIN_RUN_H = 0.25  # h; shorter runs are rated as if they had lasted this long
# A recovery cut short by heating while the room was still warming up only says the
# true value is larger than the time waited. Counting it a little longer lets the
# estimate grow in that direction at all; a room that was not warming up says nothing.
CENSORED_RECOVERY_FACTOR = 1.25
EPS = 1e-6  # tolerance for comparing sensor values in 0.1 K steps (20.1 + 0.1 > 20.2)
RECOVERY_MIN_S = 120.0  # a room "recovered" sooner never showed the airing: no sample

SAMPLE_INTERVAL = 15 * 60  # s between model updates
RATE_WINDOW = 60 * 60  # s window used to compute dT/dt
EDGE = 5 * 60  # s averaged at both ends of the window (sensor quantisation)
MAX_RUN_HOURS_FOR_OVERSHOOT = 3.0
TRACK_TIMEOUT = 4 * 3600.0


def _follow_rise(t: dict[str, float], temp: float, ts: float) -> bool:
    """Track a minimum and the first step above it in ``t``; True once the rise is real.

    The minimum only falls when a second reading confirms the lower level (one reading
    below the plateau may be noise); the rise counts from the first reading one step
    above the minimum and is real with a second step or once it lasted a while.
    """
    if "min" not in t:
        t["min"] = temp
    if temp < t["min"] - EPS:
        dip = t.get("dip")
        if dip is None:
            t["dip"] = temp
        else:
            t["min"] = max(dip, temp)
            t.pop("dip", None)
            t.pop("rise", None)
        return False
    t.pop("dip", None)
    if temp - t["min"] >= RISE_K - EPS:
        t.setdefault("rise", ts)
    else:
        t.pop("rise", None)
    return _rise_confirmed(t, temp, ts)


def _rise_confirmed(t: dict[str, float], temp: float | None, ts: float) -> bool:
    """A second sensor step above the minimum, or the first step lasting a while."""
    rise = t.get("rise")
    if temp is not None and temp - t["min"] >= RISE_CONFIRM_K - EPS:
        return True
    return rise is not None and ts - rise >= RISE_CONFIRM_S


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
    # Per update (every 15 min): about three weeks of memory. Heat loss and solar gain
    # need weeks of different weather to separate, a few days are not enough.
    forgetting: float = 0.9995

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
    pv_unknown: bool = False  # pv_kw is an estimate: keep the sample out of the model


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
            # The controller switches on once the peak has passed: that is a valid sample.
            t = self.track_off
            if (
                t is not None
                and ts - t["start"] <= TRACK_TIMEOUT
                and temp <= t["max"] - PEAK_PASSED_K + EPS
            ):
                self._add_overshoot(t)
            self.track_on = {"start": ts, "min": temp}
            self.track_off = None
        else:
            if self.track_on is not None:
                self._confirm_dead_time(self.track_on, ts, temp)
            self.track_off = {"start": ts, "t_off": temp, "max": temp, "run_h": run_hours}
            self.track_on = None

    def on_window_closed(
        self,
        ts: float,
        temp_before: float | None,
        open_seconds: float,
        wait_s: float | None = None,
    ) -> None:
        """Start measuring the recovery after airing.

        ``wait_s`` is how long the controller will hold the circuit off; without it
        the learned value is assumed.
        """
        if temp_before is None or open_seconds < 120:
            self.track_recovery = None
            return
        wait = self.recovery.value if wait_s is None else max(0.0, wait_s)
        self.track_recovery = {"start": ts, "t_before": temp_before, "wait": wait}

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
        if sample.temp is not None:
            # The recovery is measured while the controller still waits for it; those
            # samples are excluded from everything else. An estimated PV power only
            # keeps the sample out of the model, the event trackers do not need it.
            changed += self._track_recovery(sample)
            if not sample.excluded:
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
            elif _follow_rise(t, temp, s.ts) and self._confirm_dead_time(t, s.ts, temp):
                self.track_on = None
                changed.append("dead_time")
        if self.track_off is not None:
            t = self.track_off
            peak_passed = temp <= t["max"] - PEAK_PASSED_K + EPS
            if s.valve and not peak_passed:
                self.track_off = None
            elif peak_passed:
                self._add_overshoot(t)
                self.track_off = None
                changed.append("overshoot")
            elif s.ts - t["start"] > TRACK_TIMEOUT:
                self.track_off = None  # never fell again (sun, people): not a heating peak
            else:
                t["max"] = max(t["max"], temp)
        return changed

    def _confirm_dead_time(self, t: dict[str, float], ts: float, temp: float | None = None) -> bool:
        """Add the dead time once the rise is real (see ``_rise_confirmed``). The dead
        time ends at the first step."""
        if not _rise_confirmed(t, temp, ts):
            return False
        rise = t.get("rise")
        self.dead_time.add(clamp((ts if rise is None else rise) - t["start"], *DEAD_TIME_BOUNDS))
        return True

    def _add_overshoot(self, t: dict[str, float]) -> None:
        over = clamp(t["max"] - t["t_off"], *OVERSHOOT_BOUNDS)
        self.overshoot.add(over)
        # Short runs are rated as if they had lasted MIN_RUN_H: a rate learned too large
        # shortens every run, and the rate must still be able to come down.
        run_h = clamp(t.get("run_h", 0.0), MIN_RUN_H, MAX_RUN_HOURS_FOR_OVERSHOOT)
        self.overshoot_rate.add(clamp(over / run_h, *OVERSHOOT_RATE_BOUNDS))

    def _track_recovery(self, s: Sample) -> list[str]:
        if self.track_recovery is None or s.temp is None:
            return []
        t = self.track_recovery
        elapsed = s.ts - t["start"]
        rising = _follow_rise(t, s.temp, s.ts)
        if s.temp - t["t_before"] >= -0.1 - EPS:
            self.track_recovery = None
            if elapsed < RECOVERY_MIN_S:
                return []  # the sensor never showed the airing: nothing was measured
            self.recovery.add(clamp(elapsed, *RECOVERY_BOUNDS))
            return ["recovery"]
        if elapsed > TRACK_TIMEOUT:
            self.track_recovery = None  # the room never got back on its own: keep the value
            return []
        wait = t.get("wait", self.recovery.value)
        if "rising" not in t and elapsed >= wait:
            # End of the controller's wait: was the room on its way back by itself?
            t["rising"] = float(rising)
        if s.valve:
            # Censored by heating. Only a room that was still warming up when the wait
            # ended says the true value is larger; everything else says nothing. A wait
            # longer than the estimate (positive bias) must not be learned into it.
            self.track_recovery = None
            base = min(wait, self.recovery.value)
            censored = clamp(base * CENSORED_RECOVERY_FACTOR, *RECOVERY_BOUNDS)
            if not t.get("rising") or censored <= self.recovery.value:
                return []  # "larger than a short wait" says nothing about a larger estimate
            self.recovery.add(censored)
            return ["recovery"]
        return []

    def _update_model(self, now: float) -> bool:
        """Estimate dT/dt over the last hour and update the RLS model."""
        start = now - RATE_WINDOW
        window = [s for s in self.samples if s.ts >= start - 1]
        if len(window) < 20 or window[0].ts > start + EDGE:
            return False
        if any(s.excluded or s.pv_unknown or s.temp is None or s.outdoor is None for s in window):
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
