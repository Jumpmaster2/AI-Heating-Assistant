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
    changed = _feed(learner, 0, 60, lambda m: 20.0 + m * 0.025, valve=False)
    assert "recovery" in changed
    assert learner.recovery.count == 1

    learner.on_window_closed(10_000, temp_before=21.0, open_seconds=600)
    _feed(learner, 10_000, 30, lambda m: 20.0, valve=True)
    assert learner.recovery.count == 1  # censored, no update
    assert learner.track_recovery is None


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
