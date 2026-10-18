"""Tests for the heat meter (consumption between readings)."""

import pytest
from logic.energy import HeatMeter, to_kwh

H = 3600.0


def test_units() -> None:
    assert to_kwh(1.234, "MWh") == pytest.approx(1234.0)
    assert to_kwh(500, "Wh") == pytest.approx(0.5)
    assert to_kwh(1, "GJ") == pytest.approx(277.78, abs=0.01)
    assert to_kwh(1, "°C") is None


def test_span_between_readings_with_demand() -> None:
    meter = HeatMeter()
    meter.add_demand(5)  # before the first reading: not part of any span
    assert meter.update(1000.0, 0)
    meter.rebase("check")
    meter.add_demand(16)
    assert not meter.update(1000.0, 1 * H)  # same value: no new reading
    meter.add_demand(16)
    assert meter.update(1010.0, 2 * H)
    span = meter.since("check")
    assert span is not None
    assert span.kwh == pytest.approx(10.0)
    assert span.hours == pytest.approx(2.0)
    assert span.demand_kh == pytest.approx(32.0)
    assert span.kwh_per_kh == pytest.approx(10 / 32)


def test_short_span_and_missing_baseline() -> None:
    meter = HeatMeter()
    assert meter.since("check") is None  # no reading yet
    meter.update(1000.0, 0)
    assert meter.since("check") is None  # baseline starts with this reading
    meter.update(1001.0, 0.5 * H)
    assert meter.since("check") is None  # shorter than an hour: too coarse
    assert meter.kwh_since("check") == pytest.approx(1.0)


def test_reset_restarts_baselines() -> None:
    meter = HeatMeter()
    meter.update(1000.0, 0)
    meter.rebase("check")
    meter.update(5.0, 2 * H)  # new meter
    meter.update(8.0, 4 * H)
    span = meter.since("check")
    assert span is not None and span.kwh == pytest.approx(3.0)


def test_calendar_periods_keep_yesterday_only_without_gap() -> None:
    meter = HeatMeter()
    meter.update(100.0, 0)
    meter.roll("today", "2026-11-16", "yesterday", "2026-11-15")
    meter.update(130.0, 10 * H)
    meter.roll("today", "2026-11-17", "yesterday", "2026-11-16")
    assert meter.closed["yesterday"] == pytest.approx(30.0)
    meter.update(150.0, 34 * H)
    meter.roll("today", "2026-11-19", "yesterday", "2026-11-18")  # a day missed
    assert "yesterday" not in meter.closed


def test_roundtrip() -> None:
    meter = HeatMeter(entity="sensor.heat")
    meter.add_demand(3)
    meter.update(1.0, 10)
    meter.rebase("check")
    meter.roll("month", "2026-11", "last_month", "2026-10")
    restored = HeatMeter.from_dict(meter.as_dict())
    assert restored == meter
    assert HeatMeter.from_dict(None) == HeatMeter()
