"""Controller and learner together on a simulated room (floor mass plus air).

The unit tests check single decisions. Some problems only show up in the loop,
e.g. a circuit that comes back right after the minimum off time because the
switch-on prediction ignores the heat still stored in the floor.
"""

import itertools

from logic.controller import (
    AreaRuntime,
    AreaSettings,
    ControlInput,
    ControlParams,
    LearnedValues,
    step,
)
from logic.learning import AreaLearner, Sample

TARGET = 21.0
OUTDOOR = 2.0
DAYS = 3


def _simulate(
    floor_gain: float, coupling: float
) -> tuple[list[tuple[int, bool, float]], AreaLearner, float, float]:
    params, settings, rt = ControlParams(), AreaSettings(), AreaRuntime()
    learner = AreaLearner.create(1800.0, 1800.0)
    t_air, t_floor = 20.6, 21.0
    switch_on, last_change, on_since = False, 0.0, None
    events: list[tuple[int, bool, float]] = []
    lowest, highest = t_air, t_air
    for minute in range(DAYS * 24 * 60):
        ts = minute * 60.0
        run_h = (ts - on_since) / 3600 if (switch_on and on_since is not None) else 0.0
        model = learner.model
        diff = t_air - OUTDOOR
        learned = LearnedValues(
            cool_rate_kph=model.cool_rate(diff),
            heat_rate_kph=model.heat_rate(diff),
            dead_time_s=learner.dead_time.value,
            recovery_s=learner.recovery.value,
            overshoot_k=learner.expected_overshoot(run_h),
        )
        temp = round(t_air, 1)  # sensor resolution
        decision = step(
            ControlInput(ts, temp, TARGET, True, True, True, 7.0, False, switch_on, last_change),
            params,
            settings,
            learned,
            rt,
        )
        # the sample of this tick still sees the old switch state (as in the coordinator)
        learner.add_sample(Sample(ts, temp, switch_on, OUTDOOR, 0.0, False))
        if decision.may_switch and decision.want_on != switch_on:
            learner.on_switch(ts, temp, decision.want_on, run_h)
            switch_on, last_change = decision.want_on, ts
            on_since = ts if switch_on else None
            events.append((minute, switch_on, temp))
        dt = 1 / 60
        t_floor += dt * (floor_gain if switch_on else 0.0) - dt * (t_floor - t_air) * coupling
        t_air += dt * (t_floor - t_air) * coupling - dt * (t_air - OUTDOOR) * 0.015
        lowest, highest = min(lowest, t_air), max(highest, t_air)
    return events, learner, lowest, highest


def _off_to_on_gaps(events: list[tuple[int, bool, float]]) -> list[int]:
    gaps = []
    for (m_off, on_a, _), (m_on, on_b, _) in itertools.pairwise(events):
        if not on_a and on_b:
            gaps.append(m_on - m_off)
    return gaps


def test_slow_floor_no_restart_right_after_switch_off() -> None:
    events, learner, lowest, highest = _simulate(floor_gain=1.2, coupling=0.25)
    gaps = _off_to_on_gaps(events)
    assert len(gaps) >= 5
    # without the carried overshoot the circuit came back after the 10 min minimum off time
    assert min(gaps) >= 60
    # the learners get their samples (the overshoot tracker needs an uninterrupted peak;
    # in this slow room the rise is confirmed only shortly before the switch-off)
    assert learner.overshoot.count >= 3
    assert learner.dead_time.count >= 1
    assert lowest >= TARGET - 1.0 and highest <= TARGET + 1.0


def test_fast_floor_still_keeps_the_target() -> None:
    events, learner, lowest, highest = _simulate(floor_gain=2.0, coupling=0.6)
    assert len(_off_to_on_gaps(events)) >= 5
    assert learner.overshoot.count >= 3
    assert lowest >= TARGET - 1.0 and highest <= TARGET + 1.0
