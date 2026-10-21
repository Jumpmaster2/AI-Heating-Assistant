"""Tests for physics helpers and the ventilation recommendation."""

from datetime import date

import pytest
from logic.physics import absolute_humidity, in_season, parse_day_month
from logic.ventilation import (
    VentilationInput,
    VentilationSettings,
    VentilationState,
    is_blocking,
    recommend,
)


def test_absolute_humidity_reference_values() -> None:
    # 20 °C / 50 % is about 8.6 g/m³, 0 °C / 100 % about 4.85 g/m³
    assert absolute_humidity(20, 50) == pytest.approx(8.63, abs=0.05)
    assert absolute_humidity(0, 100) == pytest.approx(4.85, abs=0.05)


def test_parse_day_month() -> None:
    assert parse_day_month("01.10.") == (1, 10)
    assert parse_day_month("31.3") == (31, 3)
    with pytest.raises(ValueError):
        parse_day_month("31.02.")
    with pytest.raises(ValueError):
        parse_day_month("abc")


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 10, 1), True),
        (date(2026, 1, 15), True),
        (date(2026, 3, 31), True),
        (date(2026, 7, 1), False),
        (date(2026, 9, 30), False),
    ],
)
def test_season_wraps_year(day: date, expected: bool) -> None:
    assert in_season(day, (1, 10), (31, 3)) is expected


def test_season_within_year() -> None:
    assert in_season(date(2026, 5, 1), (1, 4), (30, 6))
    assert not in_season(date(2026, 8, 1), (1, 4), (30, 6))


SETTINGS = VentilationSettings()


def _data(**kwargs) -> VentilationInput:
    base = {"temp": 22.0, "humidity": 65.0, "ref_temp": 10.0, "ref_humidity": 90.0}
    base.update(kwargs)
    return VentilationInput(**base)


def test_humid_room_dry_outside_ventilate_now() -> None:
    result = recommend(_data(heating_active=True), SETTINGS)
    assert result.state == VentilationState.VENTILATE_NOW
    assert result.recommended
    assert result.delta_ah and result.delta_ah > 0.8


def test_cooling_useful_without_heating() -> None:
    result = recommend(_data(humidity=45.0), SETTINGS)
    assert result.state == VentilationState.VENTILATION_USEFUL


def test_no_cooling_advantage_while_heating() -> None:
    result = recommend(_data(humidity=45.0, heating_active=True), SETTINGS)
    assert result.state == VentilationState.OPTIMAL


def test_humid_outside_do_not_ventilate() -> None:
    result = recommend(
        _data(humidity=65.0, ref_temp=20.0, ref_humidity=95.0, heating_active=True), SETTINGS
    )
    assert result.state == VentilationState.DO_NOT_VENTILATE


def test_open_window_without_benefit_close() -> None:
    result = recommend(
        _data(
            humidity=45.0, ref_temp=20.0, ref_humidity=95.0, window_open=True, heating_active=True
        ),
        SETTINGS,
    )
    assert result.state == VentilationState.CLOSE_WINDOW


def test_blocked() -> None:
    assert recommend(_data(blocked=True), SETTINGS).state == VentilationState.BLOCKED
    assert (
        recommend(_data(blocked=True, window_open=True), SETTINGS).state
        == VentilationState.CLOSE_WINDOW
    )


def test_indoor_reference_cools_only_at_night() -> None:
    day = recommend(
        _data(humidity=45.0, ref_temp=20.0, ref_humidity=40.0, reference_is_indoor=True), SETTINGS
    )
    night = recommend(
        _data(
            humidity=45.0, ref_temp=20.0, ref_humidity=40.0, reference_is_indoor=True, is_night=True
        ),
        SETTINGS,
    )
    assert day.state == VentilationState.OPTIMAL
    assert night.state == VentilationState.VENTILATION_USEFUL


def test_warm_outside_limits_drying() -> None:
    # Outside 5 K warmer than inside: drying is not useful even if drier.
    result = recommend(_data(temp=20.0, humidity=70.0, ref_temp=25.0, ref_humidity=30.0), SETTINGS)
    assert result.state == VentilationState.DO_NOT_VENTILATE


def test_missing_values_unknown() -> None:
    assert recommend(_data(humidity=None), SETTINGS).state == VentilationState.UNKNOWN


def test_cooling_in_heating_period_needs_margin_above_target() -> None:
    # 22 °C, target 21, margin 1 K: exactly at the limit -> useful
    at_limit = recommend(_data(humidity=45.0, season_active=True, target=21.0), SETTINGS)
    assert at_limit.state == VentilationState.VENTILATION_USEFUL
    # 22 °C, target 21.5: below target + margin -> no cooling advice
    below = recommend(_data(humidity=45.0, season_active=True, target=21.5), SETTINGS)
    assert below.state == VentilationState.OPTIMAL


def test_cooling_margin_is_configurable_and_ignored_outside_season() -> None:
    strict = VentilationSettings(cooling_margin=3.0)
    assert recommend(_data(humidity=45.0, season_active=True, target=21.0), strict).state == (
        VentilationState.OPTIMAL
    )
    # outside the heating period the target does not matter (summer cooling)
    assert recommend(_data(humidity=45.0, season_active=False, target=25.0), strict).state == (
        VentilationState.VENTILATION_USEFUL
    )


def test_drying_not_affected_by_cooling_margin() -> None:
    result = recommend(_data(humidity=70.0, season_active=True, target=23.0), SETTINGS)
    assert result.state == VentilationState.VENTILATE_NOW


def test_cooling_min_temp_applies_all_year() -> None:
    settings = VentilationSettings(cooling_min_temp=23.5)
    # 22 °C room: below the minimum -> no cooling advice, in and outside the heating period
    for season in (True, False):
        result = recommend(_data(humidity=45.0, season_active=season, target=18.0), settings)
        assert result.state == VentilationState.OPTIMAL
        assert not result.cooling_useful
    warm = recommend(_data(temp=24.0, humidity=45.0, season_active=True, target=18.0), settings)
    assert warm.state == VentilationState.VENTILATION_USEFUL


def test_no_cooling_if_outside_air_makes_room_too_humid() -> None:
    # 14.5 °C / 99 % outside is about 12.3 g/m³, at 22 °C that is about 63 % > 60 %
    result = recommend(
        _data(humidity=60.0, ref_temp=14.5, ref_humidity=99.0, season_active=True, target=18.0),
        SETTINGS,
    )
    assert not result.cooling_useful
    assert result.rh_after_exchange is not None and result.rh_after_exchange > 60
    assert result.state == VentilationState.DO_NOT_VENTILATE
    # same air with a higher humidity threshold of the area is fine
    relaxed = recommend(
        _data(humidity=55.0, ref_temp=14.5, ref_humidity=99.0, season_active=True, target=18.0),
        VentilationSettings(rh_threshold=70.0),
    )
    assert relaxed.cooling_useful


@pytest.mark.parametrize(
    ("domain", "state", "expected"),
    [
        ("cover", "open", False),  # sun protection up: ventilating is fine
        ("cover", "opening", False),
        ("cover", "closed", True),
        ("cover", "closing", True),
        ("climate", "off", False),
        ("climate", "cool", True),
        ("climate", "heat_cool", True),
        ("water_heater", "eco", True),
        ("switch", "on", True),
        ("binary_sensor", "off", False),
        ("fan", "on", True),
        ("media_player", "playing", True),  # other domains: active unless off or idle
        ("media_player", "idle", False),
        ("cover", "unavailable", False),
        ("climate", "unknown", False),
    ],
)
def test_block_entity_per_domain(domain: str, state: str, expected: bool) -> None:
    assert is_blocking(domain, state) is expected


def _humid(humidity: float, **kwargs: object) -> VentilationInput:
    values: dict = {
        "temp": 21.0,
        "humidity": humidity,
        "ref_temp": 5.0,
        "ref_humidity": 80.0,
        "heating_active": True,  # no cooling advantage
    }
    values.update(kwargs)
    return VentilationInput(**values)


def test_humidity_hysteresis_keeps_the_recommendation() -> None:
    settings = VentilationSettings(rh_threshold=60.0, rh_hysteresis=3.0)
    assert recommend(_humid(58.0), settings).state == VentilationState.OPTIMAL
    # still high until 3 % below the threshold once it was high
    assert recommend(_humid(58.0, was_rh_high=True), settings).state == (
        VentilationState.VENTILATE_NOW
    )
    assert recommend(_humid(57.0, was_rh_high=True), settings).state == VentilationState.OPTIMAL


def test_airing_that_cannot_lower_the_humidity_is_not_recommended() -> None:
    settings = VentilationSettings(rh_threshold=60.0, min_rh_drop=3.0)
    assert recommend(_humid(65.0, achievable_rh=55.0), settings).state == (
        VentilationState.VENTILATE_NOW
    )
    result = recommend(_humid(65.0, achievable_rh=63.0), settings)
    assert result.state == VentilationState.DO_NOT_VENTILATE
    assert result.achievable_rh == 63.0


def test_ventilation_settings_round_trip() -> None:
    settings = VentilationSettings.from_dict(
        {"rh_threshold": 65, "min_rh_drop": "x"}, min_ah_advantage=1.2
    )
    assert settings.rh_threshold == 65.0
    assert settings.min_ah_advantage == 1.2
    assert settings.min_rh_drop == 3.0
    assert VentilationSettings.from_dict(settings.as_dict()) == settings
