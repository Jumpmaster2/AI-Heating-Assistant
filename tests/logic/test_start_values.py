"""Tests for applying changed start values of the area configuration."""

from logic.controller import ControlParams
from logic.learning import AreaLearner, Ewma
from logic.start_values import (
    VENT_START_NAMES,
    apply_start_values,
    apply_vent_start_values,
    read_record,
    read_vent_record,
)
from logic.ventilation import VentilationSettings

CFG = {"dead_time": 1800.0, "recovery": 1800.0, "window_delay_min": 5.0, "puffer": 0.7}


def _params(**values: float) -> ControlParams:
    return ControlParams(**{"window_delay_min": 5.0, "puffer": 0.7, **values})


def test_new_area_applies_nothing() -> None:
    learner = AreaLearner.create(1800, 1800)
    assert apply_start_values(CFG, {}, learner, _params()) == []


def test_first_start_applies_only_unlearned_values() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.recovery = Ewma(5400.0)  # stored start value, nothing learned
    learner.dead_time.add(2400)  # one sample
    configured = {**CFG, "recovery": 3600.0, "dead_time": 2400.0}
    assert apply_start_values(configured, {}, learner, _params()) == [("recovery", 5400.0, 3600.0)]
    assert learner.recovery == Ewma(3600.0)
    assert learner.dead_time.count == 1


def test_first_start_keeps_adjusted_params_but_replaces_defaults() -> None:
    params = _params(window_delay_min=7.0)  # moved by the AI
    configured = {**CFG, "window_delay_min": 8.0, "puffer": 0.5}
    assert apply_start_values(configured, {}, None, params) == [("puffer", 0.7, 0.5)]
    assert params.window_delay_min == 7.0 and params.puffer == 0.5


def test_changed_configuration_replaces_learned_values() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.dead_time = Ewma(2500.0, count=5)
    params = _params(window_delay_min=7.0)
    configured = {**CFG, "dead_time": 3600.0, "window_delay_min": 10.0}
    applied = apply_start_values(configured, CFG, learner, params)
    assert applied == [("dead_time", 2500.0, 3600.0), ("window_delay_min", 7.0, 10.0)]
    assert learner.dead_time == Ewma(3600.0) and learner.dead_time.count == 0
    assert params.window_delay_min == 10.0 and params.puffer == 0.7
    assert learner.recovery == Ewma(1800.0)


def test_unchanged_configuration_keeps_imported_values() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.dead_time = Ewma(4500.0)  # imported, count 0
    assert apply_start_values(CFG, CFG, learner, _params()) == []
    assert learner.dead_time.value == 4500.0


def test_configuration_equal_to_the_learned_value_keeps_the_samples() -> None:
    learner = AreaLearner.create(1800, 1800)
    learner.dead_time = Ewma(2700.0, count=4)
    configured = {**CFG, "dead_time": 2700.0}
    assert apply_start_values(configured, CFG, learner, _params()) == []
    assert learner.dead_time.count == 4


def test_configured_values_are_clamped_once() -> None:
    learner = AreaLearner.create(1800, 1800)
    configured = {**CFG, "dead_time": 120.0}
    assert apply_start_values(configured, {}, learner, _params()) == [("dead_time", 1800.0, 300.0)]
    assert apply_start_values(configured, {"dead_time": 120.0}, learner, _params()) == []


def test_without_learner_only_params() -> None:
    params = _params()
    configured = {"dead_time": 600.0, "recovery": 600.0, "window_delay_min": 3.0, "puffer": 0.9}
    applied = apply_start_values(configured, CFG, None, params)
    assert applied == [("window_delay_min", 5.0, 3.0), ("puffer", 0.7, 0.9)]


def test_read_record_tolerates_garbage() -> None:
    assert read_record(None) == {}
    assert read_record({"dead_time": "x", "bogus": 1, "puffer": 0.5, "recovery": True}) == {
        "puffer": 0.5
    }


def test_ventilation_start_values() -> None:
    configured = {name: 1.0 for name in VENT_START_NAMES}
    settings = VentilationSettings(rh_threshold=66.0)
    # without a record the stored value (maybe from the AI) stays
    assert apply_vent_start_values({**configured, "rh_threshold": 60.0}, {}, settings) == []
    assert settings.rh_threshold == 66.0
    record = read_vent_record({**configured, "rh_threshold": 60.0, "x": 1, "cooling_margin": True})
    assert "cooling_margin" not in record and "x" not in record
    # unchanged configuration: the value of the AI stays
    assert apply_vent_start_values({**configured, "rh_threshold": 60.0}, record, settings) == []
    # changed configuration replaces it
    applied = apply_vent_start_values({**configured, "rh_threshold": 65.0}, record, settings)
    assert applied == [("rh_threshold", 66.0, 65.0)] and settings.rh_threshold == 65.0


def test_changed_recovery_starts_its_model_again() -> None:
    learner = AreaLearner.create(1800, 1800)
    for _ in range(5):
        learner.recovery_model.update(1.0, 0.2, 40.0)
    learner.recovery = Ewma(2400.0, count=5)
    configured = {**CFG, "recovery": 3600.0}
    assert apply_start_values(configured, CFG, learner, _params()) == [("recovery", 2400.0, 3600.0)]
    assert learner.recovery_model.count == 0
