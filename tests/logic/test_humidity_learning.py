"""Tests for the learned humidity profile of an area."""

import math

import pytest
from logic.humidity_learning import FLOOR_DAYS, MIN_DAY_SAMPLES, HumidityProfile
from logic.physics import absolute_humidity

REF_AH = absolute_humidity(5.0, 80.0)  # about 5.4 g/m³


def _day(profile: HumidityProfile, date: str, rh: float, ts: float = 0.0) -> float:
    """One day of minute samples at constant humidity, the last hours at night."""
    for i in range(MIN_DAY_SAMPLES + 10):
        night = i >= MIN_DAY_SAMPLES - 60
        profile.add_sample(ts, date, "heating", night, 21.0, rh, REF_AH, False)
        ts += 60
    return ts


def test_usual_course_and_floor() -> None:
    profile = HumidityProfile()
    _day(profile, "2026-10-01", 55.0)
    _day(profile, "2026-10-02", 50.0)
    profile.add_sample(0.0, "2026-10-03", "heating", False, 21.0, 52.0, REF_AH, False)
    typical = profile.typical["heating"]
    assert typical["rh_mean"].count == 2
    assert 50.0 < typical["rh_mean"].value < 55.0
    assert profile.floor_rh == 50.0
    summary = profile.summary("heating", 21.0, 52.0, REF_AH)
    assert summary["days"] == 2 and summary["typical"]["rh_night"] > 0
    assert profile.summary("summer", 21.0, 52.0, REF_AH)["typical"] is None


def test_short_day_counts_for_the_floor_only() -> None:
    profile = HumidityProfile()
    profile.add_sample(0.0, "2026-10-01", "heating", False, 21.0, 45.0, REF_AH, False)
    profile.add_sample(60.0, "2026-10-02", "heating", False, 21.0, 50.0, REF_AH, False)
    assert profile.floor_rh == 45.0
    assert profile.typical["heating"]["rh_mean"].count == 0


def test_floor_keeps_the_last_days() -> None:
    profile = HumidityProfile()
    for day in range(FLOOR_DAYS + 3):
        profile.add_sample(
            day * 86400.0, f"d{day:02d}", "heating", False, 21.0, 40.0 + day, REF_AH, False
        )
    profile.add_sample(0.0, "end", "heating", False, 21.0, 70.0, REF_AH, False)
    assert len(profile.floor) == FLOOR_DAYS
    assert profile.floor_rh == 43.0


def _airing(profile: HumidityProfile, ts: float, start: float, low: float, after: float) -> float:
    """Ten minutes of airing from ``start`` down to ``low`` % and ``after`` % 30 min later."""
    profile.add_sample(ts, "d", "heating", False, 21.0, start, REF_AH, True)
    for i in range(1, 11):
        rh = start - (start - low) * i / 10
        profile.add_sample(ts + i * 60, "d", "heating", False, 21.0, rh, REF_AH, True)
    profile.add_sample(ts + 660, "d", "heating", False, 21.0, low, REF_AH, False)
    profile.add_sample(ts + 660 + 1800, "d", "heating", False, 21.0, after, REF_AH, False)
    return ts + 4000


def test_airing_effect_and_reachable_humidity() -> None:
    profile = HumidityProfile()
    assert profile.achievable_rh(21.0, 65.0, REF_AH) is None
    ts = _airing(profile, 0.0, 65.0, 50.0, 56.0)
    assert profile.achievable_rh(21.0, 65.0, REF_AH) is None  # one airing is not enough
    _airing(profile, ts, 65.0, 50.0, 56.0)
    assert profile.known_effect
    assert 0.3 < profile.exchange.value < 0.9
    assert profile.rebound.value > 0.2
    reachable = profile.achievable_rh(21.0, 65.0, REF_AH)
    assert reachable is not None and 50.0 < reachable < 65.0
    event = profile.events[-1]
    assert event["min"] == 11 and event["rh_min"] == 50.0 and event["rh_after_30"] == 56.0
    # reference air more humid than the room: airing does not dry
    assert profile.achievable_rh(21.0, 30.0, 20.0) == 30.0


def test_short_opening_and_reopening() -> None:
    profile = HumidityProfile()
    profile.add_sample(0.0, "d", "heating", False, 21.0, 65.0, REF_AH, True)
    profile.add_sample(60.0, "d", "heating", False, 21.0, 64.0, REF_AH, False)
    assert profile.events == [] and profile.pending is None
    ts = 120.0
    for i in range(5):
        profile.add_sample(ts + i * 60, "d", "heating", False, 21.0, 65.0 - i, REF_AH, True)
    profile.add_sample(ts + 300, "d", "heating", False, 21.0, 61.0, REF_AH, False)
    assert profile.pending is not None
    profile.add_sample(ts + 360, "d", "heating", False, 21.0, 61.0, REF_AH, True)
    assert profile.pending is None  # opened again before the rebound could be judged


def test_moisture_load_with_closed_windows() -> None:
    profile = HumidityProfile()
    profile.add_sample(0.0, "d", "heating", False, 21.0, 50.0, REF_AH, False)
    profile.add_sample(3600.0, "d", "heating", False, 21.0, 60.0, REF_AH, False)
    expected = absolute_humidity(21.0, 60.0) - absolute_humidity(21.0, 50.0)
    assert profile.load.count == 1
    assert profile.load.value == pytest.approx(expected, rel=0.01)


def test_profile_round_trip_and_bad_data() -> None:
    profile = HumidityProfile()
    ts = _day(profile, "2026-10-01", 55.0)
    ts = _airing(profile, ts, 65.0, 50.0, 56.0)
    profile.add_sample(ts, "2026-10-02", "heating", False, 21.0, 52.0, REF_AH, True)
    restored = HumidityProfile.from_dict(profile.as_dict())
    assert restored.as_dict() == profile.as_dict()
    broken = HumidityProfile.from_dict(
        {"floor": [["a", "x"], [1]], "airing": {"ts": 1}, "hour": ["a", 1], "events": [1]}
    )
    assert broken.floor == [] and broken.airing is None and broken.hour is None
    assert broken.events == []
    assert HumidityProfile.from_dict(None).floor_rh is None


def test_missing_values_are_skipped() -> None:
    profile = HumidityProfile()
    profile.add_sample(0.0, "d", "heating", False, None, 50.0, REF_AH, False)
    assert profile.day.n == 0 and profile.hour is None


def _exp_airing(profile: HumidityProfile, ts: float, k: float, minutes: int) -> float:
    """Airing where the gap to the reference shrinks with exp(-k t), 16 K difference."""
    ah0 = absolute_humidity(21.0, 65.0)
    for i in range(minutes + 1):
        ah = REF_AH + (ah0 - REF_AH) * math.exp(-k * i)
        rh = 100.0 * ah / absolute_humidity(21.0, 100.0)
        profile.add_sample(ts + i * 60, "d", "heating", False, 21.0, rh, REF_AH, True, 16.0, 7)
    profile.add_sample(ts + (minutes + 1) * 60, "d", "heating", False, 21.0, 50.0, REF_AH, False)
    return ts + (minutes + 40) * 60


def test_air_exchange_rate_gives_the_airing_time() -> None:
    profile = HumidityProfile()
    assert profile.airing_minutes(21.0, 65.0, REF_AH, 16.0, 55.0) is None
    ts = _exp_airing(profile, 0.0, 0.1, 10)
    _exp_airing(profile, ts, 0.1, 10)
    # 0.1/min over 10 of the 11 open minutes (closing is seen a minute later), at 16 K
    k = 0.1 * 10 / 11
    assert profile.rate.value == pytest.approx(k / 4, rel=0.02)
    assert profile.events[-1]["suggested_min"] == 7
    assert profile.last_closed is not None
    ah0 = absolute_humidity(21.0, 65.0)
    target = absolute_humidity(21.0, 55.0)
    expected = -math.log((target - REF_AH) / (ah0 - REF_AH)) / k
    assert profile.airing_minutes(21.0, 65.0, REF_AH, 16.0, 55.0) == pytest.approx(
        expected, rel=0.03
    )
    # less temperature difference: less draft, longer airing
    assert profile.airing_minutes(21.0, 65.0, REF_AH, 4.0, 55.0) == pytest.approx(
        expected * 2, rel=0.03
    )
    restored = HumidityProfile.from_dict(profile.as_dict())
    assert restored.rate.value == profile.rate.value
    assert restored.last_closed == profile.last_closed
