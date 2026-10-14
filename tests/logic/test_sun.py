"""Tests for the expected solar gain over the lead time."""

from datetime import datetime

import pytest
from logic.controller import ControlParams, LearnedValues, thermostat
from logic.learning import ThermalModel
from logic.sun import (
    FORECAST_TRUST,
    SunScale,
    clear_sky_index,
    cloud_factor,
    cloud_pct,
    planning_pv,
    sensor_point,
    solar_elevation,
    weather_points,
)

from .test_controller import _input

LAT, LON = 50.0, 10.0  # generic mid European position, not a real site


def _ts(text: str) -> float:
    return datetime.fromisoformat(text).timestamp()


def test_solar_elevation_noon_and_night() -> None:
    # Local solar noon at 10° east is about 11:20 UTC.
    summer = solar_elevation(_ts("2024-06-21T11:20:00+00:00"), LAT, LON)
    winter = solar_elevation(_ts("2024-12-21T11:20:00+00:00"), LAT, LON)
    assert summer == pytest.approx(90 - LAT + 23.44, abs=0.6)
    assert winter == pytest.approx(90 - LAT - 23.44, abs=0.6)
    assert solar_elevation(_ts("2024-12-21T23:20:00+00:00"), LAT, LON) < -40


def test_clear_sky_and_clouds() -> None:
    assert clear_sky_index(-5) == 0.0
    assert clear_sky_index(10) < clear_sky_index(30) < clear_sky_index(60)
    assert clear_sky_index(90) == pytest.approx(1.04, abs=0.01)
    assert cloud_factor(0) == 1.0
    assert cloud_factor(100) == pytest.approx(0.25)
    assert cloud_factor(50) > 0.9  # few clouds hardly matter, heavy cover does


def test_cloud_pct_fallbacks() -> None:
    assert cloud_pct({"cloud_coverage": 20, "condition": "cloudy"}) == 20
    assert cloud_pct({"condition": "sunny"}) == 0
    assert cloud_pct({"condition": "partlycloudy"}) == 50
    assert cloud_pct({"condition": "something-new"}) == 100  # conservative


def test_sun_scale_learns_only_on_clear_sky() -> None:
    scale = SunScale()
    assert not scale.update(3.0, 0.8, 80)  # too cloudy
    assert not scale.update(3.0, 0.1, 0)  # sun too low
    assert not scale.update(3.0, 0.8, None)  # no weather
    assert scale.update(4.0, 0.8, 0)
    assert scale.value == pytest.approx(5.0)
    scale.update(0.0, 0.8, 0)  # e.g. snow on the panels pulls it down slowly
    assert 4.8 < scale.value < 5.0


def test_weather_points() -> None:
    hourly = [
        {"datetime": "2024-03-20T10:00:00+00:00", "cloud_coverage": 0},
        {"datetime": "2024-03-20T11:00:00+00:00", "condition": "cloudy"},
        {"datetime": "2024-03-20T22:00:00+00:00", "cloud_coverage": 0},
        {"datetime": "not a date"},
    ]
    points = weather_points(hourly, 5.0, LAT, LON)
    assert len(points) == 3
    clear, cloudy, night = (p[1] for p in points)
    assert 3.0 < clear < 5.0
    assert cloudy < clear / 2
    assert night == 0.0
    assert points[0][0] == _ts("2024-03-20T10:30:00+00:00")


def test_sensor_point_units() -> None:
    assert sensor_point(0, 1500, "Wh") == (1800, 1.5)
    assert sensor_point(0, 2.0, "kWh") == (1800, 2.0)
    assert sensor_point(0, 800, "W") == (3600, 0.8)
    assert sensor_point(0, 1.2, "kW") == (3600, 1.2)
    assert sensor_point(0, 5, "%") is None
    assert sensor_point(0, None, "W") is None


def test_planning_pv_without_forecast_uses_current_value() -> None:
    assert planning_pv(0, 1.3, [], 3600) == 1.3
    assert planning_pv(1000, 1.3, [(500, 4.0)], 3600) == 1.3  # only past values
    assert planning_pv(0, 1.3, [(3600, 4.0)], 0) == 1.3


def test_planning_pv_mean_over_lead_time() -> None:
    # 0 kW now, 2 kW expected in one hour: linear ramp, reduced by the forecast trust
    expected = 2.0 * FORECAST_TRUST
    assert planning_pv(0, 0.0, [(3600, 2.0)], 3600) == pytest.approx(expected / 2)
    # second hour stays at the last forecast value
    assert planning_pv(0, 0.0, [(3600, 2.0)], 7200) == pytest.approx(expected * 0.75)
    # evening: sun now, none expected -> less than the current value
    assert planning_pv(0, 2.0, [(3600, 0.0)], 3600) < 2.0


def _model(k: float = 0.005, s: float = 0.3) -> ThermalModel:
    model = ThermalModel()
    model.theta = [1.0, k, s]
    return model


def test_expected_sun_prevents_morning_switch_on() -> None:
    model = _model()
    params = ControlParams()
    data = _input(temp=20.82, target=21.0)
    # 10 K difference -> 0.05 K/h cooling, no sun yet: 20.77 after one hour -> on
    dark = LearnedValues(cool_rate_kph=model.cool_rate(10, 0.0), dead_time_s=3600)
    assert thermostat(data, params, dark)[0]
    # 2 kW expected within the hour: the room warms instead -> stay off
    pv = planning_pv(0, 0.0, [(3600, 2.0)], 3600)
    sunny = LearnedValues(cool_rate_kph=model.cool_rate(10, pv), dead_time_s=3600)
    want, predicted, _ = thermostat(data, params, sunny)
    assert not want and predicted > 20.82


def test_force_on_still_wins_against_sun() -> None:
    model = _model()
    pv = planning_pv(0, 0.0, [(3600, 10.0)], 3600)
    sunny = LearnedValues(cool_rate_kph=model.cool_rate(10, pv), dead_time_s=3600)
    want, predicted, _ = thermostat(_input(temp=19.9, target=21.0), ControlParams(), sunny)
    assert want and predicted > 21.0 - ControlParams().hysteresis_on  # off without the rule
