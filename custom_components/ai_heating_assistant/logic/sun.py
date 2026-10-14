"""Expected solar gain over the lead time (pure logic, no Home Assistant).

The thermal model learns the warming per kW of PV power. With only the current PV
power the controller cannot know that the sun will heat a room in an hour. This
module turns a PV forecast sensor or the hourly weather forecast into a series of
expected PV values and averages them over the lead time of an area.

Without a PV forecast sensor the expected PV power is estimated from the sun
elevation and the forecast cloud coverage. The scale (kW at a clear sky per unit of
the clear sky index) is learned from the real PV power on nearly cloudless days, so
the orientation and size of the PV system need not be configured.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

FORECAST_TRUST = 0.7  # forecasts are uncertain: only part of the expected gain is used
STEP_S = 300.0  # sampling step for the mean over the lead time
CALIBRATION_MIN_INDEX = 0.2  # sun high enough for a meaningful calibration sample
CALIBRATION_MAX_CLOUD = 30.0  # % cloud coverage accepted for calibration samples
CALIBRATION_ALPHA = 0.02  # per sample (one per minute)

# Cloud coverage in % assumed for a weather condition without cloud_coverage.
# Unknown conditions count as overcast, which is the conservative choice.
CONDITION_CLOUD = {
    "sunny": 0.0,
    "clear-night": 0.0,
    "windy": 30.0,
    "partlycloudy": 50.0,
    "windy-variant": 70.0,
    "cloudy": 90.0,
    "rainy": 90.0,
    "snowy": 90.0,
    "snowy-rainy": 90.0,
}

POWER_UNITS = {"W": 0.001, "kW": 1.0, "MW": 1000.0}
ENERGY_UNITS = {"Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}

type Point = tuple[float, float]  # (timestamp, expected PV power in kW)


def solar_elevation(ts: float, lat: float, lon: float) -> float:
    """Sun elevation in degrees (low precision formula, good to about 0.5°)."""
    days = ts / 86400.0 + 2440587.5 - 2451545.0  # days since J2000.0
    mean_anomaly = math.radians(357.529 + 0.98560028 * days)
    mean_long = 280.459 + 0.98564736 * days
    ecl_long = math.radians(
        mean_long + 1.915 * math.sin(mean_anomaly) + 0.020 * math.sin(2 * mean_anomaly)
    )
    obliquity = math.radians(23.439 - 0.00000036 * days)
    right_asc = math.atan2(math.cos(obliquity) * math.sin(ecl_long), math.cos(ecl_long))
    declination = math.asin(math.sin(obliquity) * math.sin(ecl_long))
    sidereal_h = (18.697374558 + 24.06570982441908 * days) % 24
    hour_angle = math.radians(sidereal_h * 15 + lon) - right_asc
    lat_r = math.radians(lat)
    sin_elev = math.sin(lat_r) * math.sin(declination) + math.cos(lat_r) * math.cos(
        declination
    ) * math.cos(hour_angle)
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_elev))))


def clear_sky_index(elevation_deg: float) -> float:
    """Clear sky irradiance relative to 1000 W/m² (Haurwitz model)."""
    sin_elev = math.sin(math.radians(elevation_deg))
    if sin_elev <= 0.01:
        return 0.0
    return 1.098 * sin_elev * math.exp(-0.057 / sin_elev)


def cloud_factor(cloud_pct: float) -> float:
    """Share of the clear sky irradiance at a cloud coverage (Kasten and Czeplak)."""
    cover = max(0.0, min(100.0, cloud_pct)) / 100.0
    return 1.0 - 0.75 * cover**3.4


def cloud_pct(item: dict[str, Any]) -> float:
    """Cloud coverage of a forecast item or weather state in %."""
    value = item.get("cloud_coverage")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return CONDITION_CLOUD.get(str(item.get("condition", "")), 100.0)


@dataclass(slots=True)
class SunScale:
    """Learned PV power in kW per unit of clear sky irradiance."""

    value: float | None = None

    def update(self, pv_kw: float, index: float, cloud: float | None) -> bool:
        """Feed one observation. Returns True if the scale changed."""
        if cloud is None or cloud > CALIBRATION_MAX_CLOUD or index < CALIBRATION_MIN_INDEX:
            return False
        sample = max(0.0, pv_kw) / (index * cloud_factor(cloud))
        if self.value is None:
            self.value = sample
        else:
            self.value += CALIBRATION_ALPHA * (sample - self.value)
        return True


def _timestamp(value: Any) -> float | None:
    if isinstance(value, datetime):
        return value.timestamp() if value.tzinfo else None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.timestamp() if parsed.tzinfo else None


def weather_points(
    hourly: list[dict[str, Any]], scale: float, lat: float, lon: float
) -> list[Point]:
    """Expected PV power per forecast hour (taken at the middle of the hour)."""
    points = []
    for item in hourly:
        start = _timestamp(item.get("datetime"))
        if start is None:
            continue
        mid = start + 1800.0
        index = clear_sky_index(solar_elevation(mid, lat, lon))
        points.append((mid, scale * index * cloud_factor(cloud_pct(item))))
    return sorted(points)


def sensor_point(now: float, value: float | None, unit: str | None) -> Point | None:
    """Expected PV power from a forecast sensor.

    An energy value (Wh, kWh) is the production of the next hour, i.e. its mean power,
    placed in the middle of that hour. A power value (W, kW) is the expected power in
    one hour, as provided by Forecast.Solar.
    """
    if value is None or unit is None:
        return None
    if unit in ENERGY_UNITS:
        return now + 1800.0, max(0.0, value * ENERGY_UNITS[unit])
    if unit in POWER_UNITS:
        return now + 3600.0, max(0.0, value * POWER_UNITS[unit])
    return None


def _interpolate(points: list[Point], ts: float) -> float:
    if ts >= points[-1][0]:
        return points[-1][1]
    for (t0, v0), (t1, v1) in itertools.pairwise(points):
        if t0 <= ts <= t1:
            return v0 if t1 == t0 else v0 + (v1 - v0) * (ts - t0) / (t1 - t0)
    return points[0][1]


FORECAST_STALE_S = 2 * 3600.0  # forecast points older than this say nothing about now


def expected_now(points: list[Point], now: float, trust: float = FORECAST_TRUST) -> float | None:
    """PV power expected right now from the forecast points, or None without a usable one."""
    if not points or now - points[-1][0] > FORECAST_STALE_S:
        return None
    return max(0.0, _interpolate(points, now) * trust)


def planning_pv(
    now: float,
    pv_now: float,
    points: list[Point],
    horizon_s: float,
    trust: float = FORECAST_TRUST,
) -> float:
    """Mean PV power expected over the next ``horizon_s`` seconds.

    The series starts at the current PV power and runs to the forecast values,
    which are reduced by ``trust``. After the last forecast value it stays
    constant. Without a forecast the current PV power is returned (old behaviour).
    """
    future = [(t, v * trust) for t, v in points if t > now]
    if not future or horizon_s <= 0:
        return pv_now
    series = [(now, pv_now), *future]
    steps = max(1, math.ceil(horizon_s / STEP_S))
    total = sum(_interpolate(series, now + horizon_s * (i + 0.5) / steps) for i in range(steps))
    return total / steps
