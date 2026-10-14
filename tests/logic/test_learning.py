"""Tests for the learning of thermal behaviour."""

import random

import pytest
from logic.learning import AreaLearner, Ewma, Sample, ThermalModel


def test_ewma_start_value_counts_once() -> None:
    e = Ewma(1.0)
    e.add(3.0)
    assert e.value == pytest.approx(2.0)
    for _ in range(50):
        e.add(3.0)
    assert e.value == pytest.approx(3.0, abs=0.01)


def test_rls_converges_to_true_parameters() -> None:
    rng = random.Random(1)
    true_a, true_k, true_s = 1.2, 0.02, 0.4
    model = ThermalModel()
    for _ in range(3000):
        valve = rng.choice([0.0, 0.0, 0.5, 1.0])
        diff = rng.uniform(5, 20)
        pv = rng.choice([0.0, 0.0, 0.3, 0.8])
        rate = true_a * valve - true_k * diff + true_s * pv + rng.gauss(0, 0.02)
        model.update(valve, diff, pv, rate)
    assert model.a == pytest.approx(true_a, abs=0.05)
    assert model.k == pytest.approx(true_k, abs=0.005)
    assert model.s == pytest.approx(true_s, abs=0.05)
    assert model.cool_rate(10.0) == pytest.approx(0.2, abs=0.06)


def test_rls_rejects_outliers_and_stays_bounded() -> None:
    model = ThermalModel()
    assert not model.update(1.0, 10.0, 0.0, 50.0)
    for _ in range(500):
        model.update(0.0, 10.0, 0.0, 5.0 - 0.1)  # nonsense warming without heat
    assert 0.0 <= model.k <= 0.3


def test_model_roundtrip() -> None:
    model = ThermalModel()
    model.update(1.0, 10.0, 0.0, 0.6)
    copy = ThermalModel.from_dict(model.as_dict())
    assert copy.theta == model.theta and copy.n_heat == 1


def _feed(
    learner: AreaLearner,
    start: float,
    minutes: int,
    temp_fn,
    valve: bool,
    outdoor=5.0,
    pv=0.0,
    excluded=False,
):
    changed = []
    for m in range(minutes):
        ts = start + m * 60
        changed += learner.add_sample(Sample(ts, temp_fn(m), valve, outdoor, pv, excluded))
    return changed


def test_dead_time_learned() -> None:
    learner = AreaLearner.create(dead_time_s=1800, recovery_s=1800)
    learner.on_switch(0, 20.0, turned_on=True, run_hours=0)
    # flat for 50 min, then rising
    changed = _feed(
        learner, 0, 90, lambda m: 20.0 if m < 50 else 20.0 + (m - 50) * 0.01, valve=True
    )
    assert "dead_time" in changed
    assert learner.dead_time.count == 1
    assert 1800 < learner.dead_time.value < 3600


def test_dead_time_ignores_single_sensor_step() -> None:
    learner = AreaLearner.create(dead_time_s=1800, recovery_s=1800)
    learner.on_switch(0, 20.0, turned_on=True, run_hours=0)

    # one sensor step that falls back at once: noise, no sample
    changed = _feed(learner, 0, 40, lambda m: 20.1 if m == 2 else 20.0, valve=True)
    assert "dead_time" not in changed
    assert learner.track_on is not None and "rise" not in learner.track_on

    # the rise starts at minute 45 (first step) and is confirmed at minute 50
    def temp(m: int) -> float:
        return 20.0 if m < 5 else 20.1 if m < 10 else 20.2

    changed = _feed(learner, 40 * 60, 30, temp, valve=True)
    assert "dead_time" in changed
    assert learner.dead_time.count == 1
    # the dead time is the first step: 2700 s, averaged with the start value 1800 s
    assert learner.dead_time.value == pytest.approx(2250)


def test_dead_time_single_step_counts_once_it_lasts() -> None:
    learner = AreaLearner.create(dead_time_s=1800, recovery_s=1800)
    learner.on_switch(0, 20.0, turned_on=True, run_hours=0)
    changed = _feed(learner, 0, 50, lambda m: 20.0 if m < 30 else 20.1, valve=True)
    assert "dead_time" in changed
    assert learner.dead_time.value == pytest.approx(1800 + 0.5 * (30 * 60 - 1800))


def test_dead_time_and_overshoot_finished_at_switch_events() -> None:
    learner = AreaLearner.create(dead_time_s=1800, recovery_s=1800)
    learner.on_switch(0, 20.0, turned_on=True, run_hours=0)
    # rise of one step for 3 minutes (not confirmed yet), then the circuit switches off
    # 6 minutes after the step: the switch-off confirms it
    _feed(learner, 0, 34, lambda m: 20.0 if m < 30 else 20.1, valve=True)
    assert learner.dead_time.count == 0
    learner.on_switch(36 * 60, 20.1, turned_on=False, run_hours=0.6)
    assert learner.dead_time.count == 1
    # peak 20.5 passed by 0.15 K exactly when the controller switches on again
    _feed(learner, 36 * 60, 60, lambda m: 20.1 + min(m, 30) * 0.4 / 30, valve=False)
    learner.on_switch(96 * 60, 20.35, turned_on=True, run_hours=0)
    assert learner.overshoot.count == 1
    assert learner.track_off is None and learner.track_on is not None


def test_overshoot_learned() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.on_switch(0, 21.0, turned_on=False, run_hours=2.0)
    # rises 0.4 K within 60 min, then falls
    temp = lambda m: 21.0 + min(m, 60) * 0.4 / 60 - max(0, m - 60) * 0.01  # noqa: E731
    changed = _feed(learner, 0, 120, temp, valve=False)
    assert "overshoot" in changed
    assert learner.overshoot.count == 1
    assert learner.overshoot_rate.value != pytest.approx(0.3)
    assert learner.expected_overshoot(2.0) > 0


def test_recovery_learned_and_censored_by_heating() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.on_window_closed(0, temp_before=21.0, open_seconds=600)
    # measured while the controller still waits (samples excluded from the rest)
    changed = _feed(learner, 0, 60, lambda m: 20.0 + m * 0.025, valve=False, excluded=True)
    assert "recovery" in changed
    assert learner.recovery.count == 1
    assert learner.recovery.value == pytest.approx(1980)  # recovered after 36 min

    # heating starts before the wait is over: says nothing, no update
    learner.on_window_closed(10_000, temp_before=21.0, open_seconds=600)
    _feed(learner, 10_000, 5, lambda m: 20.0, valve=False, excluded=True)
    _feed(learner, 10_300, 1, lambda m: 20.0, valve=True)
    assert learner.recovery.count == 1
    assert learner.track_recovery is None

    # wait over, the room was not warming up: it would not have recovered, no update
    learner.on_window_closed(20_000, temp_before=21.0, open_seconds=600)
    _feed(learner, 20_000, 34, lambda m: 20.0, valve=False, excluded=True)
    _feed(learner, 20_000 + 34 * 60, 1, lambda m: 20.0, valve=True)
    assert learner.recovery.count == 1

    # wait over, the room was warming up by itself: the true value is larger
    learner.on_window_closed(30_000, temp_before=21.0, open_seconds=600)
    _feed(learner, 30_000, 34, lambda m: 20.0 if m < 10 else 20.1, valve=False, excluded=True)
    _feed(learner, 30_000 + 34 * 60, 1, lambda m: 20.1, valve=True)
    assert learner.recovery.count == 2
    assert learner.recovery.value == pytest.approx(1980 + (1980 * 1.25 - 1980) / 3)
    assert learner.track_recovery is None


def test_recovery_censored_uses_the_controller_wait() -> None:
    learner = AreaLearner.create(1800, 1800)
    # the controller waits only 10 min (negative bias): "longer than 10 min" says nothing
    learner.on_window_closed(0, temp_before=21.0, open_seconds=600, wait_s=600)
    _feed(learner, 0, 11, lambda m: 20.0 if m < 3 else 20.1, valve=False, excluded=True)
    _feed(learner, 11 * 60, 1, lambda m: 20.1, valve=True)
    assert learner.recovery.count == 0
    # the controller waits 50 min and the room was warming up: the estimate grows
    learner.on_window_closed(10_000, temp_before=21.0, open_seconds=600, wait_s=3000)
    _feed(learner, 10_000, 51, lambda m: 20.0 if m < 3 else 20.1, valve=False, excluded=True)
    _feed(learner, 10_000 + 51 * 60, 1, lambda m: 20.1, valve=True)
    assert learner.recovery.count == 1
    assert learner.recovery.value == pytest.approx(1800 + 0.5 * (3000 * 1.25 - 1800))


def test_recovery_timeout_keeps_the_value() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.on_window_closed(0, temp_before=21.0, open_seconds=600)
    _feed(learner, 0, 4 * 60 + 2, lambda m: 20.0, valve=False, excluded=True)
    assert learner.recovery.count == 0 and learner.track_recovery is None


def test_dead_time_ignores_single_dip_below_the_plateau() -> None:
    learner = AreaLearner.create(dead_time_s=1800, recovery_s=1800)
    learner.on_switch(0, 20.0, turned_on=True, run_hours=0)
    # one reading below the plateau must not turn the plateau into a rise
    changed = _feed(learner, 0, 40, lambda m: 19.9 if m == 5 else 20.0, valve=True)
    assert "dead_time" not in changed
    assert learner.track_on is not None and learner.track_on["min"] == 20.0
    # two readings below confirm a lower level; the later rise counts from there
    temp = lambda m: 19.9 if m < 10 else 20.0 if m < 15 else 20.1  # noqa: E731
    changed = _feed(learner, 40 * 60, 30, temp, valve=True)
    assert "dead_time" in changed
    assert learner.dead_time.value == pytest.approx(1800 + 0.5 * (50 * 60 - 1800))


def test_dead_time_sensor_step_at_float_boundary() -> None:
    learner = AreaLearner.create(dead_time_s=1800, recovery_s=1800)
    learner.on_switch(0, 20.1, turned_on=True, run_hours=0)  # 20.1 + 0.1 > 20.2 as floats
    changed = _feed(learner, 0, 40, lambda m: 20.1 if m < 30 else 20.2, valve=True)
    assert "dead_time" in changed
    assert learner.dead_time.value == pytest.approx(1800)  # step at 30 min = start value


def test_pv_unknown_keeps_event_trackers_running_but_not_the_model() -> None:
    def run(pv_unknown: bool) -> list[str]:
        learner = AreaLearner.create(dead_time_s=1800, recovery_s=1800)
        learner.on_switch(0, 20.0, turned_on=True, run_hours=0)
        changed: list[str] = []
        for m in range(180):
            temp = 20.0 if m < 30 else 20.2
            sample = Sample(m * 60, temp, True, 5.0, 0.3, False, pv_unknown=pv_unknown)
            changed += learner.add_sample(sample)
        return changed

    assert "model" in run(pv_unknown=False)
    unknown = run(pv_unknown=True)
    assert "dead_time" in unknown and "model" not in unknown


def test_stale_overshoot_tracker_is_not_counted_at_switch_on() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.on_switch(0, 20.4, turned_on=False, run_hours=1.0)
    _feed(learner, 0, 10, lambda m: 20.4, valve=False, excluded=True)  # nothing seen for hours
    learner.on_switch(8 * 3600, 20.2, turned_on=True, run_hours=0)
    assert learner.overshoot.count == 0


def test_overshoot_rate_comes_down_from_short_runs() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.overshoot_rate = Ewma(2.0, count=10)
    learner.on_switch(0, 20.6, turned_on=False, run_hours=10 / 60)
    temp = lambda m: 20.6 if m < 5 else 20.7 if m < 20 else 20.4  # noqa: E731
    _feed(learner, 0, 60, temp, valve=False)
    assert learner.overshoot.count == 1
    assert learner.overshoot_rate.value < 2.0


def test_model_updated_from_samples() -> None:
    learner = AreaLearner.create(600, 1800)
    # three hours of steady cooling 0.1 K/h with outdoor 5 °C
    changed = _feed(learner, 0, 180, lambda m: 21.0 - m / 600, valve=False)
    assert "model" in changed
    assert learner.model.n_cool >= 1


def test_excluded_samples_do_not_update_model() -> None:
    learner = AreaLearner.create(600, 1800)
    changed = _feed(learner, 0, 180, lambda m: 21.0 - m / 600, valve=False, excluded=True)
    assert "model" not in changed


def test_confidence_and_roundtrip() -> None:
    learner = AreaLearner.create(1800, 1800)
    assert learner.confidence() == 0
    learner.dead_time.add(2000)
    copy = AreaLearner.from_dict(learner.as_dict(), 1800, 1800)
    assert copy.dead_time.count == 1
    assert copy.confidence() > 0
