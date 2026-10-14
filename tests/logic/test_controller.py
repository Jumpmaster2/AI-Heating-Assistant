"""Tests for the per area controller."""

from logic.controller import (
    AreaRuntime,
    AreaSettings,
    AreaStatus,
    ControlInput,
    ControlParams,
    LearnedValues,
    preheat_start,
    step,
    thermostat,
)

PARAMS = ControlParams()
SETTINGS = AreaSettings()
LEARNED = LearnedValues(cool_rate_kph=0.2, dead_time_s=3600, overshoot_k=0.4, recovery_s=1800)


def _input(**kwargs) -> ControlInput:
    base = {
        "now": 100_000.0,
        "temp": 21.0,
        "target": 21.0,
        "hvac_on": True,
        "season_active": True,
        "heating_day": True,
        "frost_temp": 7.0,
        "window_open": False,
        "switch_on": False,
        "last_switch_change": 0.0,
    }
    base.update(kwargs)
    return ControlInput(**base)


def test_predictive_switch_on() -> None:
    # 20.95 now, cooling 0.2 K/h for 1 h -> 20.75 < 20.8 -> on
    want, predicted, _ = thermostat(_input(temp=20.95), PARAMS, LEARNED)
    assert want
    assert predicted == 20.75


def test_no_switch_on_when_prediction_fine() -> None:
    want, _, _ = thermostat(_input(temp=21.1), PARAMS, LEARNED)
    assert not want


def test_sun_warming_delays_switch_on() -> None:
    sunny = LearnedValues(cool_rate_kph=-0.3, dead_time_s=3600)
    want, predicted, _ = thermostat(_input(temp=20.85), PARAMS, sunny)
    assert not want
    assert predicted > 20.85


def test_predictive_switch_off_uses_overshoot() -> None:
    # On, 20.7 + 0.4 overshoot = 21.1 >= 21.0 -> off
    want, _, peak = thermostat(_input(temp=20.7, switch_on=True), PARAMS, LEARNED)
    assert not want
    assert peak == 21.1
    want, _, _ = thermostat(_input(temp=20.5, switch_on=True), PARAMS, LEARNED)
    assert want


def test_overshoot_carried_after_switch_off() -> None:
    """After an overshoot based switch-off the circuit must not come back at once."""
    rt = AreaRuntime()
    on = LearnedValues(cool_rate_kph=0.1, dead_time_s=1800, overshoot_k=0.6)
    # on: 20.4 + 0.6 reaches the target -> off
    d = step(_input(temp=20.4, switch_on=True, last_switch_change=0.0), PARAMS, SETTINGS, on, rt)
    assert not d.want_on
    # off, minimum off time over: 20.4 - 0.05 < 20.8 would switch on again without the carry
    off = LearnedValues(cool_rate_kph=0.1, dead_time_s=1800, overshoot_k=0.0)
    later = {"switch_on": False, "last_switch_change": 100_000.0}
    d = step(_input(now=100_601.0, temp=20.4, **later), PARAMS, SETTINGS, off, rt)
    assert rt.carry_peak == 21.0
    assert not d.want_on and d.predicted_temp == 20.95
    # the room rises and falls again: the overshoot has arrived, normal logic resumes
    step(_input(now=101_800.0, temp=20.9, **later), PARAMS, SETTINGS, off, rt)
    assert rt.carry_peak == 21.0
    d = step(_input(now=103_600.0, temp=20.7, **later), PARAMS, SETTINGS, off, rt)
    assert rt.carry_peak is None and d.want_on


def test_carried_overshoot_expires() -> None:
    rt = AreaRuntime()
    on = LearnedValues(cool_rate_kph=0.1, dead_time_s=1800, overshoot_k=0.6)
    step(_input(temp=20.4, switch_on=True, last_switch_change=0.0), PARAMS, SETTINGS, on, rt)
    off = LearnedValues(cool_rate_kph=0.1, dead_time_s=1800, overshoot_k=0.0)
    later = {"switch_on": False, "last_switch_change": 100_000.0}
    d = step(_input(now=100_601.0, temp=20.4, **later), PARAMS, SETTINGS, off, rt)
    assert not d.want_on
    d = step(_input(now=100_601.0 + 4 * 3600, temp=20.4, **later), PARAMS, SETTINGS, off, rt)
    assert rt.carry_peak is None and d.want_on
    # switched on again: nothing is carried any more
    step(_input(now=100_601.0 + 4 * 3600 + 60, temp=20.4, switch_on=True), PARAMS, SETTINGS, on, rt)
    assert rt.was_on and rt.carry_peak is None


def test_far_below_target_always_on() -> None:
    want, _, _ = thermostat(
        _input(temp=19.5, switch_on=True), PARAMS, LearnedValues(overshoot_k=3.0)
    )
    assert want


def test_min_times_respected() -> None:
    settings = AreaSettings(min_on_s=600, min_off_s=900)
    d = step(
        _input(temp=20.0, switch_on=False, last_switch_change=100_000 - 300),
        PARAMS,
        settings,
        LEARNED,
        AreaRuntime(),
    )
    assert d.want_on and not d.may_switch
    d = step(
        _input(temp=20.0, switch_on=False, last_switch_change=100_000 - 1000),
        PARAMS,
        settings,
        LEARNED,
        AreaRuntime(),
    )
    assert d.may_switch


def test_window_pause_and_recovery() -> None:
    rt = AreaRuntime()
    t0 = 100_000.0
    d = step(_input(now=t0, temp=21.0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status != AreaStatus.WINDOW_OPEN  # delay not over yet
    d = step(_input(now=t0 + 6 * 60, temp=20.0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status == AreaStatus.WINDOW_OPEN and not d.want_on
    d = step(_input(now=t0 + 20 * 60, temp=19.8, window_open=False), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status == AreaStatus.RECOVERY and not d.want_on
    assert "recovery_start" in rt.events
    # temperature back to the value before airing -> recovery ends early
    d = step(_input(now=t0 + 30 * 60, temp=20.95, window_open=False), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status != AreaStatus.RECOVERY


def test_short_airing_does_not_pause() -> None:
    rt = AreaRuntime()
    step(_input(now=0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    d = step(_input(now=120, window_open=False), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status not in (AreaStatus.WINDOW_OPEN, AreaStatus.RECOVERY)


def test_open_window_blocks_switch_on_before_delay() -> None:
    rt = AreaRuntime()
    d = step(_input(now=0, temp=20.0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    assert not d.want_on and d.status == AreaStatus.WINDOW_OPEN
    # a running circuit is not switched off before the window delay
    d = step(
        _input(now=60, temp=20.0, window_open=True, switch_on=True), PARAMS, SETTINGS, LEARNED, rt
    )
    assert d.want_on and d.status == AreaStatus.HEATING


def test_short_airing_starts_short_recovery() -> None:
    rt = AreaRuntime()
    step(_input(now=0, temp=21.0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    # 3 of 5 minutes window delay -> 60 % of the 30 min recovery = 18 min
    d = step(_input(now=180, temp=20.0, window_open=False), PARAMS, SETTINGS, LEARNED, rt)
    assert "short_recovery_start" in rt.events and rt.short_recovery
    assert rt.recovery_until == 180 + 0.6 * 1800
    assert not d.want_on and d.status == AreaStatus.RECOVERY
    # running circuits are not interrupted by a short recovery
    d = step(_input(now=240, temp=20.0, switch_on=True), PARAMS, SETTINGS, LEARNED, rt)
    assert d.want_on
    d = step(_input(now=180 + 1081, temp=20.0), PARAMS, SETTINGS, LEARNED, rt)
    assert d.want_on and d.status == AreaStatus.HEATING
    assert "short_recovery_end" in rt.events and not rt.short_recovery


def test_very_short_airing_is_ignored() -> None:
    rt = AreaRuntime()
    step(_input(now=0, temp=21.0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    d = step(_input(now=90, temp=20.0, window_open=False), PARAMS, SETTINGS, LEARNED, rt)
    assert rt.recovery_until is None
    assert d.want_on and d.status == AreaStatus.HEATING


def test_frost_overrides_short_airing() -> None:
    rt = AreaRuntime()
    d = step(_input(now=0, temp=6.0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    assert d.want_on and d.status == AreaStatus.FROST_PROTECTION


def test_recovery_times_out() -> None:
    rt = AreaRuntime()
    step(_input(now=0, temp=21.0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    step(_input(now=600, temp=19.0, window_open=True), PARAMS, SETTINGS, LEARNED, rt)
    step(_input(now=700, temp=19.0, window_open=False), PARAMS, SETTINGS, LEARNED, rt)
    d = step(_input(now=700 + 1801, temp=19.5, window_open=False), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status == AreaStatus.HEATING


def test_frost_protection_overrides_everything() -> None:
    rt = AreaRuntime()
    d = step(
        _input(temp=6.0, hvac_on=False, season_active=False, heating_day=False, window_open=True),
        PARAMS,
        SETTINGS,
        LEARNED,
        rt,
    )
    assert d.want_on and d.status == AreaStatus.FROST_PROTECTION
    d = step(_input(temp=7.3, hvac_on=False), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status == AreaStatus.FROST_PROTECTION  # hysteresis
    d = step(_input(temp=7.6, hvac_on=False), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status == AreaStatus.OFF


def test_no_heating_day_and_emergency() -> None:
    rt = AreaRuntime()
    settings = AreaSettings(emergency_duration_s=45 * 60)
    d = step(_input(now=0, temp=19.8, heating_day=False), PARAMS, settings, LEARNED, rt)
    assert d.status == AreaStatus.NO_HEATING_DAY and not d.want_on
    d = step(_input(now=46 * 60, temp=19.8, heating_day=False), PARAMS, settings, LEARNED, rt)
    assert d.status == AreaStatus.EMERGENCY and d.want_on
    assert rt.emergency_active


def test_emergency_needs_quiet_window() -> None:
    rt = AreaRuntime(last_window_change=0)
    settings = AreaSettings(emergency_duration_s=60, emergency_window_quiet_s=1800)
    step(_input(now=100, temp=19.0, heating_day=False), PARAMS, settings, LEARNED, rt)
    d = step(_input(now=400, temp=19.0, heating_day=False), PARAMS, settings, LEARNED, rt)
    assert d.status == AreaStatus.NO_HEATING_DAY


def test_out_of_season_and_off() -> None:
    assert (
        step(_input(season_active=False), PARAMS, SETTINGS, LEARNED, AreaRuntime()).status
        == AreaStatus.OUT_OF_SEASON
    )
    assert (
        step(_input(hvac_on=False), PARAMS, SETTINGS, LEARNED, AreaRuntime()).status
        == AreaStatus.OFF
    )


def test_sensor_error_is_off() -> None:
    d = step(_input(temp=None), PARAMS, SETTINGS, LEARNED, AreaRuntime())
    assert d.status == AreaStatus.SENSOR_ERROR and not d.want_on


def test_vacation_and_preheat_status() -> None:
    assert (
        step(
            _input(vacation=True, temp=18.5, target=18.0), PARAMS, SETTINGS, LEARNED, AreaRuntime()
        ).status
        == AreaStatus.VACATION
    )
    assert (
        step(
            _input(vacation=True, preheat=True, temp=18.0), PARAMS, SETTINGS, LEARNED, AreaRuntime()
        ).status
        == AreaStatus.PREHEAT
    )


def test_runtime_roundtrip() -> None:
    rt = AreaRuntime(window_open_since=5.0, window_paused=True, emergency_active=True)
    assert AreaRuntime.from_dict(rt.as_dict()).as_dict() == rt.as_dict()


def test_params_from_dict_ignores_garbage() -> None:
    params = ControlParams.from_dict(
        {"hysteresis_on": "0.3", "bogus": 1, "sun_factor": "x"}, puffer=0.5
    )
    assert params.hysteresis_on == 0.3 and params.puffer == 0.5 and params.sun_factor == 1.0


def test_preheat_start() -> None:
    # 3 K at 1 K/h = 3 h, + 1 h dead time + 0.5 h reserve
    start = preheat_start(100_000, 18.0, 21.0, 1.0, 3600, 1800)
    assert start == 100_000 - 3 * 3600 - 3600 - 1800
    assert preheat_start(100_000, 22.0, 21.0, 1.0, 0, 0) == 100_000


def test_carry_does_not_block_force_on_and_is_not_restored_from_a_stale_peak() -> None:
    rt = AreaRuntime()
    on = LearnedValues(cool_rate_kph=0.1, dead_time_s=1800, overshoot_k=0.6)
    step(_input(temp=20.4, switch_on=True, last_switch_change=0.0), PARAMS, SETTINGS, on, rt)
    off = LearnedValues(cool_rate_kph=0.1, dead_time_s=1800, overshoot_k=0.0)
    later = {"switch_on": False, "last_switch_change": 100_000.0}
    # no temperature on the switch-off tick: the carry starts anyway, no exception
    d = step(_input(now=100_601.0, temp=None, **later), PARAMS, SETTINGS, off, rt)
    assert d.status == AreaStatus.SENSOR_ERROR and rt.carry_peak == 21.0
    # 1 K below target wins over the carried peak
    d = step(_input(now=100_700.0, temp=19.9, **later), PARAMS, SETTINGS, off, rt)
    assert d.want_on
    # a pending carry is restored after a restart, the peak of the last run is not
    restored = AreaRuntime.from_dict(rt.as_dict())
    assert restored.carry_peak == 21.0 and restored.last_peak is None and not restored.was_on
    assert AreaRuntime.from_dict({"window_paused": False}).carry_peak is None


def test_window_reopened_during_recovery_keeps_the_first_reference() -> None:
    rt = AreaRuntime()
    base = {"switch_on": False, "last_switch_change": 0.0}
    step(_input(now=0.0, temp=21.0, window_open=True, **base), PARAMS, SETTINGS, LEARNED, rt)
    step(_input(now=400.0, temp=20.5, window_open=True, **base), PARAMS, SETTINGS, LEARNED, rt)
    assert rt.window_paused
    d = step(_input(now=500.0, temp=20.3, window_open=False, **base), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status == AreaStatus.RECOVERY and rt.temp_before_open == 21.0
    step(_input(now=600.0, temp=20.3, window_open=True, **base), PARAMS, SETTINGS, LEARNED, rt)
    assert rt.temp_before_open == 21.0  # not the lowered temperature
    d = step(_input(now=700.0, temp=20.4, window_open=False, **base), PARAMS, SETTINGS, LEARNED, rt)
    assert d.status == AreaStatus.RECOVERY  # 20.4 is not "recovered" against 21.0


def test_recovery_ends_exactly_one_margin_below_the_reference() -> None:
    rt = AreaRuntime()
    base = {"switch_on": False, "last_switch_change": 0.0}
    step(_input(now=0.0, temp=21.0, window_open=True, **base), PARAMS, SETTINGS, LEARNED, rt)
    step(_input(now=400.0, temp=20.5, window_open=True, **base), PARAMS, SETTINGS, LEARNED, rt)
    step(_input(now=500.0, temp=20.5, window_open=False, **base), PARAMS, SETTINGS, LEARNED, rt)
    # 20.9 >= 21.0 - 0.1 although 21.0 - 0.1 is 20.900000000000002 as a float
    d = step(_input(now=560.0, temp=20.9, window_open=False, **base), PARAMS, SETTINGS, LEARNED, rt)
    assert rt.recovery_until is None and d.status == AreaStatus.HEATING
