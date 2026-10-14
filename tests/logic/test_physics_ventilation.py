"""Tests for physics helpers and the ventilation recommendation."""

from datetime import date

import pytest
from logic.physics import absolute_humidity, in_season, parse_day_month
from logic.ventilation import VentilationInput, VentilationSettings, VentilationState, recommend


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
